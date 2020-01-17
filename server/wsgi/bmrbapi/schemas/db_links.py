import enum

from marshmallow import Schema

from bmrbapi.schemas.default import CustomErrorEnum

__all__ = ['UniprotMappings', 'UniprotBmrbMap', 'BmrbUniprotMap', 'PdbBmrbMap', 'BmrbPdbMap',
           'Uniprot', 'GetPdbIdsFromBmrbId']


class ResponseFormats(enum.Enum):
    json = "json"
    text = "text"


class UniprotMappings(Schema):
    format = CustomErrorEnum(ResponseFormats)


class UniprotBmrbMap(Schema):
    format = CustomErrorEnum(ResponseFormats)


class BmrbUniprotMap(Schema):
    format = CustomErrorEnum(ResponseFormats)


class MatchFormats(enum.Enum):
    exact = "exact"
    author = "author"
    blast = "blast"
    assembly = "assembly"


class PdbBmrbMap(Schema):
    match_type = CustomErrorEnum(MatchFormats)
    format = CustomErrorEnum(ResponseFormats)
    pass


class BmrbPdbMap(Schema):
    match_type = CustomErrorEnum(MatchFormats)
    format = CustomErrorEnum(ResponseFormats)
    pass


class Uniprot(Schema):
    class Formats(enum.Enum):
        json = "json"
        hupo_psi_id = "hupo-psi-id"

    format = CustomErrorEnum(Formats)


class GetPdbIdsFromBmrbId(Schema):
    pass
