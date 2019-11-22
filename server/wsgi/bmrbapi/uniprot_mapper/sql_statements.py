author_and_pdb_links = '''
SELECT ent."Entry_ID"                                              AS bmrb_id,
       ent."ID"                                                    AS entity_id,
       upper(coalesce(ea."PDB_chain_ID", ent."Polymer_strand_ID")) AS pdb_chain,
       upper(pdb_id)                                               AS pdb_id,
       CASE
           WHEN dbl."Accession_code" IS NOT NULL THEN 'Author supplied'
           ELSE null
           END                                                     as link_type,
       dbl."Accession_code"                                        AS uniprot_id,
       "Polymer_seq_one_letter_code"                               AS sequence,
       ent."Details"
FROM macromolecules."Entity" AS ent
         LEFT JOIN web.pdb_link AS pdb ON pdb.bmrb_id = ent."Entry_ID"
         LEFT JOIN macromolecules."Entity_db_link" AS dbl
                   ON dbl."Entry_ID" = ent."Entry_ID" AND ent."ID" = dbl."Entity_ID"
         LEFT JOIN macromolecules."Entity_assembly" AS ea
                   ON ea."Entry_ID" = ent."Entry_ID" AND ea."Entity_ID" = ent."ID"
WHERE "Polymer_seq_one_letter_code" IS NOT NULL
  AND "Polymer_seq_one_letter_code" != ''
  AND ent."Polymer_type" = 'polypeptide(L)'
  AND (dbl."Accession_code" IS NULL
    OR (dbl."Author_supplied" = 'yes' AND
        (lower(dbl."Database_code") = 'unp' OR lower(dbl."Database_code") = 'uniprot' OR
         lower(dbl."Database_code") = 'sp')))
ORDER BY ent."Entry_ID"::int, ent."ID"::int;
'''

create_mappings_table = '''
DROP TABLE IF EXISTS web.uniprot_mappings_old CASCADE;
DROP MATERIALIZED VIEW IF EXISTS web.hupo_psi_id_tmp_old;

CREATE TABLE IF NOT EXISTS web.uniprot_mappings_tmp
(
    id                     serial primary key,
    bmrb_id                text,
    entity_id              int,
    pdb_chain              text,
    pdb_id                 text,
    link_type              text,
    uniprot_id             text,
    protein_sequence       text,
    details                text
);
'''

bulk_insert = '''
INSERT INTO web.uniprot_mappings_tmp (bmrb_id, entity_id, pdb_chain, pdb_id, link_type, uniprot_id, protein_sequence,
                                      details)
VALUES %s'''

insert_clean_ready = '''
INSERT INTO web.uniprot_mappings_tmp (bmrb_id, entity_id, pdb_chain, pdb_id, link_type, uniprot_id, protein_sequence, details)
    (SELECT dbl."Entry_ID",
            dbl."Entity_ID"::int,
            null,
            pdb_id,
            'Sequence mapping',
            REPLACE (dbl."Accession_code", '.', '-'),
            ent."Polymer_seq_one_letter_code",
            ent."Details"
     FROM macromolecules."Entity_db_link" AS dbl
              LEFT JOIN macromolecules."Entity" AS ent
                        ON dbl."Entry_ID" = ent."Entry_ID" AND ent."ID" = dbl."Entity_ID"
              LEFT JOIN macromolecules."Entity_assembly" AS ea
                        ON ea."Entry_ID" = dbl."Entry_ID" AND ea."Entity_ID" = dbl."Entity_ID"
              LEFT JOIN web.pdb_link AS pdb ON pdb.bmrb_id = ent."Entry_ID"
     WHERE dbl."Author_supplied" = 'no'
       AND dbl."Database_code" = 'SP'
    );

DELETE FROM web.uniprot_mappings_tmp WHERE uniprot_id = '' OR uniprot_id IS NULL;
UPDATE web.uniprot_mappings
SET uniprot_id = REPLACE(uniprot_id, '.', '-')
WHERE uniprot_id LIKE '%.%';

UPDATE web.uniprot_mappings
SET uniprot_id = 'P9WKD3' WHERE uniprot_id = 'P9WKD3[43 - 307]';
UPDATE web.uniprot_mappings
SET uniprot_id = 'P05386' WHERE uniprot_id = 'P05386,P05387';

DELETE FROM web.uniprot_mappings WHERE uniprot_id = 'TmpAcc';
DELETE FROM web.uniprot_mappings_tmp
WHERE id IN (
    SELECT
        id
    FROM (
        SELECT
            id,
            ROW_NUMBER() OVER w AS rnum
        FROM web.uniprot_mappings_tmp
        WINDOW w AS (
            PARTITION BY bmrb_id, pdb_id, entity_id, link_type, uniprot_id
            ORDER BY id
        )

    ) t
WHERE t.rnum > 1);
CREATE UNIQUE INDEX ON web.uniprot_mappings_tmp (bmrb_id, pdb_id, entity_id, link_type, uniprot_id);


CREATE MATERIALIZED VIEW IF NOT EXISTS web.hupo_psi_id_tmp AS
(
SELECT uni.id,
       uni.uniprot_id,
       'bmrb:' || bmrb_id                   AS source,
       entity."Polymer_seq_one_letter_code" AS "regionSequenceExperimental",
       'ECO:0001238'                        AS "experimentType",
       CASE
           WHEN cit."PubMed_ID" IS NOT NULL THEN 'pubmed:' || cit."PubMed_ID"
           WHEN cit."DOI" IS NOT NULL THEN 'doi:' || cit."DOI"
           ELSE null END                    AS "experimentReference",
       (SELECT "Date"
        from macromolecules."Release"
        WHERE "Entry_ID" = entity."Entry_ID"
        ORDER BY "Release_number"::int DESC
        LIMIT 1)                            AS "lastModified",
       uni.link_type                        AS "regionDefinitionSource"
FROM web.uniprot_mappings_tmp AS uni
         LEFT JOIN macromolecules."Entity" AS entity
                   ON entity."Entry_ID" = bmrb_id AND entity."ID"::int = entity_id
         LEFT JOIN macromolecules."Entry" AS entry ON entry."ID" = bmrb_id
         LEFT JOIN macromolecules."Citation" AS cit ON cit."Entry_ID" = entry."ID"
    AND cit."Class" = 'entry citation'
ORDER BY uniprot_id);
CREATE UNIQUE INDEX ON web.hupo_psi_id_tmp (uniprot_id, id, source, "regionSequenceExperimental",
                                                                    "experimentType", "experimentReference",
                                                                    "lastModified", "regionDefinitionSource");

 -- Permissions
GRANT ALL PRIVILEGES ON web.hupo_psi_id_tmp to web;
GRANT ALL PRIVILEGES ON web.hupo_psi_id_tmp to bmrb;
GRANT ALL PRIVILEGES ON web.uniprot_mappings_tmp to web;
GRANT ALL PRIVILEGES ON web.uniprot_mappings_tmp to bmrb;

-- Move table and view into place
ALTER TABLE IF EXISTS web.uniprot_mappings RENAME TO uniprot_mappings_old;
ALTER TABLE web.uniprot_mappings_tmp RENAME TO uniprot_mappings;
DROP TABLE IF EXISTS web.uniprot_mappings_old CASCADE;

ALTER MATERIALIZED VIEW IF EXISTS web.hupo_psi_id RENAME TO hupo_psi_id_tmp_old;
ALTER MATERIALIZED VIEW web.hupo_psi_id_tmp RENAME TO hupo_psi_id;
DROP MATERIALIZED VIEW IF EXISTS hupo_psi_id_tmp_old;
'''