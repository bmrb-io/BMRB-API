import enum

from marshmallow import fields, Schema

from bmrbapi.schemas.default import DatabaseSchema, CustomErrorEnum

__all__ = ['GetBmrbDataFromPdbId', 'MultipleShiftSearch', 'GetChemicalShifts', 'GetAllValuesForTag', 'GetIdFromSearch',
           'GetBmrbIdsFromPdbId', 'GetPdbIdsFromBmrbId', 'FastaSearch', 'Instant', 'Select', 'RerouteInstantInternal']


class GetBmrbDataFromPdbId(Schema):
    pass


class MultipleShiftSearch(DatabaseSchema):
    nthresh = fields.Float()
    cthresh = fields.Float()
    hthresh = fields.Float()
    s = fields.Float(multiple=True)
    shift = fields.Float(multiple=True)


class GetChemicalShifts(DatabaseSchema):
    shift = fields.Float(multiple=True)
    threshold = fields.Float()
    atom_type = fields.String()
    atom_id = fields.String(multiple=True)
    comp_id = fields.String(multiple=True)
    conditions = fields.Bool()


class GetAllValuesForTag(DatabaseSchema):
    pass


class GetIdFromSearch(DatabaseSchema):
    pass


class GetBmrbIdsFromPdbId(Schema):
    pass


class GetPdbIdsFromBmrbId(Schema):
    pass


class FastaSearch(Schema):
    class ResidueTypes(enum.Enum):
        polymer = "polymer"
        rna = "rna"
        dna = "dna"

    type = CustomErrorEnum(ResidueTypes)
    e_val = fields.String()


class Instant(DatabaseSchema):
    term = fields.String(required=True)


class RerouteInstantInternal(Instant):
    pass


class Select(Schema):
    pass
