
class DDSDeliveryPreview(object):
    """
    A class to represent a delivery preview, without persistence.
    Has many of the same properties as a Delivery, and can be provided to the email generation code
    """
    def __init__(self, from_user_id, to_user_id, project_id, transfer_id, user_message):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.project_id = project_id
        self.transfer_id = transfer_id
        self.user_message = user_message
        self.delivery_email_text = ''
        self.email_template_set = None
