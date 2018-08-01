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

## Use Cases

