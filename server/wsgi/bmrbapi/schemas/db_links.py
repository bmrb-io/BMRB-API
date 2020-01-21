import enum

from marshmallow import Schema

from bmrbapi.schemas.default import CustomErrorEnum

__all__ = ['UniprotMappingsInternal', 'UniprotBmrbMap', 'BmrbUniprotMap', 'PdbBmrbMap', 'BmrbPdbMap',
           'Uniprot', 'GetPdbIdsFromBmrbId']


class ResponseFormats(enum.Enum):
    json = "json"
    text = "text"


class MatchFormatsPDB(enum.Enum):
    exact = "exact"
    author = "author"
    blast = "blast"
    assembly = "assembly"
    all = "all"


class MatchFormatsUniProt(enum.Enum):
    author = "author"
    blast = "blast"
    pdb = "pdb"
    all = "all"


class UniprotMappingsInternal(Schema):
    format = CustomErrorEnum(ResponseFormats)


class UniprotBmrbMap(Schema):
    match_type = CustomErrorEnum(MatchFormatsUniProt)
    format = CustomErrorEnum(ResponseFormats)


class BmrbUniprotMap(Schema):
    match_type = CustomErrorEnum(MatchFormatsUniProt)
    format = CustomErrorEnum(ResponseFormats)


class PdbBmrbMap(Schema):
    match_type = CustomErrorEnum(MatchFormatsPDB)
    format = CustomErrorEnum(ResponseFormats)
    pass


class BmrbPdbMap(Schema):
    match_type = CustomErrorEnum(MatchFormatsPDB)
    format = CustomErrorEnum(ResponseFormats)
    pass


class Uniprot(Schema):
    class Formats(enum.Enum):
        json = "json"
        hupo_psi_id = "hupo-psi-id"

    format = CustomErrorEnum(Formats)


class GetPdbIdsFromBmrbId(Schema):
    pass
