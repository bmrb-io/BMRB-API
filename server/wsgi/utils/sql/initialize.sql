-- To support the feature we need
-- yum install postgresql-contrib
-- psql -d bmrbeverything -U postgres
--   CREATE EXTENSION pg_trgm;




-- Update metabolomics and macromolecule entry tables to have "Entry_ID"
DO $$
BEGIN
    BEGIN
        ALTER TABLE macromolecules."Entry" ADD COLUMN "Entry_ID" text;
        UPDATE macromolecules."Entry" Set "Entry_ID" = "ID";
        ALTER TABLE metabolomics."Entry" ADD COLUMN "Entry_ID" text;
        UPDATE metabolomics."Entry" Set "Entry_ID" = "ID";
    EXCEPTION
        WHEN duplicate_column THEN RAISE NOTICE '"Entry_ID" already exists in "Entry" table. Running this twice?';
    END;
END $$;

-- Used when fetching pH and temperature
CREATE OR REPLACE FUNCTION web.convert_to_numeric(text)
  RETURNS numeric AS
$func$
BEGIN
    RETURN $1::numeric;
EXCEPTION WHEN OTHERS THEN
   RETURN NULL;  -- NULL for other invalid input
END
$func$  LANGUAGE plpgsql IMMUTABLE;

-- Put some indexes on the chemical shifts
DO $$
BEGIN
    BEGIN
        CREATE INDEX error_on_duplicates ON macromolecules."Atom_chem_shift" ("Atom_type");
        CREATE INDEX ON macromolecules."Atom_chem_shift" ("Atom_ID");
        CREATE INDEX ON macromolecules."Atom_chem_shift" ("Comp_ID");
        CREATE INDEX ON macromolecules."Atom_chem_shift" (CAST("Val" as float));
        CREATE INDEX ON macromolecules."Atom_chem_shift" ("Atom_chem_shift_Comp_ID_id");
        ANALYZE macromolecules."Atom_chem_shift";

        CREATE INDEX ON metabolomics."Atom_chem_shift" ("Atom_type");
        CREATE INDEX ON metabolomics."Atom_chem_shift" ("Atom_ID");
        CREATE INDEX ON metabolomics."Atom_chem_shift" ("Comp_ID");
        CREATE INDEX ON metabolomics."Atom_chem_shift" (CAST("Val" as float));
        CREATE INDEX ON metabolomics."Atom_chem_shift" ("Atom_chem_shift_Comp_ID_id");
        ANALYZE metabolomics."Atom_chem_shift";
    EXCEPTION
        WHEN OTHERS THEN RAISE NOTICE 'Skipping chemical_shift index creation because at least one index already exists.';
    END;
END $$;

-- Now start with the instant search...

-- Helper function. We will delete this later.
CREATE OR REPLACE FUNCTION web.clean_title(varchar) RETURNS varchar AS
$body$
BEGIN
    RETURN replace(regexp_replace($1, E'[\\n\\r]+', ' ', 'g' ), '  ', ' ');
END
$body$
IMMUTABLE LANGUAGE plpgsql;


--- This is for the additional information about metabolomics in the instant search
-- 2.  Molecular Formula  3.  InCh 4.  SMILES 5.  Average Mass 6.  Molecular Weight 7.  Monoisotopic Mass

DROP TABLE IF EXISTS web.metabolomics_summary_tmp;
CREATE TABLE web.metabolomics_summary_tmp (
    id varchar(12) PRIMARY KEY,
    formula text,
    inchi text,
    smiles text,
    average_mass numeric,
    molecular_weight numeric,
    monoisotopic_mass numeric);

INSERT INTO web.metabolomics_summary_tmp (id, formula, inchi, smiles, average_mass, molecular_weight, monoisotopic_mass)
  SELECT cc."Entry_ID", replace(cc."Formula", ' ', ''), cc."InCHi_code", sm."String", cc."Formula_weight"::numeric, cc."Formula_weight"::numeric, cc."Formula_mono_iso_wt_nat"::numeric
  FROM metabolomics."Chem_comp" as cc
  LEFT JOIN metabolomics."Chem_comp_SMILES" AS sm
  ON sm."Entry_ID"=cc."Entry_ID"
  WHERE sm."Type" = 'canonical';

-- Move the new table into place
ALTER TABLE IF EXISTS web.metabolomics_summary RENAME TO metabolomics_summary_old;
ALTER TABLE web.metabolomics_summary_tmp RENAME TO metabolomics_summary;
DROP TABLE IF EXISTS web.metabolomics_summary_old;


-- Create terms table
DROP TABLE IF EXISTS web.instant_extra_search_terms_tmp;
CREATE TABLE web.instant_extra_search_terms_tmp (
    id varchar(12),
    term text,
    termname text,
    identical_term tsvector);
CREATE INDEX ON web.instant_extra_search_terms_tmp USING gin(term gin_trgm_ops);
CREATE INDEX ON web.instant_extra_search_terms_tmp USING gin(identical_term);

INSERT INTO web.instant_extra_search_terms_tmp (id, termname, term, identical_term)
SELECT DISTINCT "Entry_ID", 'PubMed ID', "PubMed_ID", to_tsvector("PubMed_ID") FROM metabolomics."Citation"
UNION
SELECT DISTINCT "Entry_ID", 'PubMed ID', "PubMed_ID", to_tsvector("PubMed_ID") FROM macromolecules."Citation"
UNION
SELECT DISTINCT "Entry_ID", 'Additional data', "Type", to_tsvector("Type") FROM macromolecules."Datum"
UNION
SELECT DISTINCT "Entry_ID", 'Citation DOI', "DOI", to_tsvector("DOI") FROM macromolecules."Citation" where "DOI" IS NOT NULL
UNION
SELECT DISTINCT "ID", 'PDB structure', "Assigned_PDB_ID", to_tsvector("Assigned_PDB_ID") FROM macromolecules."Entry"
UNION
SELECT DISTINCT "Entry_ID", 'Matching PDB', "Database_accession_code", to_tsvector("Database_accession_code") FROM macromolecules."Related_entries" WHERE "Database_name"='PDB' AND "Relationship"='BMRB Entry Tracking System'
UNION
SELECT DISTINCT "Entry_ID", 'BMRB Entry DOI', '10.13018/BMR' || "Entry_ID", to_tsvector('10.13018/BMR' || "Entry_ID") FROM macromolecules."Entry"
UNION
SELECT DISTINCT "Entry_ID", 'BMRB Entry DOI', '10.13018/' || UPPER("Entry_ID"), to_tsvector('10.13018/' || UPPER("Entry_ID")) FROM metabolomics."Entry" WHERE "Entry_ID" like 'bmse%'
UNION
SELECT DISTINCT "Entry_ID", 'BMRB Entry DOI', '10.13018/' || UPPER("Entry_ID"), to_tsvector('10.13018/' || UPPER("Entry_ID")) FROM metabolomics."Entry" WHERE "Entry_ID" like 'bmst%'
UNION
SELECT DISTINCT "Entry_ID", 'BMRB Entry DOI', 'DOI:10.13018/BMR' || "Entry_ID", to_tsvector('DOI:10.13018/BMR' || "Entry_ID") FROM macromolecules."Entry"
UNION
SELECT DISTINCT "Entry_ID", 'BMRB Entry DOI', 'DOI:10.13018/' || UPPER("Entry_ID"), to_tsvector('DOI:10.13018/' || UPPER("Entry_ID")) FROM metabolomics."Entry" WHERE "Entry_ID" like 'bmse%'
UNION
SELECT DISTINCT "Entry_ID", 'BMRB Entry DOI', 'DOI:10.13018/' || UPPER("Entry_ID"), to_tsvector('DOI:10.13018/' || UPPER("Entry_ID")) FROM metabolomics."Entry" WHERE "Entry_ID" like 'bmst%'

-- This is here and below to make exact matches show up prior to fuzzy matches, but still allow fuzzy matches
UNION
SELECT DISTINCT "Entry_ID", 'Author provided ' || "Database_code" || ' Accession code', "Accession_code", to_tsvector("Accession_code") FROM macromolecules."Entity_db_link"
--
  WHERE "Database_code" != 'BMRB' AND "Author_supplied" = 'yes'
UNION
SELECT DISTINCT "Entry_ID", 'BLAST-linked ' || "Database_code" || ' Accession code', "Accession_code", to_tsvector("Accession_code") FROM macromolecules."Entity_db_link"
  WHERE "Database_code" != 'BMRB' AND "Author_supplied" = 'no';

INSERT INTO web.instant_extra_search_terms_tmp
-- metabolomics
SELECT DISTINCT "Entry_ID", "Name",'Systematic name' FROM metabolomics."Chem_comp_systematic_name"
UNION
SELECT DISTINCT "Entry_ID", regexp_replace("Formula", '\s', '', 'g'),'Formula' FROM metabolomics."Chem_comp"
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

--macromolecule
UNION
SELECT DISTINCT "Entry_ID",regexp_replace("Polymer_seq_one_letter_code", '\n| ', '', 'g'),'Polymer sequence' FROM macromolecules."Entity"
UNION
SELECT DISTINCT "Entry_ID","Organism_name_scientific",'Scientific name' FROM macromolecules."Entity_natural_src" WHERE "Organism_name_scientific" IS NOT null
UNION
SELECT DISTINCT "Entry_ID","Organism_name_common",'Common name' FROM macromolecules."Entity_natural_src" WHERE "Organism_name_common" IS NOT null
UNION
SELECT DISTINCT "Entry_ID", "Name",'Entity name' FROM macromolecules."Entity"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Assembly name' FROM macromolecules."Assembly"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Chem Comp name' FROM macromolecules."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "Accession_code", 'Author provided ' || "Database_code" || ' Accession code' FROM macromolecules."Entity_db_link"
  WHERE "Database_code" != 'BMRB' AND "Author_supplied" = 'yes';

-- Easier to do this to delete ~2000 rows than modify all of the above statements to exclude nulls
DELETE FROM web.instant_extra_search_terms_tmp WHERE term IS NULL AND identical_term IS NULL;

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

-- Metabolomics bmse
INSERT INTO web.instant_cache_tmp
SELECT
 entry."ID",
 web.clean_title(chem_comp."Name"),
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
LEFT JOIN metabolomics."Chem_comp" AS chem_comp
  ON entry."ID"=chem_comp."Entry_ID"
WHERE entry."ID" like 'bmse%'
GROUP BY entry."ID",chem_comp."Name", entry."Submission_date";

-- Metabolomics bmst
INSERT INTO web.instant_cache_tmp
SELECT
 entry."ID",
 web.clean_title(entry."Title"),
 array_agg(DISTINCT web.clean_title(citation."Title")),
 array_agg(DISTINCT REPLACE(Replace(citation_author."Given_name", '.',
'') || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.',
''),'') || ' ' || Replace(citation_author."Family_name", '.', ''), '  ',
' ')),
 '/metabolomics/mol_summary/show_theory.php?id=' || entry."ID",
 entry."Submission_date",
 True
FROM metabolomics."Entry" as entry
LEFT JOIN metabolomics."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN metabolomics."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
WHERE entry."ID" like 'bmst%'
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
