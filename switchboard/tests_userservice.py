from django.test import TestCase
from django.contrib.auth.models import User as django_user
from switchboard.userservice import create_email_from_netid, get_netid_from_user, get_user_for_netid, \
    get_users_for_query, _get_json_response
from rest_framework.exceptions import NotFound
from mock import Mock, patch


class UserServiceFunctions(TestCase):
    def test_create_email_from_netid(self):
        # When not setup return None for email
        with self.settings(USERNAME_EMAIL_HOST=None):
            self.assertEqual(create_email_from_netid("joe"), None)
        # When properly setup return full email
        with self.settings(USERNAME_EMAIL_HOST="sample.com"):
            self.assertEqual(create_email_from_netid("joe"), "joe@sample.com")

    def test_get_netid_from_user(self):
        user = Mock(username="joe@sample.com")
        self.assertEqual(get_netid_from_user(user), "joe")

    @patch("switchboard.userservice._get_json_response")
    def test_get_user_for_netid_from_db(self, mock_get_json_response):
        user = django_user.objects.create_user(username='joe@sample.com', password='secret', first_name="Joe",
                                               last_name="Smith", email="joe.smith@sample.com")
        mock_get_json_response.return_value = []
        with self.settings(DIRECTORY_SERVICE_URL="https://sample.com", USERNAME_EMAIL_HOST="sample.com"):
            user = get_user_for_netid("joe")
        self.assertEqual(user.id, "joe")
        self.assertEqual(user.username, "joe")
        self.assertEqual(user.full_name, "Joe Smith")
        self.assertEqual(user.first_name, "Joe")
        self.assertEqual(user.last_name, "Smith")
        self.assertEqual(user.email, "joe.smith@sample.com")

    @patch("switchboard.userservice._get_json_response")
    def test_get_user_for_netid_not_found(self, mock_get_json_response):
        mock_get_json_response.return_value = []
        with self.settings(DIRECTORY_SERVICE_URL="https://sample.com"):
            with self.assertRaises(NotFound):
                get_user_for_netid("joe")
        mock_get_json_response.assert_called_with("https://sample.com/ldap/people/netid/joe")

    @patch("switchboard.userservice._get_json_response")
    def test_get_user_for_netid_good(self, mock_get_json_response):
        mock_get_json_response.return_value = [{
            "givenName": "Joe",
            "sn": "Smith",
            "netid": "joe",
            "display_name": "Joe Smith",
            "emails": ["joe.smith@sample.com"]
        }]
        with self.settings(DIRECTORY_SERVICE_URL="https://sample.com"):
            user = get_user_for_netid("joe")
            self.assertEqual(user.id, "joe")
            self.assertEqual(user.username, "joe")
            self.assertEqual(user.full_name, "Joe Smith")
            self.assertEqual(user.first_name, "Joe")
            self.assertEqual(user.last_name, "Smith")
            self.assertEqual(user.email, "joe.smith@sample.com")
        mock_get_json_response.assert_called_with("https://sample.com/ldap/people/netid/joe")

    @patch("switchboard.userservice._get_json_response")
    def test_get_users_for_query(self, mock_get_json_response):
        mock_get_json_response.return_value = [{
            "givenName": "Joe",
            "sn": "Smith",
            "netid": "joe",
            "display_name": "Joe Smith"
        }, {
            # user without netid that should be filtered out
        }]
        with self.settings(DIRECTORY_SERVICE_URL="https://sample.com", USERNAME_EMAIL_HOST="sample.com"):
            results = get_users_for_query("joe")
            self.assertEqual(len(results), 1)
            user = results[0]
            self.assertEqual(user.id, "joe")
            self.assertEqual(user.username, "joe")
            self.assertEqual(user.full_name, "Joe Smith")
            self.assertEqual(user.first_name, "Joe")
            self.assertEqual(user.last_name, "Smith")
            self.assertEqual(user.email, "joe@sample.com")
        mock_get_json_response.assert_called_with("https://sample.com/ldap/people", q="joe")

    @patch("switchboard.userservice.requests")
    def test__get_json_response(self, mock_requests):
        mock_requests.get.return_value.json.return_value = {"val":123}
        with self.settings(DIRECTORY_SERVICE_TOKEN="secret"):
            response = _get_json_response("someurl", q="testing")
            self.assertEqual(response, {"val":123})
        mock_requests.get.assert_called_with('someurl', data={'access_token': 'secret', 'q': 'testing'})
