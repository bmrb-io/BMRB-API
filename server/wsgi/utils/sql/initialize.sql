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

-- Create terms table
CREATE TABLE web.instant_extra_search_terms_tmp (
    id varchar(12),
    term text,
    termname text);
CREATE INDEX ON web.instant_extra_search_terms_tmp USING gin(term gin_trgm_ops);

INSERT INTO web.instant_extra_search_terms_tmp
-- metabolomics
SELECT DISTINCT "Entry_ID", "Name",'Systematic name' FROM metabolomics."Chem_comp_systematic_name"
UNION
SELECT DISTINCT "Entry_ID", "Formula",'Formula' FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "InCHi_code",'InChI' FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Chem Comp name' FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Common name' FROM metabolomics."Chem_comp_common_name"
UNION
SELECT DISTINCT "Entry_ID", "String", 'SMILES' FROM metabolomics."Chem_comp_SMILES"
UNION
SELECT DISTINCT "Entry_ID", "Descriptor",'Compound desciption' FROM metabolomics."Chem_comp_descriptor"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Entity name' FROM metabolomics."Entity"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Assembly name' FROM metabolomics."Assembly"
UNION
SELECT DISTINCT "Entry_ID", "PubMed_ID", 'PubMed ID'  FROM metabolomics."Citation"

--macromolecule
UNION
SELECT DISTINCT "Entry_ID",regexp_replace("Polymer_seq_one_letter_code", '\n| ', '', 'g'),'Polymer sequence' FROM macromolecules."Entity"
UNION
SELECT DISTINCT "Entry_ID","Accession_code","Database_code" || ' Accession code' FROM macromolecules."Entity_db_link" WHERE "Database_code" != 'BMRB'
UNION
SELECT DISTINCT "Entry_ID","Organism_name_scientific",'Scientific name' FROM macromolecules."Entity_natural_src" WHERE "Organism_name_scientific" IS NOT null
UNION
SELECT DISTINCT "Entry_ID","Organism_name_common",'Common name' FROM macromolecules."Entity_natural_src" WHERE "Organism_name_common" IS NOT null
UNION
SELECT DISTINCT "Entry_ID", "Name",'Entity name' FROM macromolecules."Entity"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Assembly name' FROM macromolecules."Assembly"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Chem Comp name' FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "PubMed_ID", 'PubMed ID'  FROM macromolecules."Citation"
;

-- Easier to do this to delete ~2000 rows than modify all of the above statements to exclude nulls
DELETE FROM web.instant_extra_search_terms_tmp WHERE term IS NULL;

-- Move the new table into place
ALTER TABLE IF EXISTS web.instant_extra_search_terms RENAME TO instant_extra_search_terms_old;
ALTER TABLE web.instant_extra_search_terms_tmp RENAME TO instant_extra_search_terms;
DROP TABLE IF EXISTS web.instant_extra_search_terms_old;






-- Create tsvector table
DROP TABLE IF EXISTS web.instant_cache;
CREATE TABLE web.instant_cache_tmp (
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
INSERT INTO web.instant_cache_tmp
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
INSERT INTO web.instant_cache_tmp
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
INSERT INTO web.instant_cache_tmp
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
INSERT INTO web.instant_cache_tmp
SELECT
 accno,
 'Entry is on hold. Release: ' || status,
 array[]::text[],
 array[]::text[],
 '/data_library/held.shtml#' || accno,
 received,
 False
FROM web.procque WHERE onhold='Y';

-- Create the index on the tsvector
CREATE INDEX ON web.instant_cache_tmp USING gin(tsv);
UPDATE web.instant_cache_tmp SET tsv =
    setweight(to_tsvector(instant_cache_tmp.id), 'A') ||
    setweight(to_tsvector(array_to_string(instant_cache_tmp.authors, ' ')),
'B') ||
    setweight(to_tsvector(instant_cache_tmp.title), 'C') ||
    setweight(to_tsvector(array_to_string(instant_cache_tmp.citations, '
')), 'D');

-- Create the index for the text search using tsvector
CREATE INDEX ON web.instant_cache_tmp USING gin(full_tsv);
-- Create a trigram index on the full text
CREATE INDEX ON web.instant_cache_tmp USING gin(full_text gin_trgm_ops);


-- Move the new table into place
ALTER TABLE IF EXISTS web.instant_cache RENAME TO instant_cache_old;
ALTER TABLE web.instant_cache_tmp RENAME TO instant_cache;
DROP TABLE IF EXISTS web.instant_cache_old;

-- Clean up
DROP FUNCTION web.clean_title(varchar);
GRANT ALL PRIVILEGES ON TABLE web.instant_extra_search_terms to web;
GRANT ALL PRIVILEGES ON TABLE web.instant_extra_search_terms to bmrb;
GRANT ALL PRIVILEGES ON TABLE web.instant_cache to web;
GRANT ALL PRIVILEGES ON TABLE web.instant_cache to bmrb;

    
    
/*
-- Query both tsv and trigram at once. Partially broken still since
-- the UNIONED results are not in the right order
SELECT DISTINCT ON (id) * from(
SELECT * FROM (
  SELECT ''::text as term,''::text as term,1.5::real as sml,id,title,citations,authors,link,sub_date FROM web.instant_cache
    WHERE tsv @@ plainto_tsquery('caffeine')
    ORDER BY is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery('caffeine')) DESC) AS one
UNION
SELECT * FROM (
  SELECT DISTINCT on (id) term,termname,similarity(tt.term, 'caffeine') as sml,tt.id,title,citations,authors,link,sub_date FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.term % 'caffeine'
    ORDER BY id DESC, similarity(tt.term, 'caffeine') DESC) AS two) AS three;
*/

