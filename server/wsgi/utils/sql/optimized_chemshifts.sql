DROP TABLE IF EXISTS fast_cs_search;
CREATE TABLE fast_cs_search (
  "Entry_ID" varchar(10),
  "Entity_ID" integer,
  "Comp_index_ID" integer,
  "Comp_ID" varchar(12),
  "Atom_ID" varchar(12),
  "Atom_type" varchar(12),
  "Val" numeric,
  "Val_err" numeric,
  "Ambiguity_code" integer,
  "Assigned_chem_shift_list_ID" integer,
  macromolecules boolean
);

INSERT INTO fast_cs_search
SELECT
"Entry_ID"::int,"Entity_ID"::int,"Comp_index_ID"::int,"Comp_ID","Atom_ID","Atom_type","Val"::numeric,"Val_err"::numeric,"Ambiguity_code"::integer,"Assigned_chem_shift_list_ID"::integer,TRUE
FROM macromolecules."Atom_chem_shift";

INSERT INTO fast_cs_search
SELECT
"Entry_ID","Entity_ID"::int,"Comp_index_ID"::int,"Comp_ID","Atom_ID","Atom_type","Val"::numeric,"Val_err"::numeric,"Ambiguity_code","Assigned_chem_shift_list_ID",FALSE
FROM metabolomics."Atom_chem_shift";

CREATE INDEX ON fast_cs_search ("Atom_ID", "Comp_ID");
CREATE INDEX ON fast_cs_search ("Val");
ANALYZE fast_cs_search;
