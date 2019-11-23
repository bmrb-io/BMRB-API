from marshmallow import Schema, fields


class JSONResponseSchema(Schema):
    """ Always allow the special options that can apply to all methods. """

    pretty_print = fields.Bool()
