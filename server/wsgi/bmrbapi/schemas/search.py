import enum

from marshmallow import fields
from marshmallow_enum import EnumField

from bmrbapi.schemas.default import JSONResponseSchema, DatabaseSchema

__all__ = ['GetBmrbDataFromPdbId', 'MultipleShiftSearch', 'GetChemicalShifts', 'GetAllValuesForTag', 'GetIdFromSearch',
           'GetBmrbIdsFromPdbId', 'GetPdbIdsFromBmrbId', 'FastaSearch', 'Instant', 'Select']


class GetBmrbDataFromPdbId(JSONResponseSchema):
    pass


class MultipleShiftSearch(DatabaseSchema, JSONResponseSchema):
    nthresh = fields.Float()
    cthresh = fields.Float()
    hthresh = fields.Float()
    s = fields.Float(multiple=True)
    shift = fields.Float(multiple=True)


class GetChemicalShifts(DatabaseSchema, JSONResponseSchema):
    shift = fields.Float(multiple=True)
    threshold = fields.Float()
    atom_type = fields.String()
    atom_id = fields.String(multiple=True)
    comp_id = fields.String(multiple=True)
    conditions = fields.Bool()


class GetAllValuesForTag(DatabaseSchema, JSONResponseSchema):
    pass


class GetIdFromSearch(DatabaseSchema, JSONResponseSchema):
    pass


class GetBmrbIdsFromPdbId(JSONResponseSchema):
    pass


class GetPdbIdsFromBmrbId(JSONResponseSchema):
    pass


# TODO: More validation in endpoint should be moved here
class FastaSearch(JSONResponseSchema):
    a_type = fields.String()
    e_val = fields.String()


class Instant(DatabaseSchema, JSONResponseSchema):
    term = fields.String(required=True)


class Select(JSONResponseSchema):
    pass
