from flask_restful import Resource

class Handover(Resource):
    def get(self):
        return [{'handover' : 42}]

