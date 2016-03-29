from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dds_id = db.Column(db.String(36), unique=True) # UUID
    api_key = db.Column(db.String(32)) # API Key

    def __init__(self, dds_id, api_key):
        self.dds_id = dds_id
        self.api_key = api_key

    def __repr__(self):
        return '<DDS user id %r>' % self.dds_id


class HandoverModel(db.Model):
    states = ['Initiated','Notified','Accepted','Rejected']
    id = db.Column(db.Integer, primary_key=True)
    # Projects will be copies so may only be handed over once
    project_id = db.Column(db.String(36), unique=True)
    from_user_id = db.Column(db.String(36))
    to_user_id = db.Column(db.String(36))
    state = db.Column(db.Enum(*states))
    
    def __init__(self, project_id, from_user_id, to_user_id):
        self.project_id = project_id
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.state = self.states[0]

class DraftModel(HandoverModel):
    states = ['Notified']
