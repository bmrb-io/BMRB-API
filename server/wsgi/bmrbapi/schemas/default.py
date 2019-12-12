import enum

from marshmallow import Schema
from marshmallow_enum import EnumField

__all__ = ['DatabaseSchema', 'CustomErrorEnum']


class CustomErrorEnum(EnumField):
    def __init__(self, enum_object):
        super().__init__(enum_object, by_value=True,
                         error="Invalid value provided. Please select from [{values}]")


class DatabaseSchema(Schema):
    """ A schema that checks the database argument, and nothing else. """

    class Databases(enum.Enum):
        macromolecules = "macromolecules"
        metabolomics = "metabolomics"
        chemcomps = "chemcomps"
        combined = "combined"

    database = CustomErrorEnum(Databases)
