from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import User, UserProfile


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_profile_and_returns_tokens(self):
        response = self.client.post(
            reverse('signup'),
            {
                'email': ' NewUser@Example.com ',
                'password': 'SafePassword123!',
                'confirm_password': 'SafePassword123!',
                'first_name': 'New',
                'last_name': 'User',
                'phone_number': '+919999999999',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['access'])
        self.assertTrue(response.data['refresh'])
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.phone_number, '+919999999999')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_login_accepts_email_case_variation_and_rejects_wrong_password(self):
        User.objects.create_user(
            username='patient@example.com',
            email='patient@example.com',
            password='SafePassword123!',
        )

        valid = self.client.post(
            reverse('login'),
            {'email': 'PATIENT@EXAMPLE.COM', 'password': 'SafePassword123!'},
            format='json',
        )
        invalid = self.client.post(
            reverse('login'),
            {'email': 'patient@example.com', 'password': 'wrong-password'},
            format='json',
        )

        self.assertEqual(valid.status_code, 200)
        self.assertTrue(valid.data['access'])
        self.assertTrue(UserProfile.objects.filter(user__email='patient@example.com').exists())
        self.assertEqual(invalid.status_code, 401)

    def test_logout_blacklists_refresh_token(self):
        user = User.objects.create_user(
            username='logout@example.com',
            email='logout@example.com',
            password='SafePassword123!',
        )
        login = self.client.post(
            reverse('login'),
            {'email': user.email, 'password': 'SafePassword123!'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        logout = self.client.post(
            reverse('logout'),
            {'refresh': login.data['refresh']},
            format='json',
        )
        refresh = self.client.post(
            reverse('token_refresh'),
            {'refresh': login.data['refresh']},
            format='json',
        )

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(refresh.status_code, 401)

    def test_script_frontend_origin_is_allowed_for_auth_preflight(self):
        response = self.client.options(
            reverse('login'),
            HTTP_ORIGIN='http://localhost:8000',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:8000')
