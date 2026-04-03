from marshmallow import fields, Schema

__all__ = ['MolprobityOneline', 'MolprobityResidue']


class MolprobityOneline(Schema):
    pass


class MolprobityResidue(Schema):
    """ A MolProbity residue specific search"""

    r = fields.String(metadata={'multiple': True})
