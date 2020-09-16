released_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);"""

original_release_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM logtable
WHERE newstatus LIKE 'rel'
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);"""

structure_total_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""

structure_aditnmr_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 7
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""

structure_onedep_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 12
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""

structure_bmrbdep_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND nmr_dep_code = restart_id
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""







nonstructure_total_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""

nonstructure_aditnmr_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 7
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""

nonstructure_onedep_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 12
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""

nonstructure_bmrbdep_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND nmr_dep_code = restart_id
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);
"""