import enum

from marshmallow import Schema, fields

__all__ = ['DatabaseSchema', 'CustomErrorEnum']


class CustomErrorEnum(fields.Enum):
    def __init__(self, enum_object):
        super().__init__(enum_object, by_value=True,
                         error_messages={'unknown': 'Invalid value provided. Please select from [{choices}]'})


class DatabaseSchema(Schema):
    """ A schema that checks the database argument, and nothing else. """

    class Databases(enum.Enum):
        macromolecules = "macromolecules"
        metabolomics = "metabolomics"
        chemcomps = "chemcomps"
        combined = "combined"

    database = CustomErrorEnum(Databases)
