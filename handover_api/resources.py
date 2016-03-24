from flask_restful import Resource, abort
from models import HandoverModel
from schemas import HandoverSchema

from flask import jsonify


class HandoverApiResource(Resource):
    def not_found(self, name, id):
        abort(404, message="{} {} doesn't exist".format(name, id))


class HandoverList(HandoverApiResource):
    def __init__(self):
        self.schema = HandoverSchema(many=True)
    def get(self):
        handovers = HandoverModel.query.all()
        result = self.schema.dump(handovers)
        return jsonify(results=result.data)


class Handover(HandoverApiResource):
    def __init__(self):
        self.schema = HandoverSchema(many=False)
    def get(self, id):
        handover = HandoverModel.query.get(id)
        if handover is None:
            self.not_found('handover', id)
        result = self.schema.dump(handover)
        return jsonify(result.data)


class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

