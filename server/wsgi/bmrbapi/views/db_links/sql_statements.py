pdb_bmrb_map_author = """
SELECT pdb_id || ' ' || string_agg(bmrb_id, ',' ORDER BY bmrb_id)
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
WHERE link_type = %s AND pdb_id IS NOT NULL
GROUP BY pdb_id
ORDER BY pdb_id;
"""

bmrb_pdb_map_exact = """
SELECT bmrb_id || ' ' || string_agg(pdb_id, ',' ORDER BY pdb_id)
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
WHERE link_type = %s AND pdb_id IS NOT NULL
GROUP BY bmrb_id
ORDER BY bmrb_id::int;"""