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
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE el.status LIKE 'rel%%'
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);"""

withdrawn_entries_in_year: str = """
SELECT lt.year, count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, date_part('year', min(logdate)) AS year
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status NOT LIKE 'rel%%'
  AND lt.depnum IS NOT NULL
GROUP BY lt.year
ORDER BY lt.year;"""

entries_released_this_year_since_withdrawn: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'awd'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status NOT LIKE 'rel%%'
  AND lt.depnum IS NOT NULL
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);"""

structure_aditnmr_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE el.status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 7
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

structure_onedep_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE el.status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 12
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

structure_bmrbdep_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status LIKE 'rel%%'
  AND nmr_dep_code = restart_id
  AND pdb_code IS NOT NULL
  AND pdb_code NOT IN ('?', '.', '')
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

structure_total_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status LIKE 'rel%%'
  AND el.pdb_code IS NOT NULL
  AND el.pdb_code NOT IN ('?', '.', '')
  AND el.pdb_code !~ '^[0-9]+$'
  AND (nmr_dep_code = restart_id OR LENGTH(nmr_dep_code) = 12 OR LENGTH(nmr_dep_code) = 7)
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

nonstructure_total_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status LIKE 'rel%%'
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

nonstructure_aditnmr_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 7
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

nonstructure_onedep_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status LIKE 'rel%%'
  AND LENGTH(nmr_dep_code) = 12
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""

nonstructure_bmrbdep_in_year: str = """
SELECT date_part('year', logdate), count(*)
FROM entrylog AS el
         LEFT JOIN
     (SELECT depnum, min(logdate) AS logdate
      FROM logtable
      WHERE newstatus = 'rel'
      GROUP BY depnum) AS lt ON el.depnum = lt.depnum
WHERE status LIKE 'rel%%'
  AND nmr_dep_code = restart_id
  AND (pdb_code IS NULL OR pdb_code IN ('?', '.', ''))
GROUP BY date_part('year', logdate)
ORDER BY date_part('year', logdate);
"""
