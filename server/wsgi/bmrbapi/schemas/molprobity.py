from marshmallow import fields, Schema

__all__ = ['MolprobityResidue']


class MolprobityResidue(Schema):
    """ A MolProbity residue specific search"""

    r = fields.String(multiple=True)
