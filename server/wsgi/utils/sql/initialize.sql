-- yum install postgresql-contrib
-- psql -d bmrbeverything -U postgres
--   CREATE EXTENSION pg_trgm;
-- curl https://raw.githubusercontent.com/uwbmrb/BMRB-API/master/server/wsgi/utils/sql/initialize.sql

CREATE OR REPLACE FUNCTION web.clean_title(varchar) RETURNS varchar AS
$body$
BEGIN
    RETURN replace(regexp_replace($1, E'[\\n\\r]+', ' ', 'g' ), '  ', ' ');
END;
$body$
IMMUTABLE LANGUAGE plpgsql;

DROP TABLE IF EXISTS web.instant_cache_tmp;
CREATE TABLE web.instant_cache_tmp (id varchar(12) PRIMARY KEY, title text, citations text[], authors text[], link text, sub_date date, is_metab boolean, tsv tsvector);

INSERT INTO web.instant_cache_tmp
SELECT
 entry."ID",
 web.clean_title(entry."Title"),
 array_agg(DISTINCT web.clean_title(citation."Title")),
 array_agg(DISTINCT REPLACE(Replace(citation_author."Given_name", '.', '') || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.', ''),'') || ' ' || Replace(citation_author."Family_name", '.', ''), '  ', ' ')),
 '/data_library/summary/index.php?bmrbId=' || entry."ID",
 to_date(entry."Submission_date", 'YYYY-MM-DD'),
 False
FROM macromolecules."Entry" as entry
LEFT JOIN macromolecules."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN macromolecules."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
GROUP BY entry."ID",entry."Title", entry."Submission_date";

INSERT INTO web.instant_cache_tmp
SELECT
 entry."ID",
 web.clean_title(entry."Title"),
 array_agg(DISTINCT web.clean_title(citation."Title")),
 array_agg(DISTINCT REPLACE(Replace(citation_author."Given_name", '.', '') || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.', ''),'') || ' ' || Replace(citation_author."Family_name", '.', ''), '  ', ' ')),
 '/metabolomics/mol_summary/index.php?whichTab=0&molName=' || entry."Title" || '&id=' || entry."ID",
 entry."Submission_date",
 True
FROM metabolomics."Entry" as entry
LEFT JOIN metabolomics."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN metabolomics."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
GROUP BY entry."ID",entry."Title", entry."Submission_date";

CREATE INDEX ON web.instant_cache_tmp USING gin(tsv);
UPDATE web.instant_cache_tmp SET tsv =
    setweight(to_tsvector(instant_cache_tmp.id), 'A') ||
    setweight(to_tsvector(array_to_string(instant_cache_tmp.authors, ' ')), 'B') ||
    setweight(to_tsvector(instant_cache_tmp.title), 'C') ||
    setweight(to_tsvector(array_to_string(instant_cache_tmp.citations, ' ')), 'D')
;

ALTER TABLE IF EXISTS web.instant_cache RENAME TO instant_cache_old;
-- If our temp table somehow doesn't exist this whole transaction will fail and roll-back
ALTER TABLE web.instant_cache_tmp RENAME TO instant_cache;
DROP TABLE web.instant_cache_old;
