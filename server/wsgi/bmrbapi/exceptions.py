from flask import jsonify


class APIException(Exception):

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """ Converts the payload to a dictionary."""
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

    def to_response(self):
        """ Returns a Flask Response object that can be
        returned in a view. """

        response = jsonify(self.to_dict())
        response.status_code = self.status_code
        return response


class RequestError(APIException):
    """ Something is wrong with the request. """
    status_code = 400


class ServerError(APIException):
    """ Something is wrong with the server. """
    status_code = 500
