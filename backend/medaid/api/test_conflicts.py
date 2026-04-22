import threading
import time
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction, connection
from .models import UserProfile

User = get_user_model()

class UserProfileConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_conflict', password='password123')
        self.profile = UserProfile.objects.create(user=self.user)

    def test_concurrent_profile_updates(self):
        """
        Simulates concurrent modifications to a UserProfile to test select_for_update().
        """
        errors = []

        def worker1():
            try:
                # Close existing connection to force a new one for this thread
                connection.close()
                with transaction.atomic():
                    profile = UserProfile.objects.select_for_update().get(id=self.profile.id)
                    profile.city = "New York"
                    time.sleep(0.5)  # Hold the lock
                    profile.save()
            except Exception as e:
                errors.append(("worker1", e))
            finally:
                connection.close()

        def worker2():
            try:
                connection.close()
                # Wait a bit so worker1 acquires the lock first
                time.sleep(0.1)
                with transaction.atomic():
                    # This should block until worker1 completes because of select_for_update()
                    profile = UserProfile.objects.select_for_update().get(id=self.profile.id)
                    # If select_for_update is working properly, worker1's changes are already saved.
                    # We'll just overwrite an independent field.
                    profile.gender = "F"
                    profile.save()
            except Exception as e:
                errors.append(("worker2", e))
            finally:
                connection.close()

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent updates: {errors}")

        # Verify both changes persisted
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.city, "New York", "Worker 1 update failed")
        self.assertEqual(self.profile.gender, "F", "Worker 2 update failed")

