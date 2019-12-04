from flask import request

from bmrbapi.exceptions import ServerException, RequestException
from bmrbapi.utils.configuration import configuration
# Keep the schema imports separate
from bmrbapi.schemas.default import *
from bmrbapi.schemas.internal import *
from bmrbapi.schemas.molprobity import *
from bmrbapi.schemas.search import *


def validate_parameters():
    """ Validate the parameters for the request. """

    if "." in request.endpoint:
        endpoint = request.endpoint.split('.')[1].title().replace("_", "")
    else:
        endpoint = request.endpoint.title().replace("_", "")

    #  This is either very clever or very stupid
    schema = globals().get(endpoint, Schema)
    # TODO: Build a scanner module to show when schemas are missing
    if configuration['debug'] and schema is Schema:
        raise ServerException('Function without validator defined: %s' % request.endpoint)
    errors = schema().validate(request.args)
    if errors:
        raise RequestException(errors)


class CatchAll(JSONResponseSchema):
    pass


class GetStatus(JSONResponseSchema):
    pass
