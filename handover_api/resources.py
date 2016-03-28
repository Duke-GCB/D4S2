from flask_restful import Resource, abort
from models import HandoverModel, db
from schemas import HandoverSchema

from flask import jsonify, request


class HandoverApiResource(Resource):
    def not_found(self, name, id):
        abort(404, message="{} {} doesn't exist".format(name, id))

    def fail(self, action, name, error):
        abort(400, message="Unable to {} {}: {}".format(action, name, error))

class HandoverList(HandoverApiResource):
    def __init__(self):
        self.schema = HandoverSchema(many=True)

    def get(self):
        handovers = HandoverModel.query.all()
        result = self.schema.dump(handovers)
        return jsonify(results=result.data)

    def post(self):
        payload = self.schema.load(request.json, many=False)
        h = payload.data
        db.session.add(h)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('create', 'handover', e)
        response_data = self.schema.dump(h, many=False)
        return response_data.data, 201


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

