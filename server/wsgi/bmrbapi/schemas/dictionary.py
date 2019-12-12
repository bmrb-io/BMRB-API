from marshmallow import fields

from bmrbapi.schemas.default import JSONResponseSchema

__all__ = ['GetEnumerations', 'ReturnSchema']


class GetEnumerations(JSONResponseSchema):
    term = fields.String()


class ReturnSchema(JSONResponseSchema):
    pass
