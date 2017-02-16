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

    @staticmethod
    def harmonize_dict(mapping, input_dict):
        """
        Sanitizes incoming data into a dictionary with keys valid for a given domain (e.g. Django user models)
        :param mapping: Dict containing the mapping of incoming to outgoing data.
        :param input_dict: dict of data to be harmonized
        :return: dict containing keys from mapping and values from input_dict
        """
        output_dict = dict()
        for k, v in mapping.items():
            if v in input_dict:
                output_dict[k] = input_dict[v]
        return output_dict

    def harmonize_user_details(self, details):
        """
        Harmonizes incoming details into a dictionary suitable for a django user model
        :param details: user details from an external provider
        :return: dict containing only keys valid for django user model
        """
        return self.harmonize_dict(self.get_user_details_map(), details)

    @staticmethod
    def update_model(model, attrs):
        """
        Updates a model object with the given attributes
        :param model: A model object
        :param attrs: A dictionary of attribute keys and values
        :return: the incoming model object, after updating and saving
        """
        for attr, value in attrs.items():
            if value:
                setattr(model, attr, value)
        model.save()
        return model

    def save_user(self, raw_user_dict, update=True):
        """
        Creates or updates a user object from the provided dictionary
        :param raw_user_dict: dictionary of user details from the external provider
        :param update: True to update existing users with incoming data
        :return:
        """
        user_dict = self.harmonize_user_details(raw_user_dict)
        if 'username' not in user_dict:
            return None
        user, created = get_user_model().objects.get_or_create(username=user_dict.get('username'))
        # Update the keys
        if created or update:
            user = self.update_model(user, user_dict)
        return user

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
