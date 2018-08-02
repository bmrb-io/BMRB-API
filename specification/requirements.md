# Requirement document: 

## Validation Techniques
1. Webserver and API synchronized as the user updates the data on the web interface; NMR-STAR file generated at the API server each time its synchronized
2. Method to validate the dictionary update; should not break the existing system 
3. Human or automated testing framework to check the interface (UI) works correctly
4. Maintain audit/revision record for the dictionary. It should be in the dictionary

## Requirements
1. Allow interface/editing entries outside of web interface (command line deposition)
2. Allow decoupling dictionary version from web interface
3. Allow decoupling web server from API development
4. Instant data validation
5. Data consistency checking 
6. Orchid ID validation
7. Email id validation
8. Depositor will be able to modify previously entered data in later stage 

## General Issues
1.	Interface with ETS
2.	Interface with validation system
3.	Distribution to PDBj-BMRB
4.	Interface with wwPDB
5.	Creating development, testing, and production versions 
6.	Avoid wwPDB problem where the system cannot be tested, because valid PDB codes are generated?
7.	In what formats will data be accepted
8.	Will depositions be locked and not editable after submission?
9.	Will depositors interact through annotators after completing depositions as is now?
10. Deposition security (limit access to valid depositor or BMRB staff)
11. Ease of access by BMRB staff to trouble shoot issues for users
12. Industrial versus academic depositors

## Specific Issues
### UI navigation
1.  User has ability to jump from one section to any other section of the deposition including data upload. The user is not forced to enter data in a pre-defined order
2.  Navigation tool is available that describes the different sections of the deposition and ability to jump from section to section
3.  Sections with mandatory fields are clearly distinguished from sections that have no non-mandatory fields
4.  Mandatory fields are clearly defined
5.  Mandatory fields that have been filled in are clearly distinguished from those that have not been completed
6.  Entry hold choices
7.  Fields that have fixed enumerations
8.  Fields with open enumerations
9.  Mandatory fields that are usually applicable, but in some cases may not have true values (pH in pure organic solvents)

### Data upload/deletion
1.  What kinds of data to accept?

### Source of information driving deposition interface
1.  NMR-STAR dictionary
2.  Conditional mandatory linkages (files?)
3.  Information field linkages - fields that can use a pull down list populated from other sections


## Use Cases
1.  Somewhat defined by the BMRB entries listed below for testing
2.  

## Test Plan
### BMRB entries to use for student testing
1.  Single chain protein only (<entry number?>)
2.  Single chain protein with one organic ligand (<entry number?>)
3.  Single chain protein with metal ligand and organic ligand (<entry number?>)
4.  Protein homodimer (<entry number?>)
5.  Protein heterodimer (<entry number?>)
6.  Protein polynucleic acid complex (<entry number?>)
7.  RNA monomer (<entry number?>)
8.  RNA duplex (<entry number?>)
9.  RNA/DNA hybrid monomer (<entry number?>)
10. DNA duplex (<entry number?>)
11. RNA monomer with ligand (<entry number?>)
12. Chemical shifts (<entry number?>)
13. Coupling constants (<entry number?>)
14. Relaxation data (<entry number?>)

### Testing protocol
1.  Students use data from entries to populate deposition
  - each student uses 4-5 entries and the entries used rotates to keep fresh eyes looking for bugs
2.  Students also 'monkey' test fields and sections of the deposition not commonly used (just type in junk to quickly test functionality)
3.  Senior staff also test system
4.  All issues discovered entered into tracking system
5.  Issues retested by person reporting the issue, as fixes are reported
6.  Test over and over again as the system evolves and is updated
7.  NMRFAM personnel asked to review and provide feedback on UI
8.  As system nears completion, ask a few outside users (BMRB curators?) to test system

