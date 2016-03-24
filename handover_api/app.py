from flask import Flask
from flask_restful import Api
from resources import Handover, HandoverList, Draft
from models import db

app = Flask(__name__)
api = Api(app)

api.add_resource(HandoverList, '/handovers/')
api.add_resource(Handover, '/handovers/<string:id>')

api.add_resource(Draft, '/drafts', '/drafts/<string:id>')

def main(debug=True):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
    db.create_all()
    app.run(debug=debug)

if __name__ == "__main__":
    main()
