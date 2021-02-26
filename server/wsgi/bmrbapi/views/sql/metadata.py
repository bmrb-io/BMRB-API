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

# Below are the query grid queries

bmrb_query_grid_initial: str = """
SELECT entity."Polymer_type",
       COUNT(DISTINCT cs."Entry_ID")                                                AS total_entries,
       COUNT(cs.*)                                                                  AS total_shifts,
       COUNT(cs.*)
       FILTER (WHERE cs."Atom_type" = 'C' AND cs."Atom_isotope_number" = '13')      AS carbon_shift,
       COUNT(DISTINCT cs."Entry_ID")
       FILTER (WHERE cs."Atom_type" = 'C' AND cs."Atom_isotope_number" = '13')      AS carbon_entries,
       COUNT(cs.*)
       FILTER (WHERE cs."Atom_type" = 'H' AND cs."Atom_isotope_number" = '1')       AS hydrogen_shift,
       COUNT(DISTINCT cs."Entry_ID")
       FILTER (WHERE cs."Atom_type" = 'H' AND cs."Atom_isotope_number" = '1')       AS hydrogen_entries,
       COUNT(cs.*)
       FILTER (WHERE cs."Atom_type" = 'N' AND cs."Atom_isotope_number" = '15')      AS nitrogen_shift,
       COUNT(DISTINCT cs."Entry_ID")
       FILTER (WHERE cs."Atom_type" = 'N' AND cs."Atom_isotope_number" = '15')      AS nitrogen_entries,
       COUNT(cs.*)
       FILTER (WHERE cs."Atom_type" = 'P' AND cs."Atom_isotope_number" = '31')      AS phosphorus_shift,
       COUNT(DISTINCT cs."Entry_ID")
       FILTER (WHERE cs."Atom_type" = 'P' AND cs."Atom_isotope_number" = '31')      AS phosphorus_entries,
       COUNT(cs.*)
       FILTER (WHERE NOT (cs."Atom_type" = 'P' AND cs."Atom_isotope_number" = '31') AND
                     NOT (cs."Atom_type" = 'C' AND cs."Atom_isotope_number" = '13') AND
                     NOT (cs."Atom_type" = 'N' AND cs."Atom_isotope_number" = '15') AND
                     NOT (cs."Atom_type" = 'H' AND cs."Atom_isotope_number" = '1')) AS other_shift,
       COUNT(DISTINCT cs."Entry_ID")
       FILTER (WHERE NOT (cs."Atom_type" = 'P' AND cs."Atom_isotope_number" = '31') AND
                     NOT (cs."Atom_type" = 'C' AND cs."Atom_isotope_number" = '13') AND
                     NOT (cs."Atom_type" = 'N' AND cs."Atom_isotope_number" = '15') AND
                     NOT (cs."Atom_type" = 'H' AND cs."Atom_isotope_number" = '1')) AS other_entries,
       cc.coupling_constants                                                        AS coupling_constants,
       cc.entries                                                                   AS coupling_constant_entries
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."Atom_chem_shift" AS cs
                   ON cs."Entry_ID" = entity."Entry_ID" AND cs."Entity_ID" = entity."ID"
         LEFT JOIN (SELECT entity."Polymer_type",
                           COUNT(cc.*)                   AS coupling_constants,
                           COUNT(DISTINCT cc."Entry_ID") AS entries
                    FROM macromolecules."Entity" AS entity
                             LEFT JOIN macromolecules."Coupling_constant" AS cc
                                       ON cc."Entry_ID" = entity."Entry_ID" AND
                                          (cc."Entity_ID_1" = entity."ID" OR cc."Entity_ID_2" = entity."ID")
                    WHERE entity."Polymer_type" IS NOT NULL
                    GROUP BY entity."Polymer_type") AS cc ON cc."Polymer_type" = entity."Polymer_type"
WHERE entity."Polymer_type" IS NOT NULL
GROUP BY entity."Polymer_type", cc.coupling_constants, cc.entries;


-- RDCs
SELECT entity."Polymer_type", COUNT(rdc.*) AS rdcs, COUNT(DISTINCT rdc."Entry_ID") AS entries
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."RDC" AS rdc
                   ON rdc."Entry_ID" = entity."Entry_ID" AND
                      (rdc."Entity_ID_1" = entity."ID" OR rdc."Entity_ID_2" = entity."ID")
WHERE entity."Polymer_type" IS NOT NULL
GROUP BY entity."Polymer_type";


-- R1s
SELECT "Polymer_type", COUNT("Val") AS t1s, COUNT(DISTINCT "Entry_ID") AS entries
FROM (SELECT entity."Polymer_type" AS "Polymer_type", t1."Entry_ID" AS "Entry_ID", t1."Val" AS "Val"
      FROM macromolecules."Entity" AS entity
               LEFT JOIN macromolecules."T1" AS t1
                         ON t1."Entry_ID" = entity."Entry_ID" AND t1."Entity_ID" = entity."ID"
      WHERE entity."Polymer_type" IS NOT NULL
        AND t1."Val" IS NOT NULL
      UNION ALL
      SELECT entity."Polymer_type" AS "Polymer_type", ar."Entry_ID" AS "Entry_ID", ar."Auto_relaxation_val" AS "Val"
      FROM macromolecules."Entity" AS entity
               LEFT JOIN macromolecules."Auto_relaxation" AS ar
                         ON ar."Entry_ID" = entity."Entry_ID" AND ar."Entity_ID" = entity."ID"
               LEFT JOIN macromolecules."Auto_relaxation_list" AS arl ON arl."ID" = ar."Auto_relaxation_list_ID"
      WHERE entity."Polymer_type" IS NOT NULL
        AND arl."Relaxation_val_units" IS NOT NULL
        AND arl."Common_relaxation_type_name" = 'R1') AS subq
GROUP BY "Polymer_type";

-- T2s
SELECT "Polymer_type", COUNT("Val") AS t2s, COUNT(DISTINCT "Entry_ID") AS entries
FROM (SELECT entity."Polymer_type" AS "Polymer_type", t2."Entry_ID" AS "Entry_ID", t2."Rex_val" AS "Val"
      FROM macromolecules."Entity" AS entity
               LEFT JOIN macromolecules."T2" AS t2
                         ON t2."Entry_ID" = entity."Entry_ID" AND t2."Entity_ID" = entity."ID"
      WHERE entity."Polymer_type" IS NOT NULL
        AND t2."Rex_val" IS NOT NULL
      UNION ALL
      SELECT entity."Polymer_type" AS "Polymer_type", ar."Entry_ID" AS "Entry_ID", ar."Auto_relaxation_val" AS "Val"
      FROM macromolecules."Entity" AS entity
               LEFT JOIN macromolecules."Auto_relaxation" AS ar
                         ON ar."Entry_ID" = entity."Entry_ID" AND ar."Entity_ID" = entity."ID"
               LEFT JOIN macromolecules."Auto_relaxation_list" AS arl ON arl."ID" = ar."Auto_relaxation_list_ID"
      WHERE entity."Polymer_type" IS NOT NULL
        AND arl."Relaxation_val_units" IS NOT NULL
        AND arl."Common_relaxation_type_name" = 'R2') AS subq
GROUP BY "Polymer_type";

-- NOEs
SELECT entity."Polymer_type", COUNT(noe.*) AS noes, COUNT(DISTINCT noe."Entry_ID") AS entries
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."Heteronucl_NOE" AS noe
                   ON noe."Entry_ID" = entity."Entry_ID"
WHERE entity."Polymer_type" IS NOT NULL
GROUP BY entity."Polymer_type";


-- order params
SELECT entity."Polymer_type",
       COUNT(order_param.*)                   AS order_parameters,
       COUNT(DISTINCT order_param."Entry_ID") AS entries
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."Order_param" AS order_param
                   ON order_param."Entry_ID" = entity."Entry_ID"
WHERE "Order_param_val" IS NOT NULL
  AND entity."Polymer_type" IS NOT NULL
GROUP BY entity."Polymer_type";


-- H exchange
SELECT entity."Polymer_type",
       COUNT(h_exchange.*)                   AS h_exchange_rates,
       COUNT(DISTINCT h_exchange."Entry_ID") AS entries
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."H_exch_rate" AS h_exchange
                   ON h_exchange."Entry_ID" = entity."Entry_ID"
WHERE "Val" IS NOT NULL
  AND entity."Polymer_type" IS NOT NULL
GROUP BY entity."Polymer_type";

-- H exchange protection factors
SELECT entity."Polymer_type",
       COUNT(h_exchange_protection.*)                   AS h_exchange_protection_factors,
       COUNT(DISTINCT h_exchange_protection."Entry_ID") AS entries
FROM macromolecules."Entity" AS entity
         LEFT JOIN macromolecules."H_exch_protection_factor" AS h_exchange_protection
                   ON h_exchange_protection."Entry_ID" = entity."Entry_ID"
WHERE "Val" IS NOT NULL
  AND entity."Polymer_type" IS NOT NULL
GROUP BY entity."Polymer_type";
"""