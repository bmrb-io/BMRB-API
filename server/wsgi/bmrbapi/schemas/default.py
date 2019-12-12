import enum

from marshmallow import Schema, fields
from marshmallow_enum import EnumField

__all__ = ['JSONResponseSchema', 'DatabaseSchema']


class JSONResponseSchema(Schema):
    """ A schema for routes that return JSON """

    pretty_print = fields.Bool()


class Databases(enum.Enum):
    macromolecules = "macromolecules"
    metabolomics = "metabolomics"
    chemcomps = "chemcomps"
    combined = "combined"


class DatabaseSchema(Schema):
    """ A schema that checks the database argument, and nothing else. """

    database = EnumField(Databases, by_value=True)
