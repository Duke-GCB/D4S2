from flask_restful import Resource, abort
from models import HandoverModel, db
from schemas import HandoverSchema

from flask import jsonify, request


class ApiResource(Resource):
    def fail(self, action, name, error):
        abort(400, message="Unable to {} {}: {}".format(action, name, error))


class ListResource(ApiResource):

    def get(self):
        objects = self.model.query.all()
        result, error = self.schema.dump(objects)
        return jsonify(results=result)

    def post(self):
        deserialized, errors = self.schema.load(request.json, many=False)
        if errors:
            return jsonify(errors), 422
        db.session.add(deserialized)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('create', self.name, e)
        response_data = self.schema.dump(deserialized, many=False)
        return response_data.data, 201

class SingleResource(ApiResource):

    def get(self, id):
        object = self.model.query.filter_by(id=id).first_or_404()
        result = self.schema.dump(object)
        return jsonify(result.data)

    def put(self, id):
        deserialized, errors = self.schema.load(request.json, many=False)
        if errors:
            return jsonify(errors), 422

        object = self.model.query.filter_by(id=id).first_or_404()
        for k, v in request.json.iteritems():
            setattr(object, k, v)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('update', self.name, e)
        response_data = self.schema.dump(object, many=False)
        return response_data.data, 200

    def delete(self, id):
        object = self.model.query.filter_by(id=id).first_or_404()
        db.session.delete(object)
        try:
            db.session.commit()
        except Exception as e:
            self.fail('delete', self.name, e)
        return {}, 200


class HandoverList(ListResource):
    def __init__(self):
        self.schema = HandoverSchema(many=True)
        self.name = 'handover'
        self.model = HandoverModel


class Handover(SingleResource):
    def __init__(self):
        self.schema = HandoverSchema(many=False)
        self.name = 'handover'
        self.model = HandoverModel


class Draft(Resource):
    def get(self):
        return [{'draft' : 1024}]

