
class DDSDeliveryPreview(object):
    def __init__(self, from_user_id, to_user_id, project_id, user_message):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.project_id = project_id
        self.user_message = user_message
        self.delivery_email_text = ''
