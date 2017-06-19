-- Molprobity table

DROP TABLE IF EXISTS web.molprobity_oneline;
DROP TABLE IF EXISTS web.molprobity_residue;

CREATE table web.molprobity_oneline (
fullpdbname text,
pdb varchar(4),
model integer,
hydrogenations text,
molprobity_flips text,
backbone_trim_state text,
assembly_id text,
clashscore numeric,
clashscore_less40 numeric,
cbeta_outlier integer,
numcbeta integer,
rota_less1pct integer,
numrota integer,
ramaoutlier integer,
ramaallowed integer,
ramafavored integer,
numrama integer,
numbadbonds integer,
numbonds integer,
pct_badbonds numeric,
pct_resbadbonds numeric,
numbadangles integer,
numangles integer,
pct_badangles numeric,
pct_resbadangles numeric,
molprobityscore numeric,
numpperp_outlier integer,
numpperp integer,
numsuite_outlier integer,
numsuite integer,
entry_id text,
structure_val_oneline_list_id integer,
macromolecule_types text,

    PRIMARY KEY (pdb, model, hydrogenations, molprobity_flips, backbone_trim_state)
);

CREATE TEMP TABLE tmp_table
AS
SELECT *
FROM web.molprobity_oneline
WITH NO DATA;

\copy tmp_table FROM '/websites/extras/files/pdb/molprobity/oneline_files/combined/allonelinenobuild.out.csv' DELIMITER ':' CSV;
\copy tmp_table FROM '/websites/extras/files/pdb/molprobity/oneline_files/combined/allonelinebuild.out.csv' DELIMITER ':' CSV;
\copy tmp_table FROM '/websites/extras/files/pdb/molprobity/oneline_files/combined/allonelineorig.out.csv' DELIMITER ':' CSV;

INSERT INTO web.molprobity_oneline
SELECT DISTINCT ON (pdb, model, hydrogenations, molprobity_flips, backbone_trim_state) *
FROM tmp_table
ORDER BY pdb, model, hydrogenations, molprobity_flips, backbone_trim_state;

DROP TABLE tmp_table;

CREATE table web.molprobity_residue (
filename text,
pdb text,
model integer,
hydrogen_positions text,
molprobity_flips text,
cyrange_core_flag text,
two_letter_chain_id text,
pdb_strand_id varchar(1),
pdb_residue_no integer,
pdb_ins_code text,
pdb_residue_name text,
assembly_id text,
entity_assembly_id text,
entity_id text,
comp_id text,
comp_index_id text,
clash_value text,
clash_source_pdb_atom_name text,
clash_destination_pdb_atom_name text,
clash_destination_pdb_strand_id text,
clash_destination_pdb_residue_no text,
clash_destination_pdb_ins_code text,
clash_destination_pdb_residue_name text,
cbeta_deviation_value text,
rotamer_score text,
rotamer_name text,
ramachandran_phi text,
ramachandran_psi text,
ramachandran_score text,
ramachandran_evaluation text,
ramachandran_type text,
bond_outlier_count integer,
worst_bond text,
worst_bond_value numeric,
worst_bond_sigma numeric,
angle_outlier_count integer,
worst_angle text,
worst_angle_value numeric,
worst_angle_sigma numeric,
rna_phosphate_perpendicular_outlier text,
rna_suitness_score text,
rna_suite_conformer text,
rna_suite_triage text,
max_b_factor numeric,
tau_angle text,
omega_dihedral text,
disulfide_chi1 text,
disulfide_chi2 text,
disulfide_chi3 text,
disulfide_ss_angle text,
disulfide_ss text,
disulfide_ss_angle_prime text,
disulfide_chi2prime text,
disulfide_chi1prime text,
outlier_count_separate_geometry integer,
outlier_count integer,
entry_id text,
structure_validation_residue_list_id integer --,

    --PRIMARY KEY (pdb, model, pdb_residue_no, hydrogen_positions, molprobity_flips, cyrange_core_flag)
);

-- This is probably way too slow. We'll have to deal with duplicates upstream for now
/*
CREATE TEMP TABLE tmp_table
AS
SELECT *
FROM web.molprobity_residue
WITH NO DATA;

\copy web.molprobity_residue FROM '/websites/extras/files/pdb/molprobity/residue_files/everything.csv' DELIMITER ':' CSV;

INSERT INTO web.molprobity_residue
SELECT DISTINCT ON (pdb, model, hydrogen_positions, molprobity_flips, cyrange_core_flag) *
FROM tmp_table
ORDER BY pdb, model, hydrogen_positions, molprobity_flips, cyrange_core_flag;

DROP TABLE tmp_table;*/

\copy web.molprobity_residue FROM '/websites/extras/files/pdb/molprobity/residue_files/everything.csv' DELIMITER ':' CSV;
CREATE INDEX ON web.molprobity_residue (pdb);
