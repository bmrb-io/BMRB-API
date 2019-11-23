from functools import wraps

from flask import request

from bmrbapi.exceptions import RequestException
from bmrbapi.utils.querymod import check_local_ip


def require_content_type_json(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            raise RequestException("Please submit form data as JSON using Content-Type: application/json", 400)
        return function(*args, **kwargs)

    return wrapper


def require_local(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not check_local_ip():
            raise RequestException('Unauthorized', 401)
        return function(*args, **kwargs)

    return wrapper


def validate_schema(function, schema):
    @wraps(function)
    def wrapper(*args, **kwargs):
        errors = schema().validate(request.args)
        if errors:
            raise RequestException(errors)
        return function(*args, **kwargs)

    return wrapper
