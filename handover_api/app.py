from flask import Flask
from flask_restful import Api
from resources.handover import Handover
from resources.draft import Draft

app = Flask(__name__)
api = Api(app)

api.add_resource(Handover, '/handovers', '/handovers/<string:id>')
api.add_resource(Draft, '/drafts', '/drafts/<string:id>')

def main(debug=False):
    app.run(debug=debug)

if __name__ == "__main__":
    main()
