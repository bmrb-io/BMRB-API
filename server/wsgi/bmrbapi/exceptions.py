class APIException(Exception):
    pass

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


class RequestError(APIException):
    """ Something is wrong with the request. """
    status_code = 400


class ServerError(Exception):
    """ Something is wrong with the server. """
    status_code = 500
