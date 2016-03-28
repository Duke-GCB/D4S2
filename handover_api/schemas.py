from marshmallow import Schema, fields, post_load
from models import HandoverModel, UserModel, DraftModel
class HandoverSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Str()
    from_user_id = fields.Str()
    to_user_id = fields.Str()
    state = fields.Str()

    @post_load
    def make_handover(self, data):
        return HandoverModel(**data)

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    dds_id = fields.Str()
    api_key = fields.Str()

    @post_load
    def make_user(self, data):
        return UserModel(**data)

class DraftSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Str()
    from_user_id = fields.Str()
    to_user_id = fields.Str()
    state = fields.Str()

    @post_load
    def make_draft(self, data):
        return DraftModel(**data)