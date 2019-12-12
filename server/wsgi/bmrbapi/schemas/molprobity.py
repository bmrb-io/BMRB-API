from marshmallow import fields

from bmrbapi.schemas.default import JSONResponseSchema

__all__ = ['MolprobityResidue']


class MolprobityResidue(JSONResponseSchema):
    """ A MolProbity residue specific search"""

    r = fields.String(multiple=True)
