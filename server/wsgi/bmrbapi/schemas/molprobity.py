from marshmallow import fields

from bmrbapi.schemas.default import JSONResponseSchema


class MolprobityResidue(JSONResponseSchema):
    """ A MolProbity residue specific search"""

    r = fields.String(multiple=True)
