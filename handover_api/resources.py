from flask_restful import Resource, abort
from models import HandoverModel, db
from schemas import HandoverSchema

from flask import jsonify, request


class HandoverApiResource(Resource):
    def fail(self, action, name, error):
        abort(400, message="Unable to {} {}: {}".format(action, name, error))


class HandoverList(HandoverApiResource):
    def __init__(self):
        self.schema = HandoverSchema(many=True)

    def get(self):
        handovers = HandoverModel.query.all()
        result, error = self.schema.dump(handovers)
        return jsonify(results=result)

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
        handover = HandoverModel.query.filter_by(id=id).first_or_404()
        result = self.schema.dump(handover)
        return jsonify(result.data)

    def put(self, id):
        deserialized, errors = self.schema.load(request.json, many=False)
        if errors:
            return jsonify(errors), 422

        handover = HandoverModel.query.filter_by(id=id).first_or_404()
        for k, v in request.json.iteritems():
            setattr(handover, k, v)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('update', 'handover', e)
        response_data = self.schema.dump(handover, many=False)
        return response_data.data, 200

    def delete(self, id):
        handover = HandoverModel.query.filter_by(id=id).first_or_404()
        db.session.delete(handover)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('delete', 'handover', e)
        return {}, 200

class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

