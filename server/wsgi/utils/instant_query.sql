CREATE OR REPLACE FUNCTION clean_title(varchar) RETURNS varchar AS
$body$
BEGIN
    RETURN replace(regexp_replace($1, E'[\\n\\r]+', ' ', 'g' ), '  ', ' ');
END;
$body$
IMMUTABLE LANGUAGE plpgsql;

SELECT
 entry."ID",
 clean_title(entry."Title"),
 array_agg(DISTINCT clean_title(citation."Title")),
 array_agg(DISTINCT citation_author."Given_name" || ' ' || COALESCE(Replace(citation_author."Middle_initials", '.', ''),'') || ' ' || citation_author."Family_name")
FROM macromolecules."Entry" as entry
LEFT JOIN macromolecules."Citation" AS citation
  ON entry."ID"=citation."Entry_ID"
LEFT JOIN macromolecules."Citation_author" AS citation_author
  ON entry."ID"=citation_author."Entry_ID"
WHERE
  LOWER(entry."Title") like %s OR
  LOWER(citation."Title") like %s OR
  LOWER(citation_author."Given_name" || ' ' || Replace(citation_author."Middle_initials", '.', '') || ' ' || citation_author."Family_name" || ' ' || citation_author."Given_name" || ' ' || citation_author."Family_name") like %s
GROUP BY entry."ID",entry."Title"
ORDER BY
  INSTR(entry."Title", %s),
  entry."ID" DESC LIMIT 30;
