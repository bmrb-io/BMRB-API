from bmrbapi.schemas.default import DatabaseSchema, JSONResponseSchema

__all__ = ['GetSoftwareSummary', 'GetSoftwareByPackage']


class GetSoftwareSummary(DatabaseSchema, JSONResponseSchema):
    pass


class GetSoftwareByPackage(DatabaseSchema, JSONResponseSchema):
    pass
