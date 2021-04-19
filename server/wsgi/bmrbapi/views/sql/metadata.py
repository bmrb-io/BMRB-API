released_in_year: str = """
SELECT lt.year, count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, date_part('year', logdate) AS year
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum, year) AS lt ON el.depnum = lt.depnum
WHERE lt.depnum IS NOT NULL
GROUP BY lt.year
ORDER BY lt.year;"""

original_release_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE el.status LIKE 'rel%'
GROUP BY date_part('year', release_date)
ORDER BY date_part('year', release_date);"""

structure_total_in_year: str = """
SELECT date_part('year', release_date), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum,
     unnest(string_to_array(el.pdb_code, ' ')) s(pdb_code)
WHERE el.pdb_code IS NOT NULL
  AND el.pdb_code NOT IN ('?', '.', '')
  AND s.pdb_code !~ '^[0-9]+$'
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
