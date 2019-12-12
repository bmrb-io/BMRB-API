import enum

from marshmallow_enum import EnumField

from bmrbapi.schemas.default import JSONResponseSchema

__all__ = ['UniprotMappings', 'UniprotBmrbMap', 'BmrbUniprotMap', 'PdbBmrbMap', 'BmrbPdbMap',
           'Uniprot', 'GetPdbIdsFromBmrbId']


class UniprotMappings(JSONResponseSchema):
    pass


class UniprotBmrbMap(JSONResponseSchema):
    pass


class BmrbUniprotMap(JSONResponseSchema):
    pass


class PdbBmrbMap(JSONResponseSchema):
    pass


class BmrbPdbMap(JSONResponseSchema):
    pass


class Formats(enum.Enum):
    json = "json"
    hupo_psi_id = "hupo-psi-id"


class Uniprot(JSONResponseSchema):
    format = EnumField(Formats, by_value=True)


class GetPdbIdsFromBmrbId(JSONResponseSchema):
    pass
