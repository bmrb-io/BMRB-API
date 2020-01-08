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


class MatchFormats(enum.Enum):
    exact = "exact"
    author = "author"
    blast = "blast"
    assembly = "assembly"


class PdbBmrbMap(Schema):
    match_type = CustomErrorEnum(MatchFormats)
    pass


class BmrbPdbMap(Schema):
    match_type = CustomErrorEnum(MatchFormats)
    pass


class Uniprot(Schema):
    class Formats(enum.Enum):
        json = "json"
        hupo_psi_id = "hupo-psi-id"

    format = CustomErrorEnum(Formats)


class GetPdbIdsFromBmrbId(Schema):
    pass
