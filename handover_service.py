from flask import Flask
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

class Handover(Resource):
    def get(self):
        return [{'handover' : 42}]

class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

api.add_resource(Handover, '/api/v1/handovers')
api.add_resource(Draft, '/api/v1/drafts')

if __name__ == "__main__":
    app.run(debug=True)
