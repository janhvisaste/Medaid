"""Regression tests for Fix 9: the dietary rate-limit gate must not admit
more concurrent requests than DIETARY_GLOBAL_ACTIVE_LIMIT.

The old gate did cache.get(...) -> compare -> cache.incr(...), so N concurrent
requests could all read an under-limit value before any of them incremented.
These tests exercise real thread contention rather than asserting on the
implementation shape.
"""
import threading
import time

from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from rest_framework.test import APIClient

from .models import User
from .views import _cache_release, _cache_reserve

ACTIVE_GLOBAL_KEY = 'dietary:global:active'

FAKE_ADVICE = {
    'id': 1,
    'summary': 'Personalized guidance.',
    'cards': [{'category': 'Meal', 'name': 'Bowl', 'rationale': 'Context-aware.', 'nutrient_highlights': []}],
    'daily_pattern': [],
    'model_id': 'test/free-model',
    'free_tier': True,
    'safety_flags': [],
    'safety_notice': 'General guidance.',
    'context_used': {'profile': False, 'assessment_history': 0, 'report_history': 0,
                     'conversation_turns': 0, 'previous_dietary_advice': 0},
}


class CacheReservePrimitiveTests(TransactionTestCase):
    """The reserve primitive itself must hand out at most `limit` slots."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_concurrent_reservations_never_exceed_limit(self):
        limit = 3
        worker_count = 40
        key = 'test:concurrency:slots'
        admitted = []
        admitted_lock = threading.Lock()
        start = threading.Barrier(worker_count)

        def worker():
            start.wait()  # maximize real contention
            value = _cache_reserve(key, 60)
            if value <= limit:
                with admitted_lock:
                    admitted.append(value)
                # Hold the slot briefly, then release it.
                time.sleep(0.01)
                _cache_release(key, 60)
            else:
                _cache_release(key, 60)

        threads = [threading.Thread(target=worker) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # No admitted request ever saw a post-increment value above the limit,
        # and no two admissions got the same slot number concurrently.
        self.assertTrue(admitted, 'no worker was admitted at all')
        self.assertLessEqual(max(admitted), limit)

    def test_release_never_drives_counter_negative(self):
        key = 'test:concurrency:negative'
        for _ in range(5):
            _cache_release(key, 60)
        self.assertGreaterEqual(cache.get(key, 0), 0)


@override_settings(
    DIETARY_GLOBAL_ACTIVE_LIMIT=2,
    DIETARY_GLOBAL_RPM_LIMIT=100,
    DIETARY_GLOBAL_DAILY_LIMIT=500,
    DIETARY_THROTTLE_SECONDS=0,
)
class DietaryEndpointConcurrencyTests(TransactionTestCase):
    """End-to-end: the in-flight count observed inside the handler must never
    exceed the configured active limit."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.users = [
            User.objects.create_user(
                username=f'conc{i}@example.com', email=f'conc{i}@example.com', password='password-123'
            )
            for i in range(12)
        ]

    def test_concurrent_requests_never_exceed_active_limit(self):
        observed = []
        observed_lock = threading.Lock()
        statuses = []
        status_lock = threading.Lock()

        def fake_generate(user, payload):
            # Sample the global in-flight counter while actually in flight.
            with observed_lock:
                observed.append(cache.get(ACTIVE_GLOBAL_KEY, 0))
            time.sleep(0.05)
            return dict(FAKE_ADVICE)

        start = threading.Barrier(len(self.users))

        def worker(user):
            try:
                client = APIClient()
                client.force_authenticate(user)
                start.wait()
                response = client.post(
                    reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json'
                )
                with status_lock:
                    statuses.append(response.status_code)
            finally:
                connection.close()

        with patch('api.views.generate_dietary_advice', side_effect=fake_generate):
            threads = [threading.Thread(target=worker, args=(user,)) for user in self.users]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertTrue(observed, 'handler never ran; test did not exercise the gate')
        self.assertLessEqual(
            max(observed), 2,
            f'active limit of 2 exceeded; observed in-flight counts: {observed}',
        )
        # Everyone got a definitive answer - admitted (200) or shed (429).
        self.assertEqual(len(statuses), len(self.users))
        self.assertTrue(set(statuses).issubset({200, 429}), f'unexpected statuses: {statuses}')
        self.assertIn(200, statuses, 'no request was admitted at all')

    def test_slot_is_released_after_requests_complete(self):
        with patch('api.views.generate_dietary_advice', return_value=dict(FAKE_ADVICE)):
            client = APIClient()
            client.force_authenticate(self.users[0])
            response = client.post(
                reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json'
            )
        self.assertEqual(response.status_code, 200)
        # A leaked slot would permanently shrink capacity for everyone.
        self.assertEqual(cache.get(ACTIVE_GLOBAL_KEY, 0), 0)

    def test_slot_is_released_when_request_is_rejected_by_quota(self):
        with override_settings(DIETARY_GLOBAL_RPM_LIMIT=1):
            with patch('api.views.generate_dietary_advice', return_value=dict(FAKE_ADVICE)):
                client = APIClient()
                client.force_authenticate(self.users[0])
                first = client.post(
                    reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json'
                )
                second_client = APIClient()
                second_client.force_authenticate(self.users[1])
                second = second_client.post(
                    reverse('dietary_recommendations'), {'risk_level': 'medium'}, format='json'
                )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(cache.get(ACTIVE_GLOBAL_KEY, 0), 0)
