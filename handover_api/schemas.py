from marshmallow import Schema, fields

class HandoverSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Str()
    from_user_id = fields.Str()
    to_user_id = fields.Str()
    state = fields.Str()

