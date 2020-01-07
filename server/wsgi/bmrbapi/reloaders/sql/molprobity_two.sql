-- Populate real table with duplicates excluded
INSERT INTO molprobity.oneline_tmp
SELECT DISTINCT ON (pdb, model, hydrogenations, molprobity_flips, backbone_trim_state) *
FROM tmp_table
ORDER BY pdb, model, hydrogenations, molprobity_flips, backbone_trim_state;

CREATE INDEX ON molprobity.residue_tmp (pdb);

-- Move the new tables into place
ALTER TABLE IF EXISTS molprobity.oneline RENAME TO oneline_old;
ALTER TABLE molprobity.oneline_tmp RENAME TO oneline;
DROP TABLE IF EXISTS molprobity.oneline_old;
DROP TABLE tmp_table;

ALTER TABLE IF EXISTS molprobity.residue RENAME TO residue_old;
ALTER TABLE molprobity.residue_tmp RENAME TO residue;
DROP TABLE IF EXISTS molprobity.residue_old;

-- Set up permissions
GRANT USAGE ON SCHEMA molprobity TO web;
GRANT SELECT ON ALL TABLES IN SCHEMA molprobity TO web;