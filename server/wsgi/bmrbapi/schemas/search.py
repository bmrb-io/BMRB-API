from marshmallow import fields

from bmrbapi.schemas.default import JSONResponseSchema

# TODO: Figure out how to do enumerations on the database fields


class MultipleShiftSearch(JSONResponseSchema):
    """ Search for entries based on chemical shifts. """

    # the 'required' argument ensures the field exists
    nthresh = fields.Float()
    cthresh = fields.Float()
    hthresh = fields.Float()
    s = fields.Float(multiple=True)
    shift = fields.Float(multiple=True)
    database = fields.String()


class GetChemicalShifts(JSONResponseSchema):
    """ All chemical shifts, filtered. """

    shift = fields.Float(multiple=True)
    threshold = fields.Float()
    atom_type = fields.String()
    atom_id = fields.String(multiple=True)
    comp_id = fields.String(multiple=True)
    conditions = fields.Bool()
    database = fields.String()
