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

structure_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);"""

nonstructure_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog
WHERE status LIKE 'rel%%'
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);"""