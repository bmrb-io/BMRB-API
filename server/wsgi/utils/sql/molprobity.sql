-- Molprobity schema

CREATE SCHEMA IF NOT EXISTS molprobity;


DROP TABLE IF EXISTS molprobity.oneline_tmp;
CREATE table molprobity.oneline_tmp (
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

-- Temp table with duplicates
CREATE TEMP TABLE tmp_table
AS
SELECT *
FROM molprobity.oneline_tmp
WITH NO DATA;

-- Load data
\copy tmp_table FROM '/websites/extras/files/pdb/molprobity/oneline_files/combined/allonelinenobuild.out.csv' DELIMITER ':' CSV;
\copy tmp_table FROM '/websites/extras/files/pdb/molprobity/oneline_files/combined/allonelinebuild.out.csv' DELIMITER ':' CSV;
\copy tmp_table FROM '/websites/extras/files/pdb/molprobity/oneline_files/combined/allonelineorig.out.csv' DELIMITER ':' CSV;

-- Populate real table with duplicates excluded
INSERT INTO molprobity.oneline_tmp
SELECT DISTINCT ON (pdb, model, hydrogenations, molprobity_flips, backbone_trim_state) *
FROM tmp_table
ORDER BY pdb, model, hydrogenations, molprobity_flips, backbone_trim_state;

-- Move the new table into place
ALTER TABLE IF EXISTS molprobity.oneline RENAME TO oneline_old;
ALTER TABLE molprobity.oneline_tmp RENAME TO oneline;
DROP TABLE IF EXISTS molprobity.oneline_old;
DROP TABLE tmp_table;

-- Residue table
DROP TABLE IF EXISTS molprobity.residue_tmp;
CREATE table molprobity.residue_tmp (
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
structure_validation_residue_list_id integer
);

\copy molprobity.residue_tmp FROM '/websites/extras/files/pdb/molprobity/residue_files/everything.csv' DELIMITER ':' CSV;
CREATE INDEX ON molprobity.residue_tmp (pdb);

-- Move the new table into place
ALTER TABLE IF EXISTS molprobity.residue RENAME TO residue_old;
ALTER TABLE molprobity.residue_tmp RENAME TO residue;
DROP TABLE IF EXISTS molprobity.residue_old;

-- Set up permissions
GRANT USAGE ON SCHEMA molprobity TO web;
GRANT SELECT ON ALL TABLES IN SCHEMA molprobity TO web;
