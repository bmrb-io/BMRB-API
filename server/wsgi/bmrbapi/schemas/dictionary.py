from marshmallow import fields, Schema

__all__ = ['GetEnumerations']


class GetEnumerations(Schema):
    term = fields.String()
