import enum

from marshmallow import Schema

from bmrbapi.schemas.default import CustomErrorEnum

__all__ = ['UniprotMappings', 'UniprotBmrbMap', 'BmrbUniprotMap', 'PdbBmrbMap', 'BmrbPdbMap',
           'Uniprot', 'GetPdbIdsFromBmrbId']


class UniprotMappings(Schema):
    pass


class UniprotBmrbMap(Schema):
    pass


class BmrbUniprotMap(Schema):
    pass


class PdbBmrbMap(Schema):
    pass


class BmrbPdbMap(Schema):
    pass


class Formats(enum.Enum):
    json = "json"
    hupo_psi_id = "hupo-psi-id"


class Uniprot(Schema):
    format = CustomErrorEnum(Formats)


class GetPdbIdsFromBmrbId(Schema):
    pass
