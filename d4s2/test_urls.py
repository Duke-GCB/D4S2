from django.test import TestCase
from django.urls import reverse


class UrlsTestCase(TestCase):
    def test_login(self):
        url = reverse('login')
        self.client.get(url)

    def test_logout(self):
        url = reverse('logout')
        self.client.get(url)

    def test_login_local(self):
        url = reverse('login-local')
        self.client.get(url)
