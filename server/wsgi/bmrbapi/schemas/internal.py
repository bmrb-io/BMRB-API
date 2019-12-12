from marshmallow import Schema

from bmrbapi.schemas.default import JSONResponseSchema

__all__ = ['FaviconInternal', 'RefreshUniprotInternal']


class FaviconInternal(Schema):
    pass


class RefreshUniprotInternal(JSONResponseSchema):
    pass
