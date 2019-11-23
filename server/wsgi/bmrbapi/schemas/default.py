from marshmallow import Schema, fields


class APISchema(Schema):
    """ Always allow the special options that can apply to all methods. """

    pretty_print = fields.Bool()
    # TODO: Figure out how to check enumerations in marshmallow
    database = fields.String()
