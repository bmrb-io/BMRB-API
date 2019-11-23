from marshmallow import fields

from bmrbapi.schemas.default import JSONResponseSchema, DatabaseSchema


# TODO: Figure out how to do enumerations on the database fields


class GetBmrbDataFromPdbId(JSONResponseSchema):
    pass


class MultipleShiftSearch(JSONResponseSchema):
    nthresh = fields.Float()
    cthresh = fields.Float()
    hthresh = fields.Float()
    s = fields.Float(multiple=True)
    shift = fields.Float(multiple=True)
    database = fields.String()


class GetChemicalShifts(JSONResponseSchema):
    shift = fields.Float(multiple=True)
    threshold = fields.Float()
    atom_type = fields.String()
    atom_id = fields.String(multiple=True)
    comp_id = fields.String(multiple=True)
    conditions = fields.Bool()
    database = fields.String()


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


class Instant(JSONResponseSchema):
    term = fields.String(required=True)
    database = fields.String()


class Select(JSONResponseSchema):
    pass
