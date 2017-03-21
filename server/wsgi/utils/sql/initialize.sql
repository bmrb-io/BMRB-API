-- yum install postgresql-contrib
-- psql -d bmrbeverything -U postgres
--   CREATE EXTENSION pg_trgm;

DROP TABLE IF EXISTS instant_cache;
CREATE TABLE instant_cache (id varchar(12), title text, citations text[], authors text[], link text, sub_date date, is_metab boolean, tsv tsvector);

INSERT INTO instant_cache
SELECT
 entry."ID",
 clean_title(entry."Title"),
 array_agg(DISTINCT clean_title(citation."Title")),
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

INSERT INTO instant_cache
SELECT
 entry."ID",
 clean_title(entry."Title"),
 array_agg(DISTINCT clean_title(citation."Title")),
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

CREATE INDEX tsv_idx ON instant_cache USING gin(tsv);
UPDATE instant_cache SET tsv =
    setweight(to_tsvector(instant_cache.id), 'A') ||
    setweight(to_tsvector(array_to_string(instant_cache.authors, ' ')), 'B') ||
    setweight(to_tsvector(instant_cache.title), 'C') ||
    setweight(to_tsvector(array_to_string(instant_cache.citations, ' ')), 'D')
;
