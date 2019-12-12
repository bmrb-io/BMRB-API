import enum

from marshmallow import Schema
from marshmallow_enum import EnumField

__all__ = ['DatabaseSchema']


class Databases(enum.Enum):
    macromolecules = "macromolecules"
    metabolomics = "metabolomics"
    chemcomps = "chemcomps"
    combined = "combined"


class DatabaseSchema(Schema):
    """ A schema that checks the database argument, and nothing else. """

    database = EnumField(Databases, by_value=True)
