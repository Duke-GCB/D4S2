from flask import Flask
from flask_restful import Api
from resources import Handover, HandoverList, Draft
from models import db


def create_app(database_uri):
    app = Flask(__name__)
    api = Api(app)

    api.add_resource(HandoverList, '/handovers/')
    api.add_resource(Handover, '/handovers/<string:id>')

    api.add_resource(Draft, '/drafts', '/drafts/<string:id>')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    db.init_app(app)
    return app



def main(debug=True):
    app = create_app('sqlite:////tmp/test.db')
    with app.app_context():
        db.create_all()
    app.run(debug=debug)

if __name__ == "__main__":
    main()
