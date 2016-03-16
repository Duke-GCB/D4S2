from models import db
db.create_all()

from models import HandoverModel
h = HandoverModel('abc','dan','john')
db.session.add(h)
db.session.commit()
