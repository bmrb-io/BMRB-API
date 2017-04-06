-- yum install postgresql-contrib
-- psql -d bmrbeverything -U postgres
--   CREATE EXTENSION pg_trgm;

CREATE OR REPLACE FUNCTION web.clean_title(varchar) RETURNS varchar AS
$body$
BEGIN
    RETURN regexp_replace( regexp_replace( "Citation"."Title", E'\\s+', ' ', 'g' ), E'\\s+', ' ', 'g' )
END;
$body$
IMMUTABLE LANGUAGE plpgsql;

DROP TABLE IF EXISTS web.instant_cache;
CREATE TABLE web.instant_cache (id varchar(12) PRIMARY KEY, title text,
citations text[], authors text[], link text, sub_date date, is_metab
boolean, tsv tsvector);

INSERT INTO web.instant_cache
SELECT
 entry."ID",
 web.clean_title(entry."Title"),
 array_agg(DISTINCT web.clean_title(citation."Title")),
 array_agg(DISTINCT REPLACE(Replace(citation_author."Given_name", '.',
'') || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.',
''),'') || ' ' || Replace(citation_author."Family_name", '.', ''), '  ',
' ')),
 '/data_library/summary/index.php?bmrbId=' || entry."ID",
 to_date(entry."Submission_date", 'YYYY-MM-DD'),
 False
FROM macromolecules."Entry" as entry
LEFT JOIN macromolecules."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN macromolecules."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
GROUP BY entry."ID",entry."Title", entry."Submission_date";

INSERT INTO web.instant_cache
SELECT
 entry."ID",
 web.clean_title(entry."Title"),
 array_agg(DISTINCT web.clean_title(citation."Title")),
 array_agg(DISTINCT REPLACE(Replace(citation_author."Given_name", '.',
'') || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.',
''),'') || ' ' || Replace(citation_author."Family_name", '.', ''), '  ',
' ')),
 '/metabolomics/mol_summary/index.php?whichTab=0&id=' || entry."ID",
 entry."Submission_date",
 True
FROM metabolomics."Entry" as entry
LEFT JOIN metabolomics."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN metabolomics."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
GROUP BY entry."ID",entry."Title", entry."Submission_date";

CREATE INDEX ON web.instant_cache USING gin(tsv);
UPDATE web.instant_cache SET tsv =
    setweight(to_tsvector(instant_cache.id), 'A') ||
    setweight(to_tsvector(array_to_string(instant_cache.authors, ' ')),
'B') ||
    setweight(to_tsvector(instant_cache.title), 'C') ||
    setweight(to_tsvector(array_to_string(instant_cache.citations, '
')), 'D');

DROP FUNCTION web.clean_title(varchar);
