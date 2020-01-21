pdb_bmrb_map_text = """
SELECT UPPER(pdb_id) || ' ' || string_agg(bmrb_id, ',' ORDER BY bmrb_id) AS string
from (SELECT pdb_id, bmrb_id, 'exact' AS link_type, null AS comment
      FROM web.pdb_link
      UNION
      SELECT "Database_accession_code", "Entry_ID", 'author', "Relationship"
      FROM macromolecules."Related_entries"
      WHERE "Database_name" = 'PDB'
        AND "Relationship" != 'Exact'
      UNION
      SELECT "Accession_code", "Entry_ID", 'blast', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Database_code" = 'PDB'
      UNION
      SELECT "Accession_code", "Entry_ID", 'assembly', "Entry_details"
      FROM macromolecules."Assembly_db_link"
      WHERE "Database_code" = 'PDB') AS sub
WHERE link_type like %s AND pdb_id IS NOT NULL
GROUP BY UPPER(pdb_id)
ORDER BY UPPER(pdb_id);
"""

pdb_bmrb_map_json = """
SELECT UPPER(pdb_id) as pdb_id, array_agg(bmrb_id ORDER BY bmrb_id::int) AS bmrb_ids
from (SELECT pdb_id, bmrb_id, 'exact' AS link_type, null AS comment
      FROM web.pdb_link
      UNION
      SELECT "Database_accession_code", "Entry_ID", 'author', "Relationship"
      FROM macromolecules."Related_entries"
      WHERE "Database_name" = 'PDB'
        AND "Relationship" != 'Exact'
      UNION
      SELECT "Accession_code", "Entry_ID", 'blast', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Database_code" = 'PDB'
      UNION
      SELECT "Accession_code", "Entry_ID", 'assembly', "Entry_details"
      FROM macromolecules."Assembly_db_link"
      WHERE "Database_code" = 'PDB') AS sub
WHERE link_type like %s AND pdb_id IS NOT NULL
GROUP BY UPPER(pdb_id)
ORDER BY UPPER(pdb_id);
"""

bmrb_pdb_map_text = """
SELECT bmrb_id || ' ' || string_agg(pdb_id, ',' ORDER BY pdb_id) AS string
from (SELECT pdb_id, bmrb_id, 'exact' AS link_type, null AS comment
      FROM web.pdb_link
      UNION
      SELECT "Database_accession_code", "Entry_ID", 'author', "Relationship"
      FROM macromolecules."Related_entries"
      WHERE "Database_name" = 'PDB'
        AND "Relationship" != 'Exact'
      UNION
      SELECT "Accession_code", "Entry_ID", 'blast', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Database_code" = 'PDB'
      UNION
      SELECT "Accession_code", "Entry_ID", 'assembly', "Entry_details"
      FROM macromolecules."Assembly_db_link"
      WHERE "Database_code" = 'PDB') AS sub
WHERE link_type like %s AND pdb_id IS NOT NULL
GROUP BY bmrb_id
ORDER BY bmrb_id::int;"""

bmrb_pdb_map_json = """
SELECT bmrb_id, array_agg(pdb_id ORDER BY pdb_id) AS pdb_ids
from (SELECT pdb_id, bmrb_id, 'exact' AS link_type, null AS comment
      FROM web.pdb_link
      UNION
      SELECT "Database_accession_code", "Entry_ID", 'author', "Relationship"
      FROM macromolecules."Related_entries"
      WHERE "Database_name" = 'PDB'
        AND "Relationship" != 'Exact'
      UNION
      SELECT "Accession_code", "Entry_ID", 'blast', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Database_code" = 'PDB'
      UNION
      SELECT "Accession_code", "Entry_ID", 'assembly', "Entry_details"
      FROM macromolecules."Assembly_db_link"
      WHERE "Database_code" = 'PDB') AS sub
WHERE link_type like %s AND pdb_id IS NOT NULL
GROUP BY bmrb_id
ORDER BY bmrb_id::int;"""


bmrb_uniprot_map_json = """
SELECT bmrb_id, array_agg(uniprot_id) AS "uniprot_ids"
FROM web.uniprot_mappings
WHERE link_type like %s
GROUP BY bmrb_id
ORDER BY bmrb_id
"""

bmrb_uniprot_map_text = """
SELECT bmrb_id || ' ' || string_agg(uniprot_id, ',' ORDER BY uniprot_id) AS string
FROM web.uniprot_mappings
WHERE link_type like %s
GROUP BY bmrb_id
ORDER BY bmrb_id"""

uniprot_bmrb_map_json = """
SELECT uniprot_id, array_agg(bmrb_id)
FROM web.uniprot_mappings
WHERE link_type like %s
GROUP BY uniprot_id
ORDER BY uniprot_id
"""

uniprot_bmrb_map_text = """
SELECT uniprot_id || ' ' || string_agg(bmrb_id, ',' ORDER BY bmrb_id) AS string
FROM web.uniprot_mappings
WHERE link_type like %s
GROUP BY uniprot_id
ORDER BY uniprot_id
"""

uniprot_uniprot_map = """
SELECT DISTINCT(uniprot_id || ' ' || uniprot_id) AS string
FROM web.uniprot_mappings
GROUP BY uniprot_id
ORDER BY uniprot_id || ' ' || uniprot_id"""
