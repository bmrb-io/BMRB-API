-- To support the feature we need
-- yum install postgresql-contrib
-- psql -d bmrbeverything -U postgres

CREATE extension IF NOT EXISTS pg_trgm;

-- Put an index on the chemical shift values. Even though we will primarily use our custom table,
--  the indexes are still helpful for certain other queries we will make against this table
DO $$
BEGIN
    BEGIN
        CREATE INDEX error_on_duplicates ON macromolecules."Atom_chem_shift" (CAST("Val" AS FLOAT), "Atom_type");
        CREATE INDEX ON metabolomics."Atom_chem_shift" (CAST("Val" AS FLOAT), "Atom_type");
        ANALYZE macromolecules."Atom_chem_shift";
        ANALYZE metabolomics."Atom_chem_shift";
    EXCEPTION
        WHEN OTHERS THEN RAISE NOTICE 'Skipping chemical_shift index creation because at least one index already exists.';
    END;
END $$;

DROP MATERIALIZED VIEW IF EXISTS web.query_grid_tmp;
CREATE MATERIALIZED VIEW web.query_grid_tmp AS
SELECT entity."Entry_ID",
       array_agg(DISTINCT entity."Polymer_type")                                            AS "Polymer_types",
       (SELECT "Name"
        FROM macromolecules."Assembly" AS assem
        WHERE assem."Entry_ID" = entity."Entry_ID"
          AND assem."ID" = '1')                                                             AS system_name,
       COUNT(cs.*) FILTER ( WHERE cs."Atom_type" = 'C' AND cs."Atom_isotope_number" = '13') AS carbon_shifts,
       COUNT(cs.*) FILTER ( WHERE cs."Atom_type" = 'N' AND cs."Atom_isotope_number" = '15') AS nitrogen_shifts,
       COUNT(cs.*) FILTER ( WHERE cs."Atom_type" = 'P' AND cs."Atom_isotope_number" = '31') AS phosphorus_shifts,
       COUNT(cs.*) FILTER ( WHERE cs."Atom_type" = 'H' AND cs."Atom_isotope_number" = '1')  AS hydrogen_shifts,
       COUNT(cs.*) FILTER ( WHERE
               NOT (cs."Atom_type" = 'H' AND cs."Atom_isotope_number" = '1')
               AND NOT (cs."Atom_type" = 'P' AND cs."Atom_isotope_number" = '31')
               AND NOT (cs."Atom_type" = 'N' AND cs."Atom_isotope_number" = '15')
               AND NOT (cs."Atom_type" = 'C' AND cs."Atom_isotope_number" = '13'))          AS other_shifts,
       COUNT(cs.*)                                                                          AS total_shifts,
       (SELECT COUNT(cc.*)
        FROM macromolecules."Coupling_constant" AS cc
        WHERE cc."Entry_ID" = entity."Entry_ID")                                            AS coupling_constants,
       (SELECT COUNT(rdc.*)
        FROM macromolecules."RDC" AS rdc
        WHERE rdc."Entry_ID" = entity."Entry_ID")                                           as rdcs,
       (SELECT COUNT(subq.*)
        FROM (SELECT true
              FROM macromolecules."T1" AS t1
              WHERE t1."Entry_ID" = entity."Entry_ID"
                AND t1."Val" IS NOT NULL
              UNION ALL
              SELECT true
              FROM macromolecules."Auto_relaxation" AS ar
                       LEFT JOIN macromolecules."Auto_relaxation_list" AS arl
                                 ON arl."ID" = ar."Auto_relaxation_list_ID"
              WHERE ar."Entry_ID" = entity."Entry_ID"
                AND ar."Auto_relaxation_val" IS NOT NULL
                AND (UPPER(arl."Common_relaxation_type_name") = 'R1' OR
                     (UPPER(arl."Common_relaxation_type_name") = 'T1'))) AS subq)           AS t1s,
       (SELECT COUNT(subq.*)
        FROM (SELECT true
              FROM macromolecules."T2" AS T2
              WHERE T2."Entry_ID" = entity."Entry_ID"
                AND T2."T2_val" IS NOT NULL
              UNION ALL
              SELECT true
              FROM macromolecules."Auto_relaxation" AS ar
                       LEFT JOIN macromolecules."Auto_relaxation_list" AS arl
                                 ON arl."ID" = ar."Auto_relaxation_list_ID"
              WHERE ar."Entry_ID" = entity."Entry_ID"
                AND ar."Auto_relaxation_val" IS NOT NULL
                AND (UPPER(arl."Common_relaxation_type_name") = 'R2' OR
                     (UPPER(arl."Common_relaxation_type_name") = 'T2'))) AS subq)           AS t2s,
       (SELECT COUNT(heteronuclear_noes.*)
        FROM macromolecules."Heteronucl_NOE" AS heteronuclear_noes
        WHERE heteronuclear_noes."Entry_ID" = entity."Entry_ID")                            AS heteronuclear_noes,
       (SELECT COUNT(homonuclear_noes.*)
        FROM macromolecules."Homonucl_NOE" AS homonuclear_noes
        WHERE homonuclear_noes."Entry_ID" = entity."Entry_ID")                              AS homonuclear_noes,
       (SELECT COUNT(order_param.*)
        FROM macromolecules."Order_param" AS order_param
        WHERE order_param."Entry_ID" = entity."Entry_ID"
          AND "Order_param_val" IS NOT NULL)                                                AS order_params,
       (SELECT COUNT(h_exchange.*)
        FROM macromolecules."H_exch_rate" AS h_exchange
        WHERE h_exchange."Entry_ID" = entity."Entry_ID"
          AND "Val" IS NOT NULL)                                                            AS h_exchanges,
       (SELECT COUNT(h_exchange_protection.*)
        FROM macromolecules."H_exch_protection_factor" AS h_exchange_protection
        WHERE h_exchange_protection."Entry_ID" = entity."Entry_ID"
          AND "Val" IS NOT NULL)                                                            AS h_protection_factors,
       (SELECT COUNT(csa."Val")
        FROM macromolecules."CS_anisotropy" AS csa
        WHERE csa."Entry_ID" = entity."Entry_ID"
          AND "Val" IS NOT NULL)                                                            AS cs_anisotropys,
       COALESCE((SELECT sets FROM web.timedomain_data WHERE bmrbid = entity."Entry_ID"), 0) AS timedomain_data_sets,
       (SELECT array_agg(pdb_id) FROM web.pdb_link WHERE bmrb_id = entity."Entry_ID")       AS pdb_ids,
       (SELECT (COUNT(*) = COUNT(*) FILTER ( WHERE "Mol_common_name" = 'DSS'
           AND "Chem_shift_val"::numeric = 0
           AND (("Indirect_shift_ratio"::numeric = 1 AND "Atom_type" = 'H' AND "Atom_isotope_number" = '1') OR
                ("Indirect_shift_ratio"::numeric = .153506088 AND "Atom_type" = 'H' AND "Atom_isotope_number" = '2') OR
                ("Indirect_shift_ratio"::numeric = .251449530 AND "Atom_type" = 'C' AND "Atom_isotope_number" = '13') OR
                ("Indirect_shift_ratio"::numeric = .101329118 AND "Atom_type" = 'N' AND "Atom_isotope_number" = '15') OR
                ("Indirect_shift_ratio"::numeric = .101329118 AND "Atom_type" = 'P' AND
                 "Atom_isotope_number" = '31'))))::int
        FROM macromolecules."Chem_shift_ref"
        WHERE "Entry_ID" = entity."Entry_ID")                                               AS iupac_referencing
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."Atom_chem_shift" AS cs
                   ON cs."Entry_ID" = entity."Entry_ID" AND cs."Entity_ID" = entity."ID"
WHERE "Polymer_type" IS NOT NULL
GROUP BY entity."Entry_ID";
CREATE UNIQUE INDEX ON web.query_grid_tmp ("Entry_ID");

-- Go live with the new query grid info
BEGIN;
DROP MATERIALIZED VIEW web.query_grid;
ALTER MATERIALIZED VIEW web.query_grid_tmp RENAME TO query_grid;
END;


-- All of the following (until the next comment) creates a materialized view
--  to be able to read the chemical shifts much faster
CREATE OR REPLACE FUNCTION web.convert_to_numeric(text)
  RETURNS numeric AS
$func$
BEGIN
    RETURN $1::numeric;
EXCEPTION WHEN OTHERS THEN
   RETURN NULL;  -- NULL for other invalid input
END
$func$  LANGUAGE plpgsql IMMUTABLE;

DROP MATERIALIZED VIEW IF EXISTS web.chem_shifts_tmp;
CREATE MATERIALIZED VIEW web.chem_shifts_tmp AS
SELECT cs."Entry_ID"                          AS "Atom_chem_shift.Entry_ID",
       "Entity_ID"::integer                   AS "Atom_chem_shift.Entity_ID",
       "Comp_index_ID"::integer               AS "Atom_chem_shift.Comp_index_ID",
       "Comp_ID"                              AS "Atom_chem_shift.Comp_ID",
       "Atom_ID"                              AS "Atom_chem_shift.Atom_ID",
       "Atom_type"                            AS "Atom_chem_shift.Atom_type",
       cs."Val"::numeric                      AS "Atom_chem_shift.Val",
       cs."Val_err"::numeric                  AS "Atom_chem_shift.Val_err",
       "Ambiguity_code"::int                  AS "Atom_chem_shift.Ambiguity_code",
       "Assigned_chem_shift_list_ID"::integer AS "Atom_chem_shift.Assigned_chem_shift_list_ID",
       web.convert_to_numeric(ph."Val")       AS "Sample_conditions.pH",
       web.convert_to_numeric(temp."Val")     AS "Sample_conditions.Temperature_K",
       'macromolecules'                       AS database
FROM macromolecules."Atom_chem_shift" AS cs
         LEFT JOIN macromolecules."Assigned_chem_shift_list" AS csf
                   ON csf."ID" = cs."Assigned_chem_shift_list_ID" AND csf."Entry_ID" = cs."Entry_ID"
         LEFT JOIN macromolecules."Sample_condition_variable" AS ph
                   ON csf."Sample_condition_list_ID" = ph."Sample_condition_list_ID" AND
                      ph."Entry_ID" = cs."Entry_ID" AND ph."Type" = 'pH'
         LEFT JOIN macromolecules."Sample_condition_variable" AS temp
                   ON csf."Sample_condition_list_ID" = temp."Sample_condition_list_ID" AND
                      temp."Entry_ID" = cs."Entry_ID" AND temp."Type" = 'temperature' AND temp."Val_units" = 'K'
UNION
SELECT cs."Entry_ID"                          AS "Atom_chem_shift.Entry_ID",
       "Entity_ID"::integer                   AS "Atom_chem_shift.Entity_ID",
       "Comp_index_ID"::integer               AS "Atom_chem_shift.Comp_index_ID",
       "Comp_ID"                              AS "Atom_chem_shift.Comp_ID",
       "Atom_ID"                              AS "Atom_chem_shift.Atom_ID",
       "Atom_type"                            AS "Atom_chem_shift.Atom_type",
       cs."Val"::numeric                      AS "Atom_chem_shift.Val",
       cs."Val_err"::numeric                  AS "Atom_chem_shift.Val_err",
       "Ambiguity_code"                       AS "Atom_chem_shift.Ambiguity_code",
       "Assigned_chem_shift_list_ID"::integer AS "Atom_chem_shift.Assigned_chem_shift_list_ID",
       web.convert_to_numeric(ph."Val")       AS "Sample_conditions.pH",
       web.convert_to_numeric(temp."Val")     AS "Sample_conditions.Temperature_K",
       'metabolomics'                         AS database
FROM metabolomics."Atom_chem_shift" AS cs
         LEFT JOIN metabolomics."Assigned_chem_shift_list" AS csf
                   ON csf."ID" = cs."Assigned_chem_shift_list_ID" AND csf."Entry_ID" = cs."Entry_ID"
         LEFT JOIN metabolomics."Sample_condition_variable" AS ph
                   ON csf."Sample_condition_list_ID" = ph."Sample_condition_list_ID" AND
                      ph."Entry_ID" = cs."Entry_ID" AND ph."Type" = 'pH'
         LEFT JOIN metabolomics."Sample_condition_variable" AS temp
                   ON csf."Sample_condition_list_ID" = temp."Sample_condition_list_ID" AND
                      temp."Entry_ID" = cs."Entry_ID" AND temp."Type" = 'temperature' AND temp."Val_units" = 'K';
CREATE INDEX ON web.chem_shifts_tmp USING gin ("Atom_chem_shift.Atom_ID" gin_trgm_ops);
CREATE INDEX ON web.chem_shifts_tmp (database, "Atom_chem_shift.Atom_type", "Atom_chem_shift.Val");
CREATE INDEX ON web.chem_shifts_tmp (database, "Atom_chem_shift.Comp_ID", "Atom_chem_shift.Val");
CREATE INDEX ON web.chem_shifts_tmp (database, "Atom_chem_shift.Val");
CREATE INDEX ON web.chem_shifts_tmp (database, "Sample_conditions.pH");
CREATE INDEX ON web.chem_shifts_tmp (database, "Sample_conditions.Temperature_K");
CREATE INDEX cluster_index_tmp ON web.chem_shifts_tmp (database, "Atom_chem_shift.Atom_type",
                                                       "Atom_chem_shift.Atom_ID",
                                                       "Atom_chem_shift.Comp_ID", "Atom_chem_shift.Val",
                                                       "Sample_conditions.pH",
                                                       "Sample_conditions.Temperature_K");
--CLUSTER web.chem_shifts_tmp USING cluster_index_tmp;
ANALYZE web.chem_shifts_tmp;

BEGIN;
DROP MATERIALIZED VIEW IF EXISTS web.chem_shifts;
ALTER MATERIALIZED VIEW web.chem_shifts_tmp RENAME TO chem_shifts;
ALTER INDEX web.cluster_index_tmp RENAME TO cluster_index;
END;

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
  SELECT cc."Entry_ID", replace(cc."Formula", ' ', ''), cc."InChI_code", sm."String", cc."Formula_weight"::numeric, cc."Formula_weight"::numeric, cc."Formula_mono_iso_wt_nat"::numeric
  FROM metabolomics."Chem_comp" as cc
  LEFT JOIN metabolomics."Chem_comp_SMILES" AS sm
  ON sm."Entry_ID"=cc."Entry_ID"
  WHERE sm."Type" = 'canonical';

-- Move the new table into place
BEGIN;
ALTER TABLE IF EXISTS web.metabolomics_summary RENAME TO metabolomics_summary_old;
ALTER TABLE web.metabolomics_summary_tmp RENAME TO metabolomics_summary;
DROP TABLE IF EXISTS web.metabolomics_summary_old;
END;


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
SELECT DISTINCT bmrb_id, 'Matching PDB', pdb_id, to_tsvector(pdb_id) FROM web.pdb_link
UNION
SELECT DISTINCT "Entry_ID", 'Matching PDB', "Database_accession_code", to_tsvector("Database_accession_code") FROM macromolecules."Related_entries" WHERE "Database_name"='PDB' AND "Relationship"='BMRB Entry Tracking System'
UNION
SELECT DISTINCT "Entry_ID", 'Matching PDB', "Database_accession_code", to_tsvector("Database_accession_code") FROM macromolecules."Related_entries" WHERE "Database_name"='PDB' AND "Relationship"='BMRB Tracking System'
UNION
SELECT DISTINCT "ID", 'BMRB Entry DOI', '10.13018/BMR' || "ID", to_tsvector('10.13018/BMR' || "ID") FROM macromolecules."Entry"
UNION
SELECT DISTINCT "ID", 'BMRB Entry DOI', '10.13018/' || UPPER("ID"), to_tsvector('10.13018/' || UPPER("ID")) FROM metabolomics."Entry" WHERE "ID" like 'bmse%'
UNION
SELECT DISTINCT "ID", 'BMRB Entry DOI', '10.13018/' || UPPER("ID"), to_tsvector('10.13018/' || UPPER("ID")) FROM metabolomics."Entry" WHERE "ID" like 'bmst%'
UNION
SELECT DISTINCT "ID", 'BMRB Entry DOI', 'DOI:10.13018/BMR' || "ID", to_tsvector('DOI:10.13018/BMR' || "ID") FROM macromolecules."Entry"
UNION
SELECT DISTINCT "ID", 'BMRB Entry DOI', 'DOI:10.13018/' || UPPER("ID"), to_tsvector('DOI:10.13018/' || UPPER("ID")) FROM metabolomics."Entry" WHERE "ID" like 'bmse%'
UNION
SELECT DISTINCT "ID", 'BMRB Entry DOI', 'DOI:10.13018/' || UPPER("ID"), to_tsvector('DOI:10.13018/' || UPPER("ID")) FROM metabolomics."Entry" WHERE "ID" like 'bmst%'
UNION
SELECT DISTINCT "Entry_ID", 'InChI', "InChI_code", to_tsvector("InChI_code") FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", 'Compound description', "Descriptor", to_tsvector("Descriptor") FROM metabolomics."Chem_comp_descriptor"

-- This is here and below to make exact matches show up prior to fuzzy matches, but still allow fuzzy matches
UNION
SELECT DISTINCT "Entry_ID", 'Author provided ' || "Database_code" || ' Accession code', "Accession_code", to_tsvector("Accession_code") FROM macromolecules."Entity_db_link"
--
  WHERE "Database_code" != 'BMRB' AND "Author_supplied" = 'yes'
UNION
SELECT DISTINCT "Entry_ID", 'BLAST-linked ' || "Database_code" || ' Accession code', "Accession_code", to_tsvector("Accession_code") FROM macromolecules."Entity_db_link"
  WHERE "Database_code" != 'BMRB' AND "Author_supplied" = 'no'
UNION
SELECT DISTINCT "Entry_ID", 'Related ' || "Database_code" || ' Accession code', "Accession_code", to_tsvector("Accession_code") FROM macromolecules."Entity_db_link"
  WHERE "Database_code" != 'BMRB' AND "Author_supplied" != 'no' AND "Author_supplied" != 'yes';

INSERT INTO web.instant_extra_search_terms_tmp
-- metabolomics
SELECT DISTINCT "Entry_ID", "Name",'Systematic name' FROM metabolomics."Chem_comp_systematic_name"
UNION
SELECT DISTINCT "Entry_ID", regexp_replace("Formula", '\s', '', 'g'),'Formula' FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Chem Comp name' FROM metabolomics."Chem_comp"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Common name' FROM metabolomics."Chem_comp_common_name"
UNION
SELECT DISTINCT "Entry_ID", "String", 'SMILES' FROM metabolomics."Chem_comp_SMILES"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Entity name' FROM metabolomics."Entity"
UNION
SELECT DISTINCT "Entry_ID", "Name",'Assembly name' FROM metabolomics."Assembly"

--macromolecule
UNION
SELECT DISTINCT "Entry_ID",regexp_replace("Polymer_seq_one_letter_code", '[\n ]', '', 'g'),'Polymer sequence' FROM macromolecules."Entity"
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
BEGIN;
ALTER TABLE IF EXISTS web.instant_extra_search_terms RENAME TO instant_extra_search_terms_old;
ALTER TABLE web.instant_extra_search_terms_tmp RENAME TO instant_extra_search_terms;
DROP TABLE IF EXISTS web.instant_extra_search_terms_old;
END;

-- Create tsvector table
DROP TABLE IF EXISTS web.instant_cache_tmp;
CREATE TABLE web.instant_cache_tmp (
 id varchar(12) PRIMARY KEY,
 title text,
 citations text[],
 authors text[],
 link text,
 sub_date date,
 is_metab boolean,
 data_types jsonb,
 tsv tsvector
 );


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
 False,
 json_agg(distinct(jsonb_build_object('type', data_set."Type", 'count', data_set."Count")))
FROM macromolecules."Entry" AS entry
LEFT JOIN macromolecules."Citation" AS citation
  ON entry."ID"=citation."Entry_ID" AND citation."Class" = 'entry citation'
LEFT JOIN macromolecules."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID" AND citation_author."Citation_ID" = '1'
LEFT JOIN macromolecules."Data_set" AS data_set
  ON data_set."Entry_ID"=entry."ID"
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
 True,
 json_agg(distinct(jsonb_build_object('type', data_set."Type", 'count', data_set."Count")))
FROM metabolomics."Entry" AS entry
LEFT JOIN metabolomics."Citation" AS citation
  ON entry."ID"=citation."Entry_ID" AND citation."Class" = 'entry citation'
LEFT JOIN metabolomics."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
LEFT JOIN metabolomics."Chem_comp" AS chem_comp
  ON entry."ID"=chem_comp."Entry_ID"
LEFT JOIN metabolomics."Data_set" AS data_set
  ON data_set."Entry_ID"=entry."ID"
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
 True,
 json_agg(distinct(jsonb_build_object('type', data_set."Type", 'count', data_set."Count")))
FROM metabolomics."Entry" AS entry
LEFT JOIN metabolomics."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN metabolomics."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
LEFT JOIN metabolomics."Data_set" AS data_set
  ON data_set."Entry_ID"=entry."ID"
WHERE entry."ID" like 'bmst%'
GROUP BY entry."ID",entry."Title", entry."Submission_date";

-- Make sure nothing in procque gets into the released tables
DELETE FROM macromolecules."Entry" e USING web.procque pq WHERE e."ID" = pq.accno;

-- Processing
INSERT INTO web.instant_cache_tmp
SELECT
 accno,
 'Entry is being processed.',
 array[]::text[],
 array[]::text[],
 '/data_library/received.shtml',
 received,
 False
FROM web.procque WHERE onhold='N' AND status != 'Withdrawn';

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
FROM web.procque WHERE onhold='Y' AND status != 'Withdrawn';

-- Withdrawn
INSERT INTO web.instant_cache_tmp
SELECT
 accno,
 'Entry has been withdrawn by the author.',
 array[]::text[],
 array[]::text[],
 '/data_library/withdrawn.shtml',
 received,
 False
FROM web.procque WHERE status = 'Withdrawn';

-- Create the index on the tsvector
CREATE INDEX ON web.instant_cache_tmp USING gin(tsv);
UPDATE web.instant_cache_tmp SET tsv =
    setweight(to_tsvector(instant_cache_tmp.id), 'A') ||
    setweight(to_tsvector(array_to_string(instant_cache_tmp.authors, ' ')),
'B') ||
    setweight(to_tsvector(instant_cache_tmp.title), 'C') ||
    setweight(to_tsvector(array_to_string(instant_cache_tmp.citations, '
')), 'D');

-- Move the new table into place
BEGIN;
ALTER TABLE IF EXISTS web.instant_cache RENAME TO instant_cache_old;
ALTER TABLE web.instant_cache_tmp RENAME TO instant_cache;
DROP TABLE IF EXISTS web.instant_cache_old;
END;

-- Clean up
DROP FUNCTION web.clean_title(varchar);
GRANT ALL PRIVILEGES ON TABLE web.instant_extra_search_terms to web;
GRANT ALL PRIVILEGES ON TABLE web.instant_extra_search_terms to bmrb;
GRANT ALL PRIVILEGES ON TABLE web.instant_cache to web;
GRANT ALL PRIVILEGES ON TABLE web.instant_cache to bmrb;
GRANT ALL PRIVILEGES ON TABLE web.metabolomics_summary to web;
GRANT ALL PRIVILEGES ON TABLE web.metabolomics_summary to bmrb;
GRANT ALL PRIVILEGES ON TABLE web.pdb_link to web;
GRANT ALL PRIVILEGES ON TABLE web.pdb_link to bmrb;

GRANT USAGE ON schema web TO PUBLIC;
GRANT SELECT ON ALL TABLES IN schema web TO PUBLIC;
ALTER DEFAULT PRIVILEGES IN schema web GRANT SELECT ON TABLES TO PUBLIC;