from marshmallow import Schema, fields

__all__ = ['JSONResponseSchema', 'DatabaseSchema']


class JSONResponseSchema(Schema):
    """ A schema for routes that return JSON """

    pretty_print = fields.Bool()


# TODO: Figure out how to do enumerations on the database fields
class DatabaseSchema(Schema):
    """ A schema that checks the database argument, and nothing else. """

    database = fields.String()
