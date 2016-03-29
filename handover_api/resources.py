from flask_restful import Resource, abort
from models import HandoverModel, UserModel, DraftModel, db
from schemas import HandoverSchema, UserSchema, DraftSchema

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


class HandoverBase(object):
    def __init__(self, many):
        self.schema = HandoverSchema(many=many)
        self.name = 'handover'
        self.model = HandoverModel


class HandoverList(HandoverBase, ListResource):
    def __init__(self):
        super(HandoverList, self).__init__(True)


class Handover(HandoverBase, SingleResource):
    def __init__(self):
        super(Handover, self).__init__(False)


class UserBase(object):
    def __init__(self, many):
        self.schema = UserSchema(many=many)
        self.name = 'user'
        self.model = UserModel


class UserList(UserBase, ListResource):
    def __init__(self):
        super(UserList, self).__init__(True)


class User(UserBase, SingleResource):
    def __init__(self):
        super(User, self).__init__(False)


class DraftBase(object):
    def __init__(self, many):
        self.schema = DraftSchema(many=many)
        self.name = 'draft'
        self.model = DraftModel


class Draft(DraftBase, SingleResource):
    def __init__(self):
        super(Draft, self).__init__(False)


class DraftList(DraftBase, ListResource):
    def __init__(self):
        super(DraftList, self).__init__(True)
