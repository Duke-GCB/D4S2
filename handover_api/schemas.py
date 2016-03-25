from marshmallow import Schema, fields, post_load
from models import HandoverModel
class HandoverSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Str()
    from_user_id = fields.Str()
    to_user_id = fields.Str()
    state = fields.Str()

    @post_load
    def make_handover(self, data):
        return HandoverModel(**data)