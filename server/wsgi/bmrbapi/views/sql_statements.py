metabolomics_instant_query_one = '''
SELECT instant_cache.id,
       title,
       citations,
       authors,
       link,
       sub_date,
       ms.formula,
       ms.inchi,
       ms.smiles,
       ms.average_mass,
       ms.molecular_weight,
       ms.monoisotopic_mass
FROM web.instant_cache
         LEFT JOIN web.metabolomics_summary AS ms
                   ON instant_cache.id = ms.id
WHERE tsv @@ plainto_tsquery(%s)
  AND is_metab = 'True'
  AND ms.id IS NOT NULL
ORDER BY instant_cache.id = %s DESC, is_metab, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''

metabolomics_instant_query_two = """
SELECT set_limit(.5);
SELECT DISTINCT ON (instant_cache.id) term,
                        termname,
                        '1'::int AS sml,
                        tt.id,
                        title,
                        citations,
                        authors,
                        link,
                        sub_date,
                        is_metab,
                        NULL     AS "formula",
                        NULL     AS "inchi",
                        NULL     AS "smiles",
                        NULL     AS "average_mass",
                        NULL     AS "molecular_weight",
                        NULL     AS "monoisotopic_mass"
FROM web.instant_cache
         LEFT JOIN web.instant_extra_search_terms AS tt
                   ON instant_cache.id = tt.id
WHERE tt.identical_term @@ plainto_tsquery(%s)
  AND is_metab = 'True'
UNION
SELECT *
FROM (
         SELECT DISTINCT ON (instant_cache.id) term,
                                 termname,
                                 similarity(tt.term, %s) AS sml,
                                 tt.id,
                                 title,
                                 citations,
                                 authors,
                                 link,
                                 sub_date,
                                 is_metab,
                                 ms.formula,
                                 ms.inchi,
                                 ms.smiles,
                                 ms.average_mass,
                                 ms.molecular_weight,
                                 ms.monoisotopic_mass
         FROM web.instant_cache
                  LEFT JOIN web.instant_extra_search_terms AS tt
                            ON instant_cache.id = tt.id
                  LEFT JOIN web.metabolomics_summary AS ms
                            ON instant_cache.id = ms.id
         WHERE tt.term %% %s
           AND tt.identical_term IS NULL
           AND ms.id IS NOT NULL
         ORDER BY id, similarity(tt.term, %s) DESC) AS y
WHERE is_metab = 'True'"""

macromolecules_instant_query_one = '''
SELECT id, title, citations, authors, link, sub_date
FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s)
  AND is_metab = 'False'
ORDER BY id = %s DESC, is_metab, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;
'''

macromolecules_instant_query_two = '''
SELECT set_limit(.5);
SELECT DISTINCT ON (instant_cache.id) term,
                                      termname,
                                      '1'::int AS sml,
                                      tt.id,
                                      title,
                                      citations,
                                      authors,
                                      link,
                                      sub_date,
                                      is_metab
FROM web.instant_cache
         LEFT JOIN web.instant_extra_search_terms AS tt
                   ON instant_cache.id = tt.id
WHERE tt.identical_term @@ plainto_tsquery(%s)
UNION
SELECT *
FROM (
         SELECT DISTINCT ON (instant_cache.id) term,
                                               termname,
                                               similarity(tt.term, %s) AS sml,
                                               tt.id,
                                               title,
                                               citations,
                                               authors,
                                               link,
                                               sub_date,
                                               is_metab
         FROM web.instant_cache
                  LEFT JOIN web.instant_extra_search_terms AS tt
                            ON instant_cache.id = tt.id
         WHERE tt.term %% %s
           AND tt.identical_term IS NULL
         ORDER BY id, similarity(tt.term, %s) DESC) AS y
WHERE is_metab = 'False'
ORDER BY sml DESC
LIMIT 75;
'''


combined_instant_query_one = '''
SELECT id, title, citations, authors, link, sub_date
FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s)
ORDER BY id = %s DESC, is_metab, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;
'''

combined_instant_query_two = '''
SELECT set_limit(.5);
SELECT DISTINCT ON (instant_cache.id) term,
                                      termname,
                                      '1'::int AS sml,
                                      tt.id,
                                      title,
                                      citations,
                                      authors,
                                      link,
                                      sub_date,
                                      is_metab
FROM web.instant_cache
         LEFT JOIN web.instant_extra_search_terms AS tt
                   ON instant_cache.id = tt.id
WHERE tt.identical_term @@ plainto_tsquery(%s)
UNION
SELECT *
FROM (
         SELECT DISTINCT ON (instant_cache.id) term,
                                               termname,
                                               similarity(tt.term, %s) AS sml,
                                               tt.id,
                                               title,
                                               citations,
                                               authors,
                                               link,
                                               sub_date,
                                               is_metab
         FROM web.instant_cache
                  LEFT JOIN web.instant_extra_search_terms AS tt
                            ON instant_cache.id = tt.id
         WHERE tt.term %% %s
           AND tt.identical_term IS NULL
         ORDER BY id, similarity(tt.term, %s) DESC) AS y
ORDER BY sml DESC
LIMIT 75;
'''