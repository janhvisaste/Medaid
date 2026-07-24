"""The reference-compat endpoint must not be reachable unless explicitly enabled.

/api/reference-compat/assess/ reproduces the upstream Streamlit reference's
triage behaviour verbatim, which means it carries none of the safety work on
the primary paths: no emergency short-circuit, a 14-keyword emergency list with
no negation handling, no degraded-response risk floor, no confidence
calibration, no condition-name validation.

Nothing calls it (no frontend client reference, no gateway config), so it is
unrouted by default. These tests exist so that re-routing it becomes a
deliberate act rather than an accident.
"""
from importlib import reload

from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from medaid import urls as project_urls


class ReferenceCompatRoutingTests(SimpleTestCase):
    """Routing is decided at URLConf import time, so each case reloads the
    module under the setting it is asserting about."""

    def tearDown(self):
        # Leave the process's URLConf matching the real default.
        reload(project_urls)

    def _reload_urlconf(self):
        reload(project_urls)
        self.addCleanup(self.clear_url_caches)

    @staticmethod
    def clear_url_caches():
        from django.urls import clear_url_caches
        clear_url_caches()

    def test_disabled_by_default(self):
        from django.conf import settings
        self.assertFalse(
            settings.ENABLE_REFERENCE_COMPAT_API,
            'reference-compat must default to OFF - it is not patient-safe',
        )

    @override_settings(ENABLE_REFERENCE_COMPAT_API=False)
    def test_route_absent_when_disabled(self):
        self._reload_urlconf()
        with override_settings(ROOT_URLCONF=project_urls):
            with self.assertRaises(Resolver404):
                resolve('/api/reference-compat/assess/')

    @override_settings(ENABLE_REFERENCE_COMPAT_API=False)
    def test_name_not_reversible_when_disabled(self):
        self._reload_urlconf()
        with override_settings(ROOT_URLCONF=project_urls):
            with self.assertRaises(NoReverseMatch):
                reverse('reference_compat_assess')

    @override_settings(ENABLE_REFERENCE_COMPAT_API=True)
    def test_route_present_when_explicitly_enabled(self):
        self._reload_urlconf()
        with override_settings(ROOT_URLCONF=project_urls):
            match = resolve('/api/reference-compat/assess/')
            self.assertEqual(match.url_name, 'reference_compat_assess')

    @override_settings(ENABLE_REFERENCE_COMPAT_API=False)
    def test_primary_triage_route_is_unaffected(self):
        # The gate must not disturb the routes that actually serve patients.
        self._reload_urlconf()
        with override_settings(ROOT_URLCONF=project_urls):
            self.assertEqual(
                resolve('/api/triage/assess/').url_name, 'assess_symptoms'
            )
