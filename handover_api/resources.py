from flask_restful import Resource
from models import HandoverModel
from schemas import HandoverSchema

from flask import jsonify

class HandoverList(Resource):
    def __init__(self):
        self.schema = HandoverSchema(many=True)
    def get(self):
        handovers = HandoverModel.query.all()
        result = self.schema.dump(handovers)
        return jsonify(results=result.data)

class Handover(Resource):
    def __init__(self):
        self.schema = HandoverSchema(many=False)
    def get(self, id):
        handover = HandoverModel.query.get(id)
        result = self.schema.dump(handover)
        return jsonify(result.data)


class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

