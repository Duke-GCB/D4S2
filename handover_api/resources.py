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
        deserialized, errors = self.schema.load(request.json, many=False)
        if errors:
            return jsonify(errors), 422
        db.session.add(deserialized)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('create', 'handover', e)
        response_data = self.schema.dump(deserialized, many=False)
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

    def put(self, id):
        deserialized, errors = self.schema.load(request.json, many=False)
        if errors:
            return jsonify(errors), 422

        existing = HandoverModel.query.get(id)
        for k, v in request.json.iteritems():
            setattr(existing, k, v)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('update', 'handover', e)
        response_data = self.schema.dump(existing, many=False)
        return response_data.data, 200


class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

