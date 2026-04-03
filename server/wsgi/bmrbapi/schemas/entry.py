import enum

from marshmallow import fields, Schema

from bmrbapi.schemas.default import DatabaseSchema, CustomErrorEnum

__all__ = ['GetEntry', 'GetSoftwareByEntry', 'GetExperimentData', 'GetCitation', 'SimulateHsqc',
           'ValidateEntry', 'ListEntries']


class GetEntry(Schema):
    class Format(enum.Enum):
        json = "json"
        rawnmrstar = "rawnmrstar"
        zlib = "zlib"

    format = CustomErrorEnum(Format)
    saveframe_category = fields.String(metadata={'multiple': True})
    saveframe_name = fields.String(metadata={'multiple': True})
    loop = fields.String(metadata={'multiple': True})
    tag = fields.String(metadata={'multiple': True})


class GetSoftwareByEntry(Schema):
    pass


class GetExperimentData(Schema):
    shift = fields.Float(metadata={'multiple': True})
    threshold = fields.Float()
    atom_type = fields.String()
    atom_id = fields.String(metadata={'multiple': True})
    comp_id = fields.String(metadata={'multiple': True})
    conditions = fields.Bool()


class GetCitation(Schema):
    class Format(enum.Enum):
        text = "text"
        json_ld = "json-ld"
        bibtex = "bibtex"
    format = CustomErrorEnum(Format)
    file_name = fields.String()


class SimulateHsqc(Schema):
    class Format(enum.Enum):
        html = "html"
        csv = "csv"
        json = "json"
        sparky = "sparky"

    class Filter(enum.Enum):
        backbone = "backbone"
        all = "all"
    format = CustomErrorEnum(Format)
    filter = CustomErrorEnum(Filter)
    pass


class ValidateEntry(Schema):
    pass


class ListEntries(DatabaseSchema):
    pass
