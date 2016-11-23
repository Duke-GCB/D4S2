from django.contrib.auth import get_user_model


class BaseBackend(object):

    def authenticate(self):
        """
        Default implementation does nothing, must be overridden
        :return:
        """
        return None

    def save_user(self, user_dict):
        """
        Creates or updates a user object from the provided dictionary
        :param user_dict: dictionary of user details - requires 'username'
        :return:
        """
        if 'username' not in user_dict:
            return None
        user, created = get_user_model().objects.get_or_create(username=user_dict.get('username'))
        # Update the keys
        for attr, value in user_dict.items():
            setattr(user, attr, value)
        user.save()
        return user

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
