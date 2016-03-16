from flask_restful import Resource

class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

