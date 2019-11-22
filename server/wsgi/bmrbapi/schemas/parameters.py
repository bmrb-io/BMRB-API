from marshmallow import fields

from bmrbapi.schemas.default import APISchema

class ChemicalShiftSearchSchema(APISchema):
    """ A chemical shift search """

    # the 'required' argument ensures the field exists
    nthresh = fields.Float()
    cthresh = fields.Float()
    hthresh = fields.Float()
    s = fields.Float(multiple=True)
    shift = fields.Float(multiple=True)
