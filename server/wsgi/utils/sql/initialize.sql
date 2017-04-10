-- To support the feature we need
-- yum install postgresql-contrib
-- psql -d bmrbeverything -U postgres
--   CREATE EXTENSION pg_trgm;

-- Helper function. We will delete this later.
CREATE OR REPLACE FUNCTION web.clean_title(varchar) RETURNS varchar AS
$body$
BEGIN
    RETURN replace(regexp_replace($1, E'[\\n\\r]+', ' ', 'g' ), '  ', ' ');
END
$body$
IMMUTABLE LANGUAGE plpgsql;

-- Create table
DROP TABLE IF EXISTS web.instant_cache;
CREATE TABLE web.instant_cache (
 id varchar(12) PRIMARY KEY,
 title text,
 citations text[],
 authors text[],
 link text,
 sub_date date,
 is_metab boolean,
 tsv tsvector,
 full_tsv tsvector,
 full_text text);

-- Macromolecules
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

-- Metabolomics
INSERT INTO web.instant_cache
SELECT
 entry."ID",
 web.clean_title(entry."Title"),
 array_agg(DISTINCT web.clean_title(citation."Title")),
 array_agg(DISTINCT REPLACE(Replace(citation_author."Given_name", '.',
'') || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.',
''),'') || ' ' || Replace(citation_author."Family_name", '.', ''), '  ',
' ')),
 '/metabolomics/mol_summary/show_data.php?id=' || entry."ID",
 entry."Submission_date",
 True
FROM metabolomics."Entry" as entry
LEFT JOIN metabolomics."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN metabolomics."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
GROUP BY entry."ID",entry."Title", entry."Submission_date";

-- Processing
INSERT INTO web.instant_cache
SELECT
 accno,
 'Entry is being processed',
 array[]::text[],
 array[]::text[],
 '/data_library/received.shtml',
 received,
 False
FROM web.procque WHERE onhold='N';

-- On hold
INSERT INTO web.instant_cache
SELECT
 accno,
 'Entry is being processed. Release: ' || status,
 array[]::text[],
 array[]::text[],
 '/data_library/held.shtml',
 received,
 False
FROM web.procque WHERE onhold='Y';

-- Create the index on the tsvector
CREATE INDEX ON web.instant_cache USING gin(tsv);
UPDATE web.instant_cache SET tsv =
    setweight(to_tsvector(instant_cache.id), 'A') ||
    setweight(to_tsvector(array_to_string(instant_cache.authors, ' ')),
'B') ||
    setweight(to_tsvector(instant_cache.title), 'C') ||
    setweight(to_tsvector(array_to_string(instant_cache.citations, '
')), 'D');

-- Create the index for the text search using tsvector
CREATE INDEX ON web.instant_cache USING gin(full_tsv);
-- Create a trigram index on the full text
CREATE INDEX ON web.instant_cache USING gin(full_text gin_trgm_ops);

DROP FUNCTION web.clean_title(varchar);

GRANT ALL PRIVILEGES ON TABLE web.instant_cache to web;
