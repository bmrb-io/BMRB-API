from marshmallow import fields, Schema

__all__ = ['GetEnumerations', 'ReturnSchema']


class GetEnumerations(Schema):
    term = fields.String()


class ReturnSchema(Schema):
    pass
