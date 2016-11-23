from django.contrib.auth import get_user_model


class BaseBackend(object):

    def authenticate(self):
        """
        Default implementation does nothing, must be overridden
        :return:
        """
        return None

    def get_user_details_map(self):
        """
        Map of django user model keys to the DukeDS user keys
        :return: Default mapping of valid django keys
        """
        return {
            'username': 'username',
            'first_name':'first_name',
            'last_name':'last_name',
            'email':'email',
        }

    def map_user_details(self, details):
        """
        Maps incoming user details from an external data source (e.g OIDC, DukeDS)
         into a dictionary with django-user suitable keys
        :param details: dict containing keys e.g. sub, given_name, family_name, email
        :return: dict containing only keys valid for django user model (e.g.
        """
        mapped = dict()
        for k, v in self.get_user_details_map().items():
            if v in details:
                mapped[k] = details[v]
        return mapped

    def save_user(self, raw_user_dict, update=True):
        """
        Creates or updates a user object from the provided dictionary
        :param raw_user_dict: dictionary of user details from the external provider
        :param update: True to update existing users with incoming data
        :return:
        """
        user_dict = self.map_user_details(raw_user_dict)
        if 'username' not in user_dict:
            return None
        user, created = get_user_model().objects.get_or_create(username=user_dict.get('username'))
        # Update the keys
        if created or update:
            for attr, value in user_dict.items():
                if value:
                    setattr(user, attr, value)
            user.save()
        return user

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
