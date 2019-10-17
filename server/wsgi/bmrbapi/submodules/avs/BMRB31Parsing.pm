#       Copyright Hunter Moseley, 2000. All rights reserved.
#       Written by Hunter Moseley 8/1/2000
#       "Mostly" ReWritten by Gurmukh Sahota 02/01/2001
#	Modified by Hunter Moseley 6/12/2001
#       Modified by Gurmukh Sahota 06/18/2001
#                fixed the cmap_conversion_hash (some wrong names)
#       Modified by Gurmukh Sahota 07/01/2001
#                added hack for name_array where inconsistent with current residue shifts (write_bmrb_file)
#                added hack for non-existant _Atom_chem_shift.Atom_type (using first letter of shift name) (write_bmrb_file)
#                modified the multiplicity hash for increased atomType inclusions and some typo's.
#                modified deMultiplicate so that it now accepts -1 residues and demultiplicates accordingly.
#
#	90% Rewritten by Hunter Moseley 11/17/2001
#       Copyright Hunter Moseley, 2001. All rights reserved.
#	Modified by Hunter Moseley 3/18/2002 (800 more lines).
#       Copyright Gurmukh Sahota, 2002. All rights reserved.
#	Modified by Gurmukh Sahota 05/13/2002.  Adding coupling_constant and secondary_structure saveframes
#                     and fixed some "exists" bugs and a last in the entity
#
#	Modified by David Tolmie (BMRB)  05/03/2005.
#       Changed the NMR-STAR tags from version 2.1 to
#      version 3.0 format.  The below mappings show
#      the Save Frame name and the 2.1 to 3.0 mappings.
#
#
#	A complete rewrite of the code by Hunter Moseley 07/30/2005
#       Copyright Hunter Moseley, 2005. All rights reserved.
#	Through out most of the original code.
#	Through out all the changes made by David Tolmie.
#	This is a complete rewrite of the base code, with major changes to the underlying data structures.
#	
#
#  BMRBParsing.pm
#	Contains subroutines for reading and writing BMRB files.
#
#	Subroutines:
#		read_bmrb_file - reads a bmrb file and returns a hash of records (Residue is a hash).
#		write_bmrb_file - prints a bmrb file out to $filename
#
package BMRB31Parsing;
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw();
@EXPORT_OK = qw(clone read_bmrb_file write_bmrb_file deMultiplicate residueNameofIndex convert_aa3to1 is_known_atom_name convert_aa1to3 find_entity sort_shift_names);
%EXPORT_TAGS = ( ALL => [@EXPORT_OK] );

use strict;
#use Dumpvalue qw(:ALL);
#my $dumper    = new Dumpvalue;

#
# useful hashes and subroutines
#

my %aa_name_conversion3to1 = ( "ala" => "A", "arg" => "R", "asn" => "N", "asp" => "D",
			   "cys" => "C", "gln" => "Q", "glu" => "E", "gly" => "G",
			   "his" => "H", "ile" => "I", "leu" => "L", "lys" => "K",
			   "met" => "M", "phe" => "F", "pro" => "P", "ser" => "S",
			   "thr" => "T", "trp" => "W", "tyr" => "Y", "val" => "V",
			   "a"   => "A", "r"   => "R", "n"   => "N", "d"   => "D", 
			   "c"   => "C", "q"   => "Q", "e"   => "E", "g"   => "G",
			   "h"   => "H", "i"   => "I", "l"   => "L", "k"   => "K",
			   "m"   => "M", "f"   => "F", "p"   => "P", "s"   => "S",
			   "t"   => "T", "w"   => "W", "y"   => "Y", "v"   => "V"); 
sub convert_aa3to1
  {
  my $aa = shift @_;
  if (exists $aa_name_conversion3to1{lc($aa)})
    { return $aa_name_conversion3to1{lc($aa)}; }

  return $aa;
  }

my %aa_name_conversion1to3 = ("A"   => "Ala", "R"   => "Arg", "N"   => "Asn", "D"   => "Asp",
			   "C"   => "Cys", "Q"   => "Gln", "E"   => "Glu", "G"   => "Gly",
			   "H"   => "His", "I"   => "Ile", "L"   => "Leu", "K"   => "Lys",
			   "M"   => "Met", "F"   => "Phe", "P"   => "Pro", "S"   => "Ser",
			   "T"   => "Thr", "W"   => "Trp", "Y"   => "Tyr", "V"   => "Val",
			   "ALA" => "Ala", "ARG" => "Arg", "ASN" => "Asn", "ASP" => "Asp",
			   "CYS" => "Cys", "GLN" => "Gln", "GLU" => "Glu", "GLY" => "Gly",
			   "HIS" => "His", "ILE" => "Ile", "LEU" => "Leu", "LYS" => "Lys",
			   "MET" => "Met", "PHE" => "Phe", "PRO" => "Pro", "SER" => "Ser",
			   "THR" => "Thr", "TRP" => "Trp", "TYR" => "Tyr", "VAL" => "Val" ); 
sub convert_aa1to3
  {
  my $aa = shift @_;
  if (exists $aa_name_conversion1to3{uc($aa)})
    { return $aa_name_conversion1to3{uc($aa)}; }

  return $aa;
  }


sub find_entity
  {
  my $bmrb_hlist = shift @_;
  my $res_name = shift @_;

  foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
    {
    if (exists $$entity{"rlist"}{$res_name})
      { return $entity; }
    }

  return 0;
  }


my %BMRB_shift_name_ordering = ( "H" => 1, "HA" => 2, "HA2" => 3, "HA3" => 4, "HB" => 5, "HB2" => 6, "HB3" => 7, "HG" => 8,
				 "HG1" => 9, "HG12" => 10, "HG13" => 11, "HG2" => 12, "HG3" => 13, "HD1" => 14, "HD2" => 15,
				 "HD21" => 16, "HD22" => 17, "HD3" => 18, "HE" => 19, "HE1" => 20, "HE2" => 21, "HE21" => 22,
				 "HE22" => 23, "HE3" => 24, "HZ" => 25, "HZ2" => 26, "HZ3" => 27, "HH" => 28, "HH11" => 29,
				 "HH12" => 30, "HH2" => 31, "HH21" => 32, "HH22" => 33, "C" => 34, "CA" => 35, "CB" => 36,
				 "CG" => 37, "CG1" => 38, "CG2" => 39, "CD" => 40, "CD1" => 41, "CD2" => 42, "CE" => 43,
				 "CE1" => 44, "CE2" => 45, "CE3" => 46, "CZ" => 47, "CZ2" => 48, "CZ3" => 49, "CH2" => 50,
				 "N" => 51, "ND1" => 52, "ND2" => 53, "NE" => 54, "NE1" => 55, "NE2" => 56, "NZ" => 57,
				 "NH1" => 58, "NH2" => 59 );
sub shift_name_CMP
  { return $BMRB_shift_name_ordering{$a} <=> $BMRB_shift_name_ordering{$b}; }

sub sort_shift_names
  { return (sort shift_name_CMP (@_)); }


my %degeneracy_shift_conversion = 
  ( "ala" => { "H" => "H", "HA" => "HA", "HB" => "HB", "C" => "C", "CA" => "CA", "CB" => "CB", "N" => "N" },
    "arg" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HG2" => "HG",
	       "HG3" => "HG", "HD" => "HD", "HD2" => "HD", "HD3" => "HD", "HE" => "HE", "HH" => "HH", "HH11" => "HH",
	       "HH12" => "HH", "HH21" => "HH", "HH22" => "HH", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG",
	       "CD" => "CD", "CZ" => "CZ", "N" => "N", "NE" => "NE", "NH" => "NH", "NH1" => "NH", "NH2" => "NH" },
    "asn" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HD2" => "HD2", "HD21" => "HD2",
	       "HD22" => "HD2", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG", "N" => "N", "ND2" => "ND2" },
    "asp" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "C" => "C", "CA" => "CA",
	       "CB" => "CB", "CG" => "CG", "N" => "N" },
    "cys" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "C" => "C",
	       "CA" => "CA", "CB" => "CB", "N" => "N" },
    "gln" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HG2" => "HG",
	       "HG3" => "HG", "HE2" => "HE2", "HE21" => "HE2", "HE22" => "HE2", "C" => "C", "CA" => "CA", "CB" => "CB",
	       "CG" => "CG", "CD" => "CD", "N" => "N", "NE2" => "NE2" },
    "glu" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HG2" => "HG",
	       "HG3" => "HG", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG", "CD" => "CD", "N" => "N" },
    "gly" => { "H" => "H", "HA" => "HA", "HA2" => "HA", "HA3" => "HA", "C" => "C", "CA" => "CA", "N" => "N" },
    "his" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HD1" => "HD1", "HD2" => "HD2",
	       "HE1" => "HE1", "HE2" => "HE2", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG", "CD2" => "CD2",
	       "CE1" => "CE1", "N" => "N", "ND1" => "ND1", "NE2" => "NE2" },
    "ile" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HG1" => "HG", "HG12" => "HG", "HG13" => "HG", 
	       "HG2" => "HG", "HD"=>"HD", "HD1" => "HD", "C" => "C", "CA" => "CA", "CB" => "CB", "CG1" => "CG", "CG2" => "CG",
	       "CD1" => "CD", "CD"=>"CD", "N" => "N" },
    "leu" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HD" => "HD",
	       "HD1" => "HD", "HD2" => "HD", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG", "CD" => "CD",
	       "CD1" => "CD", "CD2" => "CD", "N" => "N" },
    "lys" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HG2" => "HG",
	       "HG3" => "HG", "HD" => "HD", "HD2" => "HD", "HD3" => "HD", "HE" => "HE", "HE2" => "HE", "HE3" => "HE",
	       "HZ" => "HZ", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG", "CD" => "CD", "CE" => "CE",
	       "N" => "N", "NZ" => "NZ" },
    "met" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HG2" => "HG",
	       "HG3" => "HG", "HE" => "HE", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG", "CE" => "CE",
	       "N" => "N" },
    "phe" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HD" => "HD", "HD1" => "HD",
	       "HD2" => "HD", "HE1" => "HE", "HE2" => "HE", "HZ" => "HZ", "C" => "C", "CA" => "CA", "CB" => "CB",
	       "CG" => "CG", "CD" => "CD", "CD1" => "CD", "CD2" => "CD", "CE1" => "CE", "CE2" => "CE", "CZ" => "CZ",
	       "N" => "N" },
    "pro" => { "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "HG2" => "HG", "HG3" => "HG",
	       "HD" => "HD", "HD2" => "HD", "HD3" => "HD", "C" => "C", "CA" => "CA", "CB" => "CB", "CG" => "CG",
	       "CD" => "CD", "N" => "N" },
    "ser" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HG" => "HG", "C" => "C",
	       "CA" => "CA", "CB" => "CB", "N" => "N" },
    "thr" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HG1" => "HG1", "HG2" => "HG2", "C" => "C", "CA" => "CA",
	       "CB" => "CB", "CG2" => "CG2", "N" => "N" },
    "trp" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HD1" => "HD1", "HE1" => "HE1",
	       "HE3" => "HE3", "HZ2" => "HZ2", "HZ3" => "HZ3", "HH2" => "HH2", "C" => "C", "CA" => "CA", "CB" => "CB",
	       "CG" => "CG", "CD1" => "CD1", "CD2" => "CD2", "CE2" => "CE2", "CE3" => "CE3", "CZ2" => "CZ2",
	       "CZ3" => "CZ3", "CH2" => "CH2", "N" => "N", "NE1" => "NE1" },
    "tyr" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HB2" => "HB", "HB3" => "HB", "HD" => "HD", "HD1" => "HD",
	       "HD2" => "HD", "HE" => "HE", "HE1" => "HE", "HE2" => "HE", "HH" => "HH", "C" => "C", "CA" => "CA",
	       "CB" => "CB", "CG" => "CG", "CD" => "CD", "CD1" => "CD", "CD2" => "CD", "CE" => "CE", "CE1" => "CE",
	       "CE2" => "CE", "CZ" => "CZ", "N" => "N" },
    "val" => { "H" => "H", "HA" => "HA", "HB" => "HB", "HG" => "HG", "HG1" => "HG", "HG2" => "HG", "C" => "C",
	       "CA" => "CA", "CB" => "CB", "CG" => "CG", "CG1" => "CG", "CG2" => "CG", "N" => "N" } );

sub is_known_atom_name
  {
  my $res_type = lc(&convert_aa1to3(shift @_));
  my $atom_name = shift @_;

  return 1 if (exists $degeneracy_shift_conversion{$res_type} && exists $degeneracy_shift_conversion{$res_type}{$atom_name});
  return 0;
  }



my %multiplicity = ("A" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 1, "CA" => 1, "CB" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "C" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "CA" => 1, "CB" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "SG" => 1, "HG" => 1},
		    "D" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 1, "HD2" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "OD" => 2, "OD1" => 1, "OD2" => 1},
		    "E" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 2, "HG2" => 1, "HG3" => 1, "HE" => 1, "HE2" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "OE" => 2, "OE1" => 1, "OE2" => 1},
		    "F" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 2, "HD1" => 1, "HD2" => 1, "HE" => 2, "HE1" => 1, "HE2" => 1, "HZ" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 2, "CE" => 2, "CZ" => 1, "CD1" => 1, "CD2" => 1, "CE1" => 1, "CE2" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "G" => { "H" => 1, "HN" => 1, "HA2" => 1, "HA3" => 1, "CA" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "H" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 2, "HD1" => 1, "HD2" => 1, "HE" => 2, "HE1" => 1, "HE2" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "CE" => 1, "CD2" => 1, "CE1" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "ND" => 1, "ND1" => 1, "NE" => 1, "NE2" => 1},
		    "I" => {"H" => 1, "HN" => 1, "HA" => 1, "HB" => 1, "HG" => 3, "HG12" => 1, "HG13" => 1, "HG2" => 1, "HD" => 1, "HD1" => 1, "CA" => 1, "CB" => 1, "CG" => 2, "CD" => 1, "CG1" => 1, "CG2" => 1, "CD1" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "K" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 2, "HG2" => 1, "HG3" => 1, "HD" => 2, "HD2" => 1, "HD3" => 1, "HE" => 2, "HE2" => 1, "HE3" => 1, "HZ" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "CE" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "NZ" => 1},
		    "L" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 2, "HD1" => 1, "HD2" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 2, "CE" => 1, "CD1" => 1, "CD2" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "M" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 1, "HG2" => 1, "HG3" => 1, "HE" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "CE" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "SD" => 1},
		    "N" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 2, "HD2" => 2, "HD21" => 1, "HD22" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CE" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "ND" => 1, "ND2" => 1, "OD" => 1, "OD1" => 1},
		    "P" => { "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 2, "HG2" => 1, "HG3" => 1, "HD" => 2, "HD2" => 1, "HD3" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "Q" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 2, "HG2" => 1, "HG3" => 1, "HE" => 2, "HE2" => 2, "HE21" => 1, "HE22" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "NE" =>1, "NE2" => 1, "OE" => 1, "OE1" => 1},
		    "R" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 2, "HG2" => 1, "HG3" => 1, "HD" => 2, "HD2" => 1, "HD3" => 1, "HE" => 1, "HH" => 4, "HH1" => 2, "HH11" => 1, "HH12" => 1, "HH2" => 2, "HH21" => 1, "HH22" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 1, "CZ" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "NE" => 1, "NH" => 2, "NH1" => 1, "NH2" => 1},
		    "S" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HG" => 1, "CA" => 1, "CB" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "OG" => 1},
		    "T" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 1, "HG" =>2, "HG1" => 1, "HG2" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CG2" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "OG" => 1, "OG1" => 1},
		    "V" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 1, "HG" => 2, "HG1" => 1, "HG2" => 1, "CA" => 1, "CB" => 1, "CG" => 2, "CG1" => 1, "CG2" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1},
		    "W" => { "H" => 1, "HN" => 1, "HA" => 1, "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 1, "HD1" => 1, "HE" => 2, "HE1" => 1, "HE3" => 1, "HZ" => 2, "HZ2" => 1, "HZ3" => 1, "HH" => 1, "HH2" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 2, "CE" => 2, "CZ" => 2, "CH" => 1, "CD1" => 1, "CD2" => 1, "CE2" => 1, "CE3" => 1, "CZ2" => 1, "CZ3" => 1, "CH2" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "NE" => 1, "NE1" => 1},
		    "Y" => { "H" => 1, "HN" => 1, "HA" => 1,  "HB" => 2, "HB2" => 1, "HB3" => 1, "HD" => 2, "HD1" => 1, "HD2" => 1, "HE" => 2, "HE1" => 1, "HE2" => 1, "HH" => 1, "CA" => 1, "CB" => 1, "CG" => 1, "CD" => 2, "CE" => 2, "CZ" => 1, "CD1" => 1, "CD2" => 1, "CE1" => 1, "CE2" => 1, "C" => 1, "CO" => 1, "N" => 1, "N15" => 1, "OH" => 1}
		    );

####################################### deMultiplicate ########################################
# Input   : a bmrb_hlist type                                                                 # 
# Output  : a bmrb_hlist type                                                                 #
# Purpose : To return only the proper multiplicity of the bmrb_hlist                          #
###############################################################################################
sub deMultiplicate
  {
  my $bmrb_hlist = shift @_;

  foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
    {
    foreach my $residue (values %{$$entity{"rlist"}})
      {
      foreach my $shift_name_real (keys %{$$residue{"shifts"}})
	{
	my $suffix = "";
	my $shift_name = ($shift_name_real =~ /^(.*?)(\-1)?$/)[0];
	$suffix = "-1"   if ($shift_name ne $shift_name_real);
	if ( ($suffix ne "") && ( exists $$residue{"prev"}) && ( exists $multiplicity{&convert_aa3to1($$entity{"rlist"}{$$residue{"prev"}}{"aa"})}{$shift_name} ) )
	  {
	  splice(@{$$residue{"shifts"}{$shift_name_real}{"list"}}, $multiplicity{&convert_aa3to1($$entity{"rlist"}{$$residue{"prev"}}{"aa"})}{$shift_name});
	  splice(@{$$residue{"shifts"}{$shift_name_real}{"idlist"}}, $multiplicity{&convert_aa3to1($$entity{"rlist"}{$$residue{"prev"}}{"aa"})}{$shift_name});
	  splice(@{$$residue{"shifts"}{$shift_name_real}{"list_id_list"}}, $multiplicity{&convert_aa3to1($$entity{"rlist"}{$$residue{"prev"}}{"aa"})}{$shift_name});
	  }
	elsif ( exists $multiplicity{&convert_aa3to1($$residue{"aa"})}{$shift_name_real} )
	  {
	  splice(@{$$residue{"shifts"}{$shift_name_real}{"list"}}, $multiplicity{&convert_aa3to1($$residue{"aa"})}{$shift_name_real});
	  splice(@{$$residue{"shifts"}{$shift_name_real}{"idlist"}}, $multiplicity{&convert_aa3to1($$residue{"aa"})}{$shift_name_real});
	  splice(@{$$residue{"shifts"}{$shift_name_real}{"list_id_list"}}, $multiplicity{&convert_aa3to1($$residue{"aa"})}{$shift_name_real});
	  }
	}
      }
    }
  }


# residueNameofIndex
#    Returns the residue name of the residue with the inputted index
#
# Parameters:
#	$name_array - ref to name_array.
#	$index - index of residue.
#
sub residueNameofIndex
  {
  my $name_array = shift @_;
  my $index = shift @_;
  
  foreach my $residue_name (@$name_array)
    {
    $residue_name =~ /^([A-Za-z]+)(\d+)$/;
    if ($2 == $index)
      { return $residue_name; }
    }
  return "";
  }


# clone
#   clones a bmrb_hlist.
#
#        $original_hlist - the original $bmrb_hlist
#        $cloned_hlist   - the cloned $bmrb_hlist
sub clone
  {
  my $original_hlist = shift @_;
  my $cloned_hlist = shift @_;

  # generic cloning code
  my @clone_stack;
  push @clone_stack, { "type" => "HASH", "clone" => $cloned_hlist, "range" => [ keys %$original_hlist ], "index" => 0, "original" => $original_hlist }; 

  while(@clone_stack)
    {
    my $index = $clone_stack[$#clone_stack]{"index"};

    if ($index < @{$clone_stack[$#clone_stack]{"range"}}) # clone a part of the current hash or array
      {
      # get new value
      my $test_value;
      if ($clone_stack[$#clone_stack]{"type"} eq "HASH")
	{ $test_value = $clone_stack[$#clone_stack]{"original"}{$clone_stack[$#clone_stack]{"range"}[$index]}; }
      elsif ($clone_stack[$#clone_stack]{"type"} eq "ARRAY")
	{ $test_value = $clone_stack[$#clone_stack]{"original"}[$index]; }

      my $test_ref = ref($test_value);
      if ($test_ref eq "HASH") # test value is a hash
	{ push @clone_stack, {"type" => "HASH", "clone" => {}, "range" => [ keys %$test_value ], "index" => 0, "original" => $test_value }; }
      elsif ($test_ref eq "ARRAY") # test value is an array
	{ push @clone_stack, {"type" => "ARRAY", "clone" => [], "range" => $test_value, "index" => 0, "original" => $test_value }; }
      elsif ($clone_stack[$#clone_stack]{"type"} eq "HASH") # clone section is a hash
	{
	$clone_stack[$#clone_stack]{"clone"}{$clone_stack[$#clone_stack]{"range"}[$index]} = $test_value;
	$clone_stack[$#clone_stack]{"index"}++;
	}
      else # clone section is an array
	{
	$clone_stack[$#clone_stack]{"clone"}[$index] = $test_value;
	$clone_stack[$#clone_stack]{"index"}++;
	}
      }
    else # pop finished cloned section.
      {
      if (@clone_stack > 1)
	{
	my $index = $clone_stack[$#clone_stack - 1]{"index"};

	if($clone_stack[$#clone_stack - 1]{"type"} eq "HASH") # handle hashes
	  { $clone_stack[$#clone_stack - 1]{"clone"}{$clone_stack[$#clone_stack - 1]{"range"}[$index]} = $clone_stack[$#clone_stack]{"clone"}; }
	else # handle arrays
	  { $clone_stack[$#clone_stack - 1]{"clone"}[$index] = $clone_stack[$#clone_stack]{"clone"}; }
	}
      
      pop @clone_stack;
      if (@clone_stack)
	{ $clone_stack[$#clone_stack]{"index"}++; }
      }
    }
  
  return;
  }


#
# Save frame descriptions for translating these specific save frames into usable hash structures
#

# Assembly frame description
my $assembly_sf_fields = {
  "_Assembly.ID" => { "hash_field" => 1, "name" => "assembly_id", "order" => 3 },
  "_Assembly.Name" => { "name" => "name", "order" => 2 },
  "_Assembly.Number_of_components" => { "name" => "num_entities", "order" => 1 },
  };
my $assembly_sf_entity_loop_fields = {
  "entity_list" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Entity_assembly.Entity_ID" => { "hash_field" => 2, "name" => "entity_id", "required" => 1 },
  "_Entity_assembly.Entity_assembly_name" => { "name" => "common_name", "required" => 1, },
  "_Entity_assembly.Entity_label" => { "name" => "label", "required" => 0, },
  "_Entity_assembly.Assembly_ID" => { "name" => "assembly_id", "required" => 1 }
  };
my $assembly_frame_description = { "type" => "assembly", "type_tag" => "_Assembly.Sf_category", "code" => "molecular_assembly", "code_tag" => "_Assembly.Sf_framecode", 
				   "list_name" => "assembly_list", "list_id" => "assembly_id", "list_ids_sub" => \&get_sort_list_ids, "single_field_description" => $assembly_sf_fields, 
				   "process_sub" => \&process_frame, "create_sub" => \&create_assembly_frame, "description_sub" => \&create_frame_description,
				   "loops" => [  { "name" => "entity_loop", "fields" => $assembly_sf_entity_loop_fields, "start_top" => 1 } ] };

# Entity frame description
my $entity_sf_fields = {
  "_Entity.ID" => { "hash_field" => 1, "name" => "entity_id", "order" => 4 },
  "_Entity.Name" => { "name" => "common_name", "order" => 3 },
  "_Entity.Type" => { "name" => "molecule_type", "order" => 2 },
  "_Entity.Polymer_type" => { "name" => "polymer_class", "order" => 1 },
  "_Entity.Polymer_seq_one_letter_code" => { "name" => "sequence", "format" => \&format_sequence },
  "_Entity.Number_of_monomers" => { "name" => "residue_count" },
  "_Entity.Ambiguous_conformational_states" => { },
  "_Entity.Ambiguous_chem_comp_sites" => { },
  "_Entity.Nstd_monomer" => {},
  "_Entity.Nstd_chirality" => {},
  "_Entity.Nstd_linkage" => {},
  "_Entity.Paramagnetic" => {},
  "_Entity.Thiol_state" => {}
  };
#
sub format_sequence
  {
  my $sequence = shift @_;

  my $text = "\n;\n";
  my @text_lines = ("", ";");
  for(my $x=0; $x < length($sequence); $x += 20)
    {
    if (($x + 20) > length($sequence))
      { $text .= substr($sequence, $x) . "\n"; }
    else
      { $text .=  substr($sequence, $x, 20) . "\n"; }
    }
  
  $text .=  ";";
  return $text;
  }
my $entity_sf_sequence_loop_fields = {
  "rlist" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "name" => { "hash_field" => 2, "compose" => sub { my ($cols, $elems) = @_; return $$cols[$$elems{"_Entity_comp_index.Comp_ID"}] . $$cols[$$elems{"_Entity_comp_index.ID"}]; }, "required" => 0, "sort" => sub { my ($a_num) = ($a =~ /(\d+)/); my ($b_num) = ($b =~ /(\d+)/);  $a_num <=> $b_num; } },
  "_Entity_comp_index.ID" => { "name" => "index", "required" => 1, },
  "_Entity_comp_index.Comp_ID" => { "name" => "aa", "conversion" => 0, "required" => 1, "format" => \&convert_aa1to3 },
  "_Entity_comp_index.Author_seq_code" => { "name" => "author_index", "required" => 0, },
  "_Entity_comp_index.Entity_ID" => { "name" => "entity_id", "required" => 0, "skip_field" => 1 }
  };
  
my $entity_frame_description = { "type" => "entity", "type_tag" => "_Entity.Sf_category", "code" => sub { my $vals = shift @_; if (exists $$vals{"common_name"}) { return $$vals{"common_name"}; } else { return "null"; }  }, "code_tag" => "_Entity.Sf_framecode", 
				 "list_name" => "entity_list", "list_id" => "entity_id", "list_ids_sub" => \&get_sort_list_ids, "single_field_description" => $entity_sf_fields, 
				 "process_sub" => \&process_entity_frame, "create_sub" => \&create_frame, "description_sub" => \&create_frame_description,
				 "loops" => [  { "name" => "sequence_loop", "fields" => $entity_sf_sequence_loop_fields, "test" => "rlist" } ] };

# assigned_chemical_shift frame description 
my $acs_sf_shift_loop_fields = {
  "entity_list" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Atom_chem_shift.Entity_ID" => { "hash_field" => 2, "name" => "entity_id", "required" => 1, "skip_field" => 1 }, 
  "rlist" => { "hash_field" => 3, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "residue_name" => { "hash_field" => 4, "compose" => sub { my ($cols, $elems) = @_; return $$cols[$$elems{"_Atom_chem_shift.Comp_ID"}] . $$cols[$$elems{"_Atom_chem_shift.Comp_index_ID"}]; }, "required" => 0, "skip_field" => 1, "sort" => sub { my ($a_num) = ($a =~ /(\d+)/); my ($b_num) = ($b =~ /(\d+)/);  $a_num <=> $b_num; } },
  "shifts" => { "hash_field" => 5, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Atom_chem_shift.Atom_ID" => { "hash_field" => 6, "name" => "atom_name", "conversion" => 0, "required" => 1, "sort" => \&shift_name_CMP }, 
  "_Atom_chem_shift.ID" => { "name" => "idlist", "required" => 1, "type" => "ARRAY" }, 
  "_Atom_chem_shift.Comp_index_ID" => { "name" => "index", "required" => 1 }, 
  "_Atom_chem_shift.Comp_ID" => { "name" => "aa", "required" => 0, "conversion" => 0, "format" => \&convert_aa1to3 },
  "_Atom_chem_shift.Auth_seq_ID" => { "name" => "author_index", "required" => 0 }, 
  "_Atom_chem_shift.Atom_type" => { "name" => "atom_type", "required" => 1 }, 
  "_Atom_chem_shift.Val" => { "name" => "list", "required" => 1, "type" => "ARRAY" }, 
  "_Atom_chem_shift.Val_err" => { "name" => "error", "required" => 0 }, 
  "_Atom_chem_shift.Ambiguity_code" => { "name" => "ambiguity_code", "required" => 1 }, 
  "_Atom_chem_shift.Assigned_chem_shift_list_ID" => { "name" => "list_id_list", "required" => 1, "type" => "ARRAY" } 
  };
my $acs_sf_ambiguity_loop_fields = {
  "ambiguity_lists" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Ambiguous_atom_chem_shift.Ambiguous_shift_set_ID" => { "hash_field" => 2, "name" => "set_id", "required" => 1 },
  "_Ambiguous_atom_chem_shift.Atom_chem_shift_ID" => { "name" => "list", "required" => 1, "type" => "ARRAY" },
  "_Ambiguous_atom_chem_shift.Assigned_chem_shift_list_ID" => { "name" => "list_id", "required" => 1, "type" => "ARRAY" }
  };
my $assigned_chemical_shifts_frame_description = { "type" => "assigned_chemical_shifts", "type_tag" => "_Assigned_chem_shift_list.Sf_category", "code" => "assigned_chemical_shifts", "code_tag" => "_Assigned_chem_shift_list.Sf_framecode", 
						   "list_id" => "list_id", "list_id_field" => "_Assigned_chem_shift_list.ID", "list_ids_sub" => \&get_sort_acs_list_ids,
						   "process_sub" => \&process_assigned_chemical_shifts_frame, "create_sub" => \&create_assigned_chemical_shifts_frame,
						   "description_sub" => \&create_assigned_chemical_shifts_frame_description,
						   "loops" => [ { "name" => "chemical_shifts_loop", "fields" => $acs_sf_shift_loop_fields, "start_top" => 1 },
								 { "name" => "ambiguity_loop", "fields" => $acs_sf_ambiguity_loop_fields, "start_top" => 1 } ] };

# spectral_peak_list frame description 
my $spl_sf_fields = {
  "_Spectral_peak_list.ID" => { "hash_field" => 1, "name" => "peak_list_id", "order" => 4 },
  "_Spectral_peak_list.Details" => { "name" => "details", "order" => 3 },
  "_Spectral_peak_list.NMR_spec_expt_label" => { "name" => "experiment_label", "order" => 2 },
  "_Spectral_peak_list.Number_of_spectral_dimensions" => { "name" => "num_dimensions", "order" => 1 }
  };
my $spl_sf_dim_loop_fields = {
  "dimension_descriptions" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1, "hash_type" => "ARRAY" },
  "_Spectral_dim.ID" => { "name" => "dim_id", "required" => 1  },
  "_Spectral_dim.Atom_type" => { "name" => "atom_type", "required" => 1  },
  "_Spectral_dim.Atom_isotope" => { "name" => "isotope", "required" => 1  },
  "_Spectral_dim.Spectral_region" => { "name" => "spectral_region", "required" => 1  },
  "_Spectral_dim.Magnetization_linkage_ID" => { "name" => "magnetization_linkage", "required" => 1  },
  "_Spectral_dim.Sweep_width" => { "name" => "sweep_width", "required" => 1  },
  "_Spectral_dim.Encoding_code" => { "name" => "encoding", "required" => 1  },
  "_Spectral_dim.Encoded_source_dimension_ID" => { "name" => "encoding_dimension", "required" => 1  },
  "_Spectral_dim.Spectral_peak_list_ID" => { "name" => "peak_list_id", "required" => 0, "skip_field" => 1  }
  };
my $spl_sf_peak_loop_fields = {
  "plist" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Peak.ID" => { "hash_field" => 2, "name" => "index", "required" => 1 },
  "_Peak.Intensity_val" => { "name" => "intensity", "required" => 1 },
  "_Peak.Intensity_err" => { "name" => "intensity_error", "required" => 1 },
  "_Peak.Figure_of_merit" => { "name" => "figure_of_merit", "required" => 1 },
  "_Peak.Intensity_measurement_method_ID" => { "name" => "measurement_method", "required" => 1 },
  "_Peak.Derivation_set_ID" => { "name" => "derivation_set", "required" => 1 },
  "_Peak.Details" => { "name" => "details", "required" => 1, "local_only" => 1 },
  "_Peak.Spectral_peak_list_ID" => { "name" => "peak_list_id", "required" => 0, "skip_field" => 1  }
  };
my $spl_sf_peak_char_loop_fields = {
  "plist" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Peak_char.Peak_ID" => { "hash_field" => 2, "required" => 1, "skip_field" => 1  },
  "dimensions" => { "hash_field" => 3, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Peak_char.Spectral_dimension_ID" => { "hash_field" => 4, "name" => "dim_id", "required" => 1 },
  "_Peak_char.Chem_shift_val" => { "name" => "shift", "required" => 1 },
  "_Peak_char.Chem_shift_val_err" => { "name" => "shift_error", "required" => 1 },
  "_Peak_char.Line_width_val" => { "name" => "width", "required" => 1 },
  "_Peak_char.Line_width_val_err" => { "name" => "width_error", "required" => 1 },
  "_Peak_char.Phase_val" => { "name" => "phase", "required" => 1 },
  "_Peak_char.Phase_val_err" => { "name" => "phase_error", "required" => 1 },
  "_Peak_char.Decay_rate_val" => { "name" => "decay", "required" => 1 },
  "_Peak_char.Decay_rate_val_err" => { "name" => "decay_error", "required" => 1 },
  "_Peak_char.Derivation_method_ID" => { "name" => "derivation_method", "required" => 1 },
  "_Peak_char.Spectral_peak_list_ID" => { "name" => "peak_list_id", "required" => 0, "skip_field" => 1 },
  };
my $spl_sf_assignment_loop_fields = {
  "plist" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Assigned_peak_chem_shift.Peak_ID" => { "hash_field" => 2, "required" => 1, "skip_field" => 1 },
  "dimensions" => { "hash_field" => 3, "hash_name" => 1, "required" => 0, "skip_field" => 1 },
  "_Assigned_peak_chem_shift.Spectral_dimension_ID" => { "hash_field" => 4, "required" => 1, "skip_field" => 1 },
  "assignments" => { "hash_field" => 5, "hash_name" => 1, "required" => 0, "skip_field" => 1, "hash_type" => "ARRAY" },
  "_Assigned_peak_chem_shift.Set_ID" => { "name" => "set_id", "required" => 1 },
  "_Assigned_peak_chem_shift.Magnetization_linkage_ID" => { "name" => "magnetization_linkage", "required" => 1 },
  "_Assigned_peak_chem_shift.Figure_of_merit" => { "name" => "figure_of_merit", "required" => 1 },
  "_Assigned_peak_chem_shift.List_ID" => { "name" => "list_id", "required" => 1 },
  "_Assigned_peak_chem_shift.Atom_chem_shift_ID" => { "name" => "shift_id", "required" => 1 },
  "_Assigned_peak_chem_shift.Spectral_peak_list_ID" => { "name" => "peak_list_id", "required" => 0, "skip_field" => 1 },
  };
my $spectral_peak_list_frame_description = { "type" => "spectral_peak_list", "type_tag" => "_Spectral_peak_list.Sf_category", "code" => sub { my $vals = shift @_; if (exists $$vals{"experiment_label"}) { return substr($$vals{"experiment_label"},1); } else { return "spectral_peak_list"; }  }, "code_tag" => "_Spectral_peak_list.Sf_framecode", 
					     "list_name" => "peak_lists", "list_id" => "peak_list_id", "list_ids_sub" => \&get_sort_list_ids, "single_field_description" => $spl_sf_fields, 
					     "process_sub" => \&process_spectral_peak_list_frame, "create_sub" => \&create_frame, "description_sub" => \&create_frame_description,
					     "loops" => [  { "name" => "dimension_descriptions", "fields" => $spl_sf_dim_loop_fields, "test" => "dimension_descriptions" },
							    { "name" => "peaks", "fields" => $spl_sf_peak_loop_fields, "test" => "plist" },
							    { "name" => "peak_characteristics", "fields" => $spl_sf_peak_char_loop_fields, "test" => "plist" }, 
							    { "name" => "peak_assignments", "fields" => $spl_sf_assignment_loop_fields, "test" => "plist" } ] };

# coupling_constants frame description
my $cc_sf_fields = {
  "_Coupling_constant_list.ID" => { "hash_field" => 1, "name" => "cc_list_id", "order" => 2 },
  "_Coupling_constant_list.Details" => { "name" => "details", "order" => 1 },
  };
my $cc_sf_loop_fields = {
  "elements" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1, "hash_type" => "ARRAY" },
  "_Coupling_constant.ID" => { "name" => "id", "required" => 1 },
  "_Coupling_constant.Code" => { "name" => "type", "required" => 1 },
#  "_Coupling_constant.Entry_atom_ID_1" => { "required" => 0 },
#  "_Coupling_constant.Entity_assembly_ID_1" => { "required" => 0 },
  "_Coupling_constant.Entity_ID_1" => { "name" => "Atom1entityID", "required" => 1 },
  "_Coupling_constant.Comp_index_ID_1" => { "name" => "Atom1residueNumber", "required" => 1 },
#  "_Coupling_constant.Seq_ID_1" => { "name" => "Atom1authorResidueNumber", "required" => 0 },
  "_Coupling_constant.Comp_ID_1" => { "name" => "Atom1residueName", "required" => 1 },
  "_Coupling_constant.Atom_ID_1" => { "name" => "Atom1atomName", "required" => 1 },
  "_Coupling_constant.Atom_type_1" => { "name" => "Atom1atomType", "required" => 0 },
  "_Coupling_constant.Ambiguity_code_1" => { "name" => "Atom1ambiguity", "required" => 0 },
#  "_Coupling_constant.Entry_atom_ID_2" => { "required" => 0 },
#  "_Coupling_constant.Entity_assembly_ID_2" => { "required" => 0 },
  "_Coupling_constant.Entity_ID_2" => { "name" => "Atom2entityID", "required" => 1 },
  "_Coupling_constant.Comp_index_ID_2" => { "name" => "Atom2residueNumber", "required" => 1 },
#  "_Coupling_constant.Seq_ID_2" => { "name" => "Atom2authorResidueNumber", "required" => 0 },
  "_Coupling_constant.Comp_ID_2" => { "name" => "Atom2residueName", "required" => 1 },
  "_Coupling_constant.Atom_ID_2" => { "name" => "Atom2atomName", "required" => 1 },
  "_Coupling_constant.Atom_type_2" => { "name" => "Atom2atomType", "required" => 0 },
  "_Coupling_constant.Ambiguity_code_2" => { "name" => "Atom2ambiguity", "required" => 0 },
  "_Coupling_constant.Val" => { "name" => "value", "required" => 1 },
  "_Coupling_constant.Val_min" => { "name" => "minValue", "required" => 0 },
  "_Coupling_constant.Val_max" => { "name" => "maxValue", "required" => 0 },
  "_Coupling_constant.Val_err" => { "name" => "error", "required" => 1 },
  "_Coupling_constant.Derivation_ID" => { "name" =>"derivation", "required" => 0 }
  };
my $coupling_constants_frame_description = { "type" => "coupling_constants", "type_tag" => "_Coupling_constant_list.Sf_category", "code" => "coupling_constants", "code_tag" => "_Coupling_constant_list.Sf_framecode", 
					     "list_name" => "cc_lists", "list_id" => "cc_list_id", "list_ids_sub" => \&get_sort_list_ids, "single_field_description" => $cc_sf_fields, 
					     "process_sub" => \&process_frame, "create_sub" => \&create_frame, "description_sub" => \&create_frame_description,
					     "loops" => [ { "name" => "coupling_constants", "fields" => $cc_sf_loop_fields, "test" => "elements" } ] };

# secondary_structure frame description
my $ss_sf_fields = {
  "_Secondary_struct_feature_list.ID" => { "hash_field" => 1, "name" => "ss_list_id", "order" => 2 },
  "_Secondary_struct_feature_list.Details" => { "name" => "details", "order" => 1 },
  };
my $ss_sf_loop_fields = {
  "elements" => { "hash_field" => 1, "hash_name" => 1, "required" => 0, "skip_field" => 1, "hash_type" => "ARRAY" },
  "_Secondary_struct.ID" => { "name" => "id", "required" => 1 },
  "_Secondary_struct.Entity_assembly_ID" => { "name" => "assembly_id", "required" => 0 },
  "_Secondary_struct.Entity_ID" => { "name" => "entity_id", "required" => 1 },
  "_Secondary_struct.Comp_index_ID_start" => { "name" => "start_index", "required" => 1 },
  "_Secondary_struct.Comp_index_ID_end" => { "name" => "end_index", "required" => 1 },
#  "_Secondary_struct.Seq_ID_start" => { "name" => "", "required" => 1 },
#  "_Secondary_struct.Seq_ID_end" => { "name" => "", "required" => 1 },
#  "_Secondary_struct.Auth_seq_ID_start" => { "name" => "", "required" => 1 },
#  "_Secondary_struct.Auth_seq_ID_end" => { "name" => "", "required" => 1 },
  "_Secondary_struct.Name" => { "name" => "sseName", "required" => 0 },
  "_Secondary_struct.Code" => { "name" => "sseCode", "required" => 1 },
#  "_Secondary_struct.Static_field_orientation_angle" => { "name" => "", "required" => 1 },
  "_Secondary_struct.Selection_method_ID" => { "name" => "method", "required" => 0 },
  "_Secondary_struct.Details" => { "name" => "details", "required" => 0 }
  };
my $secondary_structure_frame_description = { "type" => "secondary_structure", "type_tag" => "_Secondary_struct_feature_list.Sf_category", "code" => "secondary_structure", "code_tag" => "_Secondary_struct_feature_list.Sf_framecode", 
					      "list_name" => "ss_lists", "list_id" => "ss_list_id", "list_ids_sub" => \&get_sort_list_ids, "single_field_description" => $ss_sf_fields, 
					      "process_sub" => \&process_frame, "create_sub" => \&create_frame, "description_sub" => \&create_frame_description,
					      "loops" => [ { "name" => "secondary_structure", "fields" => $ss_sf_loop_fields, "test" => "elements" } ] };


my $frame_types = {
  $$assembly_frame_description{"type"} => $assembly_frame_description,
  $$entity_frame_description{"type"} => $entity_frame_description,
  $$assigned_chemical_shifts_frame_description{"type"} => $assigned_chemical_shifts_frame_description,
  $$spectral_peak_list_frame_description{"type"} => $spectral_peak_list_frame_description,
  $$coupling_constants_frame_description{"type"} => $coupling_constants_frame_description,
  $$secondary_structure_frame_description{"type"} => $secondary_structure_frame_description 
    };

my $frame_order = { $$assembly_frame_description{"type"} => 10, $$entity_frame_description{"type"} => 9, $$assigned_chemical_shifts_frame_description{"type"} => 8 };

# read_bmrb_file
#   reads a bmrb file and returns a hash of records (Residue is a hash).
#
#       $$bmrb_hlist{"filename"} - name of bmrb file used to build hash of residue names.
#	$$bmrb_hlist{"skip_processing"} - flag indicating that processing of usable save frames was skipped (optional).
#       $$bmrb_hlist{"ambiguity_lists"} - hash of ambiguity list set id's (optional).
#		$$ambiguity{"set_id"} - set id
#		$$ambiguity{"list"} - array of shift ID's.
#		$$ambiguity{"list_id"} - save_frame list ID.
#	$$bmrb_hlist{"assembly_list"} - hash of assembly_id.
#		$$assembly{"assembly_id"} - assembly ID.
#		$$assembly{"name"} - assembly name.
#		$$assembly{"num_entities"} - number of entities.
#	$$bmrb_hlist{"entity_list"} - hash of entity_id.
#		$$entity{"entity_id"} - entity id.
#               $$entity{"index_array"} - list of indeces in their proper order.
#               $$entity{"name_array"} - list of residue names in their proper order.
#		$$entity{"sequence"} - string of the amino acid sequence (single letter code).
#		$$entity{"residue_count"} - the number of residues in the polymer.
#		$$entity{"sequence_startpos"} - starting author_index (or index if no author_index).
#		$$entity{"molecule_type"} - molecule_type; polymer.
#		$$entity{"polymer_class"} - polymer_class; DNA, RNA, protein, etc.
#		$$entity{"common_name"} - common name for the molecule (optional).
#		$$entity{"rlist"} - hash list of name to residue.
#			$$residue{"name"} - name of residue (uses index in name)
#			$$residue{"author_name"} - name of residue (uses author_index in name)
#			$$residue{"aa"} - amino acid of residue
#			$$residue{"author_index"} - author designated residue number (optional).
#			$$residue{"insertion_code"} - insertion code for aligning with a native sequence (optional).
#			$$residue{"segment_definition_code"} - segment code for identifying important group of residues (optional).
#			$$residue{"index"} - residue number
#			$$residue{"shifts"} - hash of shifts
#				$$shift{"atom_type"} - atom_type of shift.
#				$$shift{"list"} - array of shift values.
#				$$shift{"idlist"} - array of shift ID's.
#				$$shift{"list_id_list"} - array of save_frame list ID's.
#				$$shift{"ambiguity_code"} - ambiguity code for the shift_name (optional).
#				$$shift{"error"} - amount of error for the shift value (optional).
#				$$shift{"extra_tags"} - hash of extra tags for the shift (optional).
#			$$residue{"next"} - name of the next residue.
#			$$residue{"prev"} - name of the previous residue.
#			$$residue{"extra_tags"} - hash of extra tags for the residue (optional).
#	$$bmrb_hlist{"peak_lists"} - hash of peak_list_id.
#		$$peak_list{"peak_list_id"} - spectral peak list id.
#		$$peak_list{"index_array"} - array of peak indexes.
#		$$peak_list{"details"} - array of lines  describing details for the peak list.
#		$$peak_list{"num_dimensions"} - number of dimensions. 
#		$$peak_list{"experiment_label"} - experiment_label.
#		$$peak_list{"dimension_descriptions"} - array of dimension descriptions.
#			$$dim_description{"dim_id"} - dimension id.
#			$$dim_description{"atom_type"} - atom type.
#			$$dim_description{"isotope"} - isotope number.
#			$$dim_description{"spectral_region"} - spectral region.
#			$$dim_description{"magnetization_linkage"} - magnetization linkage.
#			$$dim_description{"sweep_width"} - sweep width.
#			$$dim_description{"encoding"} - encoding code for composed dimensions.
#			$$dim_description{"encoding_dimension"} - source dimension for encoding.
#			$$dim_description{"extra_tags"} - extra tags.
#		$$peak_list{"plist"} - hash of peak index to peak.
#			$$peak{"index"} - index for the peak.
#			$$peak{"dimensions"} - hash of dimension id to dimension.
#				$$dimension{"dim_id"} - dimension id.
#				$$dimension{"shift"} - shift value in this dimension.
#				$$dimension{"shift_error"} - shift standard error in this dimension.
#				$$dimension{"width"} - peak width in this dimension.
#				$$dimension{"width_error"} - peak width standard error in this dimension.
#				$$dimension{"phase"} - peak phase.
#				$$dimension{"phase_error"} - peak phase standard error.
#				$$dimension{"decay"} - peak decay rate.
#				$$dimension{"decay_error"} - peak decay rate standard error.
#				$$dimension{"derivation_method"} - derivation method.
#				$$dimension{"assignments"} - array of shift assignments.
#					$$assignment{"entity_id"} - entity id.
#					$$assignment{"aa"} - amino acid.
#					$$assignment{"index"} - residue index. 
#					$$assignment{"atom_name"} - atom name.
#					$$assignment{"set_id"} - set id for handling ambiguous constraints.
#					$$assignment{"magnetization_linkage"} - magnetization_linkage.  
#					$$assignment{"figure_of_merit"} - figure of merit.  
#					$$assignment{"list_id"} - chemical shift list id. 
#					$$assignment{"shift_id"} - assigned shift id.
#					$$assignment{"extra_tags"} - extra tags.
#				$$dimension{"extra_tags"} - extra_tags.
#			$$peak{"intensity"} - peak intensity.
#			$$peak{"intensity_error"} - peak intensity standard error.
#			$$peak{"details"} - detail about the peak. 
#			$$peak{"figure_of_merit"} - figure of merit.
#			$$peak{"measurement_method"} - measurement method.
#			$$peak{"derivation_set"} - derivation set.
#			$$peak{"extra_tags"} - extra_tags.
#	$$bmrb_hlist{"cc_lists"} - hash of cc_list_id for different coupling constants lists.
#		$$cc_list{"cc_list_id"} - the coupling constant list id.
#		$$cc_list{"elements"} - array of coupling constant elements.
#			$$cc_elem{"id"} - coupling constants id
#			$$cc_elem{"type"} - description of type of coupling constants
#			$$cc_elem{"Atom1entityID"} - entity_id for Atom1
#			$$cc_elem{"Atom1residueNumber"} - residue number for Atom1
#			$$cc_elem{"Atom1residueName"} - residue name for Atom1
#			$$cc_elem{"Atom1atomName"} - atom name for Atom1
#			$$cc_elem{"Atom1atomType"} - atom type for Atom1
#			$$cc_elem{"Atom1ambiguity"} - atom ambiguity for Atom1
#			$$cc_elem{"Atom2entityID"} - entity_id for Atom2
#			$$cc_elem{"Atom2residueNumber"} - residue number for Atom2
#			$$cc_elem{"Atom2residueName"} - residue name for Atom2
#			$$cc_elem{"Atom2atomName"} - atom name for Atom2
#			$$cc_elem{"Atom2atomType"} - atom type for Atom2
#			$$cc_elem{"Atom2ambiguity"} - atom ambiguity for Atom2
#			$$cc_elem{"value"} - coupling constant value
#			$$cc_elem{"minValue"} - coupling constant minimum value
#			$$cc_elem{"maxValue"} - coupling constant maximum value
#			$$cc_elem{"error"} - coupling constant measurement error (uncertainty)
#	$$bmrb_hlist{"ss_lists"} - hash of ss_list_id for different secondary structure lists.
#		$$ss_list{"ss_list_id"} - the secondary structure list id.
#		$$ss_list{"elements"} - array of secondary structure elements.
#			$$ss_elem{"id"} - secondary structure id
#			$$ss_elem{"entity_id"} - entity id containing the SSE.
#			$$ss_elem{"start_index"} - beginning residue number of SSE
#			$$ss_elem{"end_index"} - ending residue number of SSE
#			$$ss_elem{"sseName"} - SSE name
#			$$ss_elem{"sseCode"} - SSE codes (loop, alpha-helix, beta-sheet)
#			$$ss_elem{"method"} - method of secondary structure determination
#
#       $$bmrb_hlist{"save_frames"} - list of save_frames.
#		$$save_frame{"type"} - type of save_frame.
#		$$save_frame{"code"} - framecode (name) of save_frame.
#		$$save_frame{"text"} - list of text lines of the save_frame.
#		$$save_frame{"sections"} - (optional) orderred list of sections of the save_frame.
#			$$section{"type"} - type of section.
#			$$section{"value"} - value of the section, if it has a value.
#			$$section{"extra_tags"} - (optional) lists of tags of extra data.
#			$$section{"all_tags"} - (optional) lists of tags of data.
#		$$save_frame{"data"} - organized data structure of save frame data (only for certain save frame types).
#
#   Parameters:
#       $filename - bmrb file to read.
#	$read_options - reference to hash of read options (optional).
#		$$read_options{"convert_aa_name"} - convert aa names from single letter to three letter. 
#		$$read_options{"convert_shift_names"} - convert shift names to degenerate naming scheme.
#		$$read_options{"shift_conversion_hash"} - ref to hash of shift name conversions.
#		$$read_options{"bmrb_hlist"} - reference to bmrb_hlist to fill.
sub read_bmrb_file
  {
  my $filename = shift @_;
  my $read_options = {};
  if (@_)
    { $read_options = shift @_; }

  # setting read_options
  my $skip_processing = (exists $$read_options{"skip_processing"} && $$read_options{"skip_processing"});
  my $delete_save_frames = (exists $$read_options{"delete_save_frames"} && $$read_options{"delete_save_frames"});

  my $bmrb_hlist;
  if (exists $$read_options{"bmrb_hlist"} && ref $$read_options{"bmrb_hlist"} eq "HASH")
    { $bmrb_hlist = $$read_options{"bmrb_hlist"}; }
  else
    { 
    $bmrb_hlist = {}; 
    $$bmrb_hlist{"filename"} = $filename;
    }

  # create "save_frames" if it does not exist
  if (! exists $$bmrb_hlist{"save_frames"})
    { $$bmrb_hlist{"save_frames"} = []; }

  # add newly read save_frames
  my $save_frame_alist = &read_raw_frames($filename, $read_options);
  if (! $delete_save_frames)
    { push @{$$bmrb_hlist{"save_frames"}}, @$save_frame_alist; }

  # skip processing usable save_frames if indicated in read_options
  if ($skip_processing)
    {
    $$bmrb_hlist{"skip_processing"} = 1;
    return $bmrb_hlist; 
    }

  # find and process usable save_frames
  foreach my $save_frame (@$save_frame_alist)
    {
    foreach my $ftype (keys %$frame_types)
      {
      if ($$save_frame{"type"} eq $ftype)
	{ &{$$frame_types{$ftype}{"process_sub"}}($save_frame, $$frame_types{$ftype}, $bmrb_hlist, $read_options); }
      }
    }
  
  # update spectral peak lists assignment info
  if (&has_shifts($bmrb_hlist) && exists $$bmrb_hlist{"peak_lists"} && ref($$bmrb_hlist{"peak_lists"}) eq "HASH" && %{$$bmrb_hlist{"peak_lists"}})
    { &update_spectral_peak_lists($bmrb_hlist); }

  return $bmrb_hlist; 
  }


# write_bmrb_file
#   Prints a bmrb file out to $filename
#
#   Parameters:
#	$bmrb_hlist - reference to bmrb hash structure.
#	$filename - name of output filename.
#       $write_options - hash of options.
sub write_bmrb_file
  {
  my $bmrb_hlist = shift @_;
  my $filename = shift @_; 
  my $write_options = {};
  if (@_)
    { $write_options = shift @_; }
  
  # do nothing if there are no save_frames and "skip_processing" is true
  if ((! exists $$bmrb_hlist{"save_frames"} || ! @{$$bmrb_hlist{"save_frames"}}) && (exists $$bmrb_hlist{"skip_processing"} && $$bmrb_hlist{"skip_processing"}))
    { return; }

  # start writing BMRB file
  local *STARFILE;
  if ($filename eq "-")
    { *STARFILE = *STDOUT; }
  else
    { open (STARFILE, ">$filename") || die "unable to open $filename"; }
      
  if (! exists $$bmrb_hlist{"save_frames"} || ref($$bmrb_hlist{"save_frames"}) ne "ARRAY")
    { $$bmrb_hlist{"save_frames"} = []; }

  my $save_frames = $$bmrb_hlist{"save_frames"};
  
  # create the needed save_frames if they do not exist.
  foreach my $frame_type (values %$frame_types)
    {
    foreach my $id (&{$$frame_type{"list_ids_sub"}}($frame_type, $bmrb_hlist, $save_frames))
      { 
      if (! (grep {$$_{"type"} eq $$frame_type{"type"} && $$_{"data"}{$$frame_type{"list_id"}} == $id; } (@$save_frames)))
	{ push @$save_frames, &{$$frame_type{"description_sub"}}($frame_type,$bmrb_hlist, $id); }
      }
    }
  
  if (exists $$bmrb_hlist{"entity_list"} && scalar(%{$$bmrb_hlist{"entity_list"}}))
    {
    if (! (grep {$$_{"type"} eq "assembly"; } (@$save_frames)))
      { unshift  @$save_frames, &create_frame_description($assembly_frame_description, $bmrb_hlist, ""); }
    
    foreach my $entity (sort { $$b{"entity_id"} <=> $$a{"entity_id"}; } (values %{$$bmrb_hlist{"entity_list"}}))
      { &update_entity($entity,0); }
    }
  
  # update spectral peak lists assignment info
  if (&has_shifts($bmrb_hlist) && exists $$bmrb_hlist{"peak_lists"} && ref($$bmrb_hlist{"peak_lists"}) eq "HASH" && %{$$bmrb_hlist{"peak_lists"}})
    { &update_spectral_peak_lists($bmrb_hlist); }

  # update shift ids across assigned chemical shifts frame and spectral peak list frames
  &update_shift_ids($bmrb_hlist);
  
  # sort save frames into proper order
  @$save_frames = sort { $$frame_order{$$b{"type"}} <=> $$frame_order{$$a{"type"}}; } (@$save_frames);

  # loop through save_frames
  foreach my $save_frame (@$save_frames)
    {
    my $text_lines = [];

    my $found = 0;
    foreach my $frame_type (values %$frame_types)
      {
      if ($$save_frame{"type"} eq $$frame_type{"type"} && exists $$save_frame{"sections"} && @{$$save_frame{"sections"}})
	{
	$text_lines = &{$$frame_type{"create_sub"}}($frame_type, $save_frame, $bmrb_hlist, $write_options);
	$found = 1;
	}
      }

    if (! $found && exists $$save_frame{"text"} && @{$$save_frame{"text"}})
      { $text_lines = $$save_frame{"text"}; }

    if (@$text_lines)
      {
      print STARFILE "save_",$$save_frame{"code"},"\n";
      print STARFILE "  ",$$save_frame{"type_tag"},"    ",$$save_frame{"type"},"\n"; ;
      print STARFILE "  ",$$save_frame{"code_tag"},"    ",$$save_frame{"code"},"\n"; ;
      
      foreach my $line (@$text_lines)
	{ print STARFILE $line,"\n"; }

      print STARFILE "save_\n\n";
      }
    }
      
  close STARFILE;
  }


#
#
#  Routines for internal use only.
#
#


# read_raw_frames
#   Reads raw save frames and returns array of save_frames.
#
#   Parameters:
#	$filename - filename to read.
#	$read_options - reference to hash of read options (optional).
#	
sub read_raw_frames
  {
  my $filename = shift @_;
  my $read_options = shift @_;

  my $limit_save_frames = 0;
  if (exists $$read_options{"limit_save_frames"} && ref $$read_options{"limit_save_frames"} eq "ARRAY")
    { $limit_save_frames = $$read_options{"limit_save_frames"}; }

  my $save_frames_alist = [];

  local *STARFILE;
  if ($filename eq "-")
    { *STARFILE = *STDIN; }
  else
    { open (STARFILE, "<$filename") || die "unable to open $filename"; }

  # divide STARFILE into save_frames.
  while (my $line = <STARFILE>)
    {
    # begin reading a save_frame
    if ($line =~ /^\s*save_/)
      {
      # skip comment and blank lines
      while (($line = <STARFILE>) && (($line =~ /^\s*$/) ||($line =~ /^\s*\#/))) {}

      my ($type_tag, $save_frame_type) = ($line =~ /(\S+Sf_category)\s+(\S+)/);
      if ($save_frame_type eq "")
	{
	chomp $line;
	print STDERR "ERROR LINE: \"",$line,"\"\n";
	die "Null _Sf_category";
	}

      while (($line = <STARFILE>) && (($line =~ /^\s*$/) ||($line =~ /^\s*\#/))) {}
      my ($code_tag,$save_frame_code) = ($line =~ /(\S+Sf_framecode)\s+(\S+)/);
      if ($save_frame_code eq "")
	{
	chomp $line;
	print STDERR "ERROR LINE: \"",$line,"\"\n";
	die "Null _Sf_framecode";
	}

      if (! $limit_save_frames || (grep {$_ eq $save_frame_type; } (@$limit_save_frames)))
	{
	my $save_frame = { "type" => $save_frame_type, "type_tag" => $type_tag, "code" => $save_frame_code, "code_tag" => $code_tag, "text" => [] };

	while (my $line = <STARFILE>)
	  {
	  chomp $line;
	  if ($line =~ /^\s*save_/)
	    { last; }
	  
	  push @{$$save_frame{"text"}}, $line; 
	  }      
 
	push @$save_frames_alist, $save_frame; 
	}
      else
	{
	while (my $line = <STARFILE>)
	  {
	  if ($line =~ /^\s*save_/)
	    { last; }	  
	  }      
	}
      }
    }
  
  close STARFILE if ($filename ne "-");

  return $save_frames_alist;
  }


# loop_contains
#   checks to see whether the loop_ fields contain the required and returns a hash of field name to field order.
#
#   Parameters:
#	$line_array - reference to array of lines.
#	$start - starting position in array to test
#	$usable_fields - hash of elements to check against the array of lines
sub loop_contains
  {
  my $line_array = shift @_;
  my $start = shift @_;
  my $usable_fields = shift @_;
  
  my $columns = {};
  my $required_count = 0;
  # Check all elements ...
  my $x=0;
  while (($start < @$line_array) && ($$line_array[$start] !~ /^\s*$/))
    {
    # skip comment lines
    if ($$line_array[$start] =~ /^\s*\#/)
      {
      $start++;
      next;
      }

    my ($field_name) = ($$line_array[$start] =~ /^\s*([A-Za-z0-9_.]+)/);
    my @new_name = (grep { $field_name =~ /^$_$/i; } (keys %$usable_fields));
    if (@new_name)
      {
      $field_name = $new_name[0]; 
      if ($$usable_fields{$field_name}{"required"})
	{ $required_count++; }
      }
    
    $$columns{$field_name} = $x;
    $x++;
    $start++;
    }
  
  if ($required_count != scalar(grep { $$_{"required"}; } (values %$usable_fields))) # this test could be erroneous; however, it is very unlikely
    { return 0; }
  
  return $columns;
  }


# find_loop
#   Finds and returns the appropriate loop description if it exists in the given array of loop descriptions.
#
#   Parameters:
#	$line_array - reference to array of lines.
#	$start - starting position in array to test
#	$loops - ref to array of loop descriptions
#
sub find_loop
  {
  my $line_array = shift @_;
  my $start = shift @_;
  my $loops = shift @_;

  foreach my $loop (@$loops)
    {
    if (&loop_contains($line_array,$start,$$loop{"fields"}))
      { return $loop; }
    }

  return 0;
  }


# process_create_loop_section
#   Processes a standard loop section of a save frame and puts it into the given hash or array.
#	Returns the ending line index.
#
#   Parameters:
#	$loop - ref to loop description.
#       $text_array - array of text lines to process
#	$start - ref to starting index in the array.
#	$data - hash/array to put information in.
sub process_create_loop_section
  {
  my $loop = shift @_;
  my $text_array = shift @_;
  my $start = shift @_;
  my $data = shift @_;
  
  my $fields = $$loop{"fields"};
  my $column_elements = &loop_contains($text_array, $$start+1, $fields);

  # increment index beyond loop description
  $$start += 1 + scalar(keys %$column_elements);

  my $extra_tags = [ grep { ! exists $$fields{$_}; } (keys %$column_elements) ];
  my @hash_fields = (sort { $$fields{$a}{"hash_field"} <=> $$fields{$b}{"hash_field"}; } (grep { $$fields{$_}{"hash_field"}; } (keys %$fields)));

  while($$start < @$text_array)
    {
    # stop on the stop_
    if ($$text_array[$$start] =~ /^\s*stop_/)
      { $$start++; last; }

    # skip comment or blank lines
    next if (($$text_array[$$start] =~ /^\s*\#/) || ($$text_array[$$start] =~ /^\s*$/));

    # split on \s into columns
    my @chars = split(//,$$text_array[$$start]);
    my $dquote = 0;
    my @tokens = ("");
    while(@chars)
      {
      if (($chars[0] eq "\"" && $dquote) || ($chars[0] =~ /\s/ && ! $dquote && length($tokens[$#tokens])))
	{ push @tokens, ""; $dquote = 0; }
      elsif ($chars[0] eq "\"" && ! $dquote)
	{ $dquote = 1; }
      elsif (($chars[0] =~ /\s/ && $dquote) || ($chars[0] !~ /\s/))
	{ $tokens[$#tokens] .= $chars[0]; }
      
      shift @chars;
      }

    if (scalar(@tokens) >= scalar(keys %$column_elements))
      {
      # perform conversions
      foreach my $field (grep { exists $$column_elements{$_}; } (keys %$fields))
	{
	if (ref($$fields{$field}{"conversion"}) eq "CODE")
	  { 
	  if (($tokens[$$column_elements{$field}] ne "") && ($tokens[$$column_elements{$field}] ne ".") && ($tokens[$$column_elements{$field}] ne "?"))
	    { $tokens[$$column_elements{$field}] = &{$$fields{$field}{"conversion"}}(\@tokens, $column_elements); }
	  }
	}

      # find entry, pre_entry and hash_id for insertion into $data
      my $entry = {};
      my $pre_entry = $data;
      if (@hash_fields)
	{ 
	for(my $x=0; $x < @hash_fields; $x++)
	  {
	  my $hash_id;
	  if ($$fields{$hash_fields[$x]}{"hash_name"})
	    { $hash_id = $hash_fields[$x]; }
	  elsif (ref($$fields{$hash_fields[$x]}{"compose"}) eq "CODE")
	    { $hash_id = &{$$fields{$hash_fields[$x]}{"compose"}}(\@tokens, $column_elements); }
	  else
	    { $hash_id = $tokens[$$column_elements{$hash_fields[$x]}]; }

	  if (ref($pre_entry) eq "HASH")
	    { 
	    if (! defined $$pre_entry{$hash_id})
	      {
	      if ($$fields{$hash_fields[$x]}{"hash_type"} eq "ARRAY")
		{ $$pre_entry{$hash_id} = []; }
	      else
		{ $$pre_entry{$hash_id} = {}; }
	      }

	    $pre_entry = $$pre_entry{$hash_id};
	    }
	  elsif (ref($pre_entry) eq "ARRAY")
	    { 
	    if (! defined $$pre_entry[$hash_id])
	      {
	      if ($$fields{$hash_fields[$x]}{"hash_type"} eq "ARRAY")
		{ $$pre_entry[$hash_id] = []; }
	      else
		{ $$pre_entry[$hash_id] = {}; }
	      }

	    $pre_entry = $$pre_entry[$hash_id];
	    }
	  }

	if (ref($pre_entry) ne "ARRAY")
	  { $entry = $pre_entry; }
	}

      # fill in $entry
      foreach my $field (keys %$fields)
	{
	next if ($$fields{$field}{"skip_field"});

	if (exists $$column_elements{$field})
	  {
	  my $name;
	  if (exists $$fields{$field}{"name"})
	    { $name = $$fields{$field}{"name"}; }
	  else
	    { $name = $field; }
	  
	  if (($tokens[$$column_elements{$field}] ne "") && ($tokens[$$column_elements{$field}] ne ".") && ($tokens[$$column_elements{$field}] ne "?"))
	    { 
	    if ($$fields{$field}{"type"} eq "ARRAY")
	      {
	      if (! exists $$entry{$name})
		{ $$entry{$name} = []; }
	      push @{$$entry{$name}}, $tokens[$$column_elements{$field}]; 
	      }
	    else
	      { $$entry{$name} = $tokens[$$column_elements{$field}]; }
	    }
	  }
	elsif (ref($$fields{$field}{"compose"}) eq "CODE")
	  {
	  my $name;
	  if (exists $$fields{$field}{"name"})
	    { $name = $$fields{$field}{"name"}; }
	  else
	    { $name = $field; }

	  $$entry{$name} = &{$$fields{$field}{"compose"}}(\@tokens, $column_elements);
	  }
	}

      # handle extra tags
      foreach my $field (@$extra_tags)
	{
	if (($tokens[$$column_elements{$field}] ne "") && ($tokens[$$column_elements{$field}] ne ".") && ($tokens[$$column_elements{$field}] ne "?"))
	  { $$entry{"extra_tags"}{$field} = $tokens[$$column_elements{$field}]; }
	}

      # add $entry to $data through $pre_entry if it is an array
      if (ref($pre_entry) eq "ARRAY")
	{ push @$pre_entry, $entry; }      
      }
    }
  continue
    { $$start++; }
  
  $$start--;

  # return section hash structure
  return { "type" => $$loop{"name"}, 
	   "extra_tags" => $extra_tags, 
	   "all_tags" => [ sort { $$column_elements{$a} <=> $$column_elements{$b}; } (keys %$column_elements) ] };
  }


# real_loop_fields
#   Return array of real loop fields in a given loop section description
#
# Parameters:
#	$fields - ref to hash of field descriptions.
#
sub real_loop_fields
  {
  my $fields = shift @_;
  return (grep { ! exists $$fields{$_}{"hash_name"} && ! exists $$fields{$_}{"compose"}; } (keys %$fields));
  }


# create_loop_section_text
#   Create text lines for a loop save_frame section
#
# Parameters:
#	$section - ref to the loop section.
#	$data - ref to data hash.
#	$fields - ref to hash of field descriptions.
#	$valid_record_sub - ref to subroutine to test if a given record is valid (optional).
#
sub create_loop_section_text
  {
  my $section = shift @_;
  my $data = shift @_;
  my $fields = shift @_;
  my $valid_record_sub = 0;
  if (@_)
    { $valid_record_sub = shift @_; }

  my @text_lines;
  push @text_lines, "   loop_";
  foreach my $tag (@{$$section{"all_tags"}})
    { push @text_lines, "     " . $tag; }
  push @text_lines, "";
  
  my @hash_fields = (sort { $$fields{$a}{"hash_field"} <=> $$fields{$b}{"hash_field"}; } (grep { $$fields{$_}{"hash_field"}; } (keys %$fields)));
  my @array_fields = (grep { ! $$fields{$_}{"hash_field"} && $$fields{$_}{"type"} eq "ARRAY"; } (keys %$fields));

  #initialize key array
  my $key_array = [];

  if ($$fields{$hash_fields[0]}{"hash_name"})
    { $$key_array[0] = [ $data , [ -1, $hash_fields[0] ] ]; }
  elsif (ref($data) eq "HASH")
    {
    my $sort = sub { $a <=> $b };
    if (exists $$fields{$hash_fields[0]}{"sort"} && ref($$fields{$hash_fields[0]}{"sort"}) eq "CODE")
      { $sort = $$fields{$hash_fields[0]}{"sort"}; }
    
    $$key_array[0] = [ $data , [ -1, sort $sort (keys %$data) ] ];
    }
  elsif (ref($data) eq "ARRAY")
    { $$key_array[0] = [ $data, [ -1, (0 .. $#$data) ] ]; }

  &increment_key_array($key_array, $fields, \@hash_fields);

  # loop through all records
  while(@{$$key_array[0][1]})
    {
    my $base_entry;
    if (ref($$key_array[$#$key_array][0]) eq "HASH")
      { $base_entry = $$key_array[$#$key_array][0]{$$key_array[$#$key_array][1][0]}; }
    else
      { $base_entry = $$key_array[$#$key_array][0][$$key_array[$#$key_array][1][0]]; }

    my $field_values = {};
    foreach my $field (grep { my $test = $_; ! (grep { $test eq $_; } (@array_fields)); } (@{$$section{"all_tags"}}))
      {
      my $name = $field;
      if (exists $$fields{$field}{"name"})
	{ $name = $$fields{$field}{"name"}; }
      
      my $format = sub { return shift @_; };
      if (exists $$fields{$field}{"format"} && ref($$fields{$field}{"format"}) eq "CODE")
	{ $format = $$fields{$field}{"format"}; }

      if (exists $$base_entry{$name})
	{ $$field_values{$field} = &$format($$base_entry{$name}); }
      elsif (exists $$base_entry{"extra_tags"}{$name})
	{ $$field_values{$field} = &$format($$base_entry{"extra_tags"}{$name}); }
      elsif (grep { $field eq $_; } (@hash_fields))
	{
	my $index = (grep { $field eq $hash_fields[$_]; } (0 .. $#hash_fields))[0];
	$$field_values{$field} = &$format($$key_array[$index][1][0]);
	}
      elsif(exists $$data{$name} && ! $$fields{$field}{"local_only"})
	{ $$field_values{$field} = &$format($$data{$name}); }
      }

    # handle array_fields
    my @usable_array_fields = (grep { my $test = $_; (grep { $test eq $_; } (@array_fields)); } (@{$$section{"all_tags"}}));
    if (@usable_array_fields)
      {
      my $num_records = 1;
      foreach my $field (@usable_array_fields)
	{
	my $name = $field;
	if (exists $$fields{$field}{"name"})
	  { $name = $$fields{$field}{"name"}; }

	if (exists $$base_entry{$name} && ref($$base_entry{$name}) eq "ARRAY" && @{$$base_entry{$name}} > $num_records)
	  { $num_records = @{$$base_entry{$name}}; }
	elsif (exists $$base_entry{"extra_tags"}{$name} && ref($$base_entry{"extra_tags"}{$name}) eq "ARRAY" && @{$$base_entry{"extra_tags"}{$name}} > $num_records)
	  { $num_records = @{$$base_entry{"extra_tags"}{$name}}; }
	}

      for(my $x=0; $x < $num_records; $x++)
	{
	foreach my $field (@usable_array_fields)
	  {
	  my $name = $field;
	  if (exists $$fields{$field}{"name"})
	    { $name = $$fields{$field}{"name"}; }
      
	  my $format = sub { return shift @_; };
	  if (exists $$fields{$field}{"format"} && ref($$fields{$field}{"format"}) eq "CODE")
	    { $format = $$fields{$field}{"format"}; }

	  if (exists $$base_entry{$name})
	    {
	    if (ref($$base_entry{$name}) eq "ARRAY" && $x < @{$$base_entry{$name}}) 
	      { $$field_values{$field} = &$format($$base_entry{$name}[$x]); }
	    else
	      { delete $$field_values{$field}; }
	    }
	  elsif (exists $$base_entry{"extra_tags"}{$name})
	    {
	    if (ref($$base_entry{"extra_tags"}{$name}) eq "ARRAY" && $x < @{$$base_entry{"extra_tags"}{$name}}) 
	      { $$field_values{$field} = &$format($$base_entry{"extra_tags"}{$name}[$x]); }
	    else
	      { delete $$field_values{$field}; }
	    }
	  }

	if (%$field_values && (! $valid_record_sub || (ref($valid_record_sub) eq "CODE" && &$valid_record_sub($field_values))))
	  { push @text_lines, "    " . join("   ",(map { (exists $$field_values{$_}) ? $$field_values{$_} :"?"; } (@{$$section{"all_tags"}}))); }
	}
      }
    else
      { 
      if (%$field_values && (! $valid_record_sub || (ref($valid_record_sub) eq "CODE" && &$valid_record_sub($field_values))))
	{ push @text_lines, "    " . join("   ",(map { (exists $$field_values{$_}) ? $$field_values{$_} : "?"; } (@{$$section{"all_tags"}}))); }
      }

    # iterate key array
    &increment_key_array($key_array, $fields, \@hash_fields);
    }

  push @text_lines, "","   stop_";
  return @text_lines;
  }


# increment_key_array
#   increments a given key array for iterating through the records in a section loop.
#
# Parameters:
#	$key_array - array of array of keys used to iterate through a complex hash structure representation of records.
#	$fields - ref to hash of field descriptions.
#	$hash_fields - array of the hash fields used to parse the complex hash structure.
#
sub increment_key_array
  {
  my $key_array = shift @_;
  my $fields = shift @_;
  my $hash_fields = shift @_;

  my $x = $#$key_array;
  while($x >= 0 && $x <= $#$key_array)
    {
    if (! @{$$key_array[$x][1]})
      { $x--; }
    else
      {
      shift @{$$key_array[$x][1]}; 
      next if (! @{$$key_array[$x][1]});
      $x++;
      while((($x <= $#$hash_fields) || ($x == @$hash_fields && $$fields{$$hash_fields[$#$hash_fields]}{"hash_type"} eq "ARRAY")) && @{$$key_array[$x-1][1]})
	{
	if (ref($$key_array[$x-1][0]) eq "HASH")
	  { $$key_array[$x][0] = $$key_array[$x-1][0]{$$key_array[$x-1][1][0]}; }
	else
	  { $$key_array[$x][0] = $$key_array[$x-1][0][$$key_array[$x-1][1][0]]; }

	if ($x <= $#$hash_fields && $$fields{$$hash_fields[$x]}{"hash_name"})
	  { $$key_array[$x][1] = [ $$hash_fields[$x] ]; }
	elsif (ref($$key_array[$x][0]) eq "HASH")
	  {
	  my $sort = sub { $a <=> $b };
	  if (exists $$fields{$$hash_fields[$x]}{"sort"} && ref($$fields{$$hash_fields[$x]}{"sort"}) eq "CODE")
	    { $sort = $$fields{$$hash_fields[$x]}{"sort"}; }
	  
	  $$key_array[$x][1] = [ sort $sort (keys %{$$key_array[$x][0]}) ];
	  }
	elsif (ref($$key_array[$x][0]) eq "ARRAY")
	  { $$key_array[$x][1] = [ (0 .. $#{$$key_array[$x][0]}) ]; }
	else
	  { $$key_array[$x][1] = []; }
	
	if (@{$$key_array[$x][1]})
	  { $x++; }
	else
	  { last; }
	}
      }
    }  
  }


# find_data_field 
#   Find the field that matches the given section type.
#
# Parameters:
#	$section_type - type of save_frame section.
#	$frame_description - ref to hash of a frame description.
#
sub find_data_field
  {
  my $section_type = shift @_;
  my $frame_description = shift @_;

  if (exists $$frame_description{"single_field_description"})
    {
    foreach my $field (keys %{$$frame_description{"single_field_description"}})
      {
      if ((exists $$frame_description{"single_field_description"}{$field}{"name"} && $section_type eq $$frame_description{"single_field_description"}{$field}{"name"}) || (! exists $$frame_description{"single_field_description"}{$field}{"name"} && $section_type eq $field))
	{ return $field; }
      }
    }

  return "";
  }


# find_loop_by_name
#   Finds and returns the appropriate loop description if it matches the given section type.
#
#   Parameters:
#	$section_type - section type.
#	$loops - ref to array of loop descriptions
#
sub find_loop_by_name
  {
  my $section_type = shift @_;
  my $loops = shift @_;

  foreach my $loop (@$loops)
    {
    if ($$loop{"name"} eq $section_type)
      { return $loop; }
    }

  return 0;
  }


# process_create_single_field_section
#   Process a single field section of a save frame and return a section type.
#
# Parameters
#	$lines - ref to array of lines.
#	$count - ref to $line count.
#	$fields - ref to hash of field descriptions.
#	$data - ref to location to put data.
#	$hash - ref to hash for putting $data in (optional).
sub process_create_single_field_section
  {
  my $lines = shift @_;
  my $count = shift @_;
  my $fields = shift @_;
  my $data = shift @_;
  my $hash;
  if (@_)
    { $hash = shift @_; }

  my $field_name;
  foreach my $name (keys %$fields)
    { 
    if ($$lines[$$count] =~ /^\s*$name/i)
      { $field_name = $name; }
    }

  my $value;
  if ($$lines[$$count] =~ /^\s*$field_name\s*\"(.*)\"/i)
    {$value = $1; }
  elsif ($$lines[$$count] =~ /^\s*$field_name\s*\'(.*)\'/i)
    {$value = $1; }
  elsif ($$lines[$$count] =~ /^\s*$field_name\s*(\S+)/i)
    {$value = $1; }
  elsif (($$lines[$$count] =~ /^\s*$field_name\s*$/i) && (@$lines > $$count+1) && ($$lines[$$count+1] =~ /^;/))
    {
    $value = [];
    $$count++; $$count++;
    while(($$count < @$lines) && ($$lines[$$count] !~ /^;/))
      {
      push @$value, $$lines[$$count];
      $$count++;
      }
    }

  my $data_name;
  if (exists $$fields{$field_name}{"name"})
    { $data_name = $$fields{$field_name}{"name"}; }
  else
    { $data_name = $field_name; }

  if (ref($hash) eq "HASH" && $$fields{$field_name}{"hash_field"})
    { 
    if (exists $$hash{$value})
      { $data = $$hash{$value}; }
    else
      { 
      $$hash{$value} = $data; 
      $$data{$data_name} = $value;
      }
    }
  elsif (($value ne "") && ($value ne ".") && ($value ne "?"))
    { $$data{$data_name} = $value; }

  return wantarray ? ($data, { "type" => $data_name }) : { "type" => $data_name };
  }

# create_single_field_section_text
#   Create text lines for a single field save_frame section
#
# Parameters:
#	$name - name of data field.
#	$data - ref to data hash.
#	$field - name of field.
#	$fields - ref to hash of field descriptions.
#
sub create_single_field_section_text
  {
  my $name = shift @_;
  my $data = shift @_;
  my $field = shift @_;
  my $fields = shift @_;
  
  my @text_lines;
  my $format_sub = sub { return shift @_; }; 

  if (exists $$fields{$field}{"format"} && ref($$fields{$field}{"format"}) eq "CODE")
    { $format_sub = $$fields{$field}{"format"}; }

  if (exists $$data{$name} && $$data{$name} ne "")
    {
    if (ref($$data{$name}) eq "ARRAY")
      {
      push @text_lines, "    " . $field;
      push @text_lines, ";";
      foreach my $value (@{$$data{$name}})
	{ push @text_lines, &$format_sub($value); }
      push @text_lines, ";";
      }
    else
      { push @text_lines, "    " . $field . "	" . &$format_sub($$data{$name}); }
    }
  else
    { push @text_lines, "    " . $field . "	?"; }
  
  return @text_lines;
  }


# process_frame
#   Process the given save_frame given the save_frame text and a description of how to process it.
#
#   Parameters:
#       $save_frame - save_frame hash
#	$frame_description - description of the save frame and how to process it.
#	$bmrb_hlist - bmrb hash structure to fill.
#	$read_options - hash of read options.
#
sub process_frame
  {
  my $save_frame = shift @_;
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
#  my $read_options = shift @_;
  
  if (exists $$frame_description{"list_name"} && ! exists $$bmrb_hlist{$$frame_description{"list_name"}})
    { $$bmrb_hlist{$$frame_description{"list_name"}} = {}; }

  my $orig_text = $$save_frame{"text"};
  my $data = {};
  my $sections = [];
  my $list_id;
  # foreach line in the file until stop_
  for(my $x=0; $x < @$orig_text; $x++)
    {
    if (exists $$frame_description{"list_id_field"} && ($$orig_text[$x] =~ /^\s*$$frame_description{"list_id_field"}\s*(\S+)/i))
      { $list_id = $1; }

    if (exists $$frame_description{"single_field_description"} && (grep { $$orig_text[$x] =~ /^\s*$_\s+/i; } (keys %{$$frame_description{"single_field_description"}})))
      { 
      my $section;
      ($data, $section) = &process_create_single_field_section($orig_text,\$x,$$frame_description{"single_field_description"},$data,$$bmrb_hlist{$$frame_description{"list_name"}}); 
      push @$sections, $section;
      }
    elsif (($$orig_text[$x] =~ /^\s*loop_/) && (my $loop = &find_loop($orig_text,$x+1,$$frame_description{"loops"})))
      {
      if ($$loop{"start_top"})
	{ push @$sections, &process_create_loop_section($loop, $orig_text,\$x, $bmrb_hlist); }
      else
	{ push @$sections, &process_create_loop_section($loop, $orig_text,\$x, $data); }
      }
    else
      {
      if (! @$sections || ($$sections[$#{$sections}]{"type"} ne "text")) 
	{ push @$sections, { "type" => "text", "value" => [] }; }
      push @{$$sections[$#{$sections}]{"value"}}, $$orig_text[$x];
      } 
    }

  if (@$sections)
    { 
    $$save_frame{"sections"} = $sections; 
    if (exists $$frame_description{"list_id_field"})
      { $$save_frame{"data"}{$$frame_description{"list_id"}} = $list_id; }
    else
      { $$save_frame{"data"}{$$frame_description{"list_id"}} = $$data{$$frame_description{"list_id"}}; }
    delete $$save_frame{"text"}; 
    }
  }


# get_sort_list_ids
#   Returns sorted list of ids for a particular save_frame description
#
# Parameters:
#	$frame_description - ref to save_frame description.
#	$bmrb_hlist - ref to BMRB hash structure.
#	$save_frames - ref to array of save_frames.
#
sub get_sort_list_ids
  {
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $save_frames = shift @_;

  if (exists $$frame_description{"list_name"} && exists $$bmrb_hlist{$$frame_description{"list_name"}} && ref($$bmrb_hlist{$$frame_description{"list_name"}}) eq "HASH" && %{$$bmrb_hlist{$$frame_description{"list_name"}}})
    { return sort { $a <=> $b } (keys %{$$bmrb_hlist{$$frame_description{"list_name"}}}); }
  
  return ();
  }


# create_frame_description
#    Create and return a given type of save frame description
#
# Parameters:
#	$frame_description - ref to save_frame description.
#	$bmrb_hlist - ref to BMRB hash structure.
#	$list_id - list_id.
#
sub create_frame_description
  {
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $list_id = shift @_;

  my $data = 0;
  if ($list_id ne "" && exists $$frame_description{"list_name"} && exists $$bmrb_hlist{$$frame_description{"list_name"}} && 
      ref($$bmrb_hlist{$$frame_description{"list_name"}}) eq "HASH" && exists $$bmrb_hlist{$$frame_description{"list_name"}}{$list_id} && 
      ref($$bmrb_hlist{$$frame_description{"list_name"}}{$list_id}) eq "HASH")
    { $data = $$bmrb_hlist{$$frame_description{"list_name"}}{$list_id}; }

  my $sections = [];
  push @$sections, { "type" => "text", "value" => [ "" ] };
  if (exists $$frame_description{"single_field_description"})
    {
    foreach my $field (sort { $$frame_description{"single_field_description"}{$b}{"order"} <=> $$frame_description{"single_field_description"}{$a}{"order"}; } (keys %{$$frame_description{"single_field_description"}}))
      {
      if (exists $$frame_description{"single_field_description"}{$field}{"name"})
	{ push @$sections, { "type" => $$frame_description{"single_field_description"}{$field}{"name"} }; }
      else
	{ push @$sections, { "type" => $field }; }
      }
    }
  
  if (exists $$frame_description{"loops"})
    {
    foreach my $loop (@{$$frame_description{"loops"}})
      {
      if (! exists $$loop{"test"} || ($data && exists $$data{$$loop{"test"}}))
	{
	push @$sections, { "type" => "text", "value" => [ "" ] };
	push @$sections, { "type" => $$loop{"name"}, "all_tags" => [ &real_loop_fields($$loop{"fields"}) ], "extra_tags" => [] };
	}
      }
    }

  push @$sections, { "type" => "text", "value" => [ "" ] };

  my $description = { "type" => $$frame_description{"type"}, "sections" => $sections, "data" => { $$frame_description{"list_id"} => $list_id }, "code_tag" => $$frame_description{"code_tag"}, "type_tag" => $$frame_description{"type_tag"} };

  if (ref($$frame_description{"code"}) eq "CODE")
    { $$description{"code"} = &{$$frame_description{"code"}}($data); }
  else
    { $$description{"code"} = $$frame_description{"code"}; }
  
  return $description;  
  }


# create_frame
#   Returns an array of text_lines given the description of the save_frame and the bmrb hash structure.
#
#   Parameters:
#	$frame_description - ref to save_frame description.
#	$save_frame - ref to save_frame hash structure.
#	$bmrb_hlist - ref to bmrb hash structure.
#	$write_options - hash of write options.
#
sub create_frame
 {
 my $frame_description = shift @_;
 my $save_frame = shift @_;
 my $bmrb_hlist = shift @_;
# my $write_options = shift @_;

 my $data = {};
 if (exists $$frame_description{"list_name"}) 
   {
   if (exists $$frame_description{"list_id"} && exists $$save_frame{"data"}{$$frame_description{"list_id"}} && 
       exists $$bmrb_hlist{$$frame_description{"list_name"}}{$$save_frame{"data"}{$$frame_description{"list_id"}}})
     { $data = $$bmrb_hlist{$$frame_description{"list_name"}}{$$save_frame{"data"}{$$frame_description{"list_id"}}}; }
   }
 else
   { $data = $bmrb_hlist; }

 my $text_lines = [];
 my $field;
 foreach my $section (@{$$save_frame{"sections"}})
   {
   if ($$section{"type"} eq "text")
     { push @$text_lines, (@{$$section{"value"}}); }
   elsif (($field = &find_data_field($$section{"type"}, $frame_description)) ne "")
     { push @$text_lines, &create_single_field_section_text($$section{"type"},$data, $field, $$frame_description{"single_field_description"}); }
   elsif (my $loop = &find_loop_by_name($$section{"type"}, $$frame_description{"loops"}))
     {
     if ($$loop{"start_top"})
       { push @$text_lines, &create_loop_section_text($section, $bmrb_hlist, $$loop{"fields"}, $$loop{"valid_record_sub"}); }
     else
       { push @$text_lines, &create_loop_section_text($section, $data, $$loop{"fields"}, $$loop{"valid_record_sub"}); }
     }
   }

 return $text_lines;
 }


# create_assembly_frame
#   Returns an array of text_lines given the description of the save_frame and the bmrb hash structure.
#
#   Parameters:
#	$frame_description - ref to save_frame description.
#	$save_frame - ref to save_frame hash structure.
#	$bmrb_hlist - ref to bmrb hash structure.
#	$write_options - hash of write options.
#
sub create_assembly_frame
 {
 my $frame_description = shift @_;
 my $save_frame = shift @_;
 my $bmrb_hlist = shift @_;
 my $write_options = shift @_;

 my $entity_loop = &find_loop_by_name("entity_loop",$$assembly_frame_description{"loops"});
 if (exists $$save_frame{"data"}{"assembly_id"} && $$save_frame{"data"}{"assembly_id"} ne "" && $$save_frame{"data"}{"assembly_id"} ne "." && $$save_frame{"data"}{"assembly_id"} ne "?")
   { $$entity_loop{"valid_record_sub"} = sub { my $record = shift @_;  return ($$save_frame{"data"}{"assembly_id"} == $$record{"_Entity_assembly.Assembly_ID"}); }; }
 else
   { $$entity_loop{"valid_record_sub"} = 0; }

 return &create_frame($frame_description, $save_frame, $bmrb_hlist, $write_options);
 }


# process_entity_frame
#   Reads the residue list from a monomeric polymer frame and puts them in the bmrb hash.
#
#   Parameters:
#       $save_frame - save_frame hash
#	$frame_description - description of the save frame and how to process it.
#	$bmrb_hlist - bmrb hash structure to fill.
#	$read_options - hash of read options.
#
sub process_entity_frame
  {
  my $save_frame = shift @_;
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $read_options = shift @_;

  if (! (exists $$read_options{"convert_aa_names"} && ! $$read_options{"convert_aa_names"}))
    { 
    $$entity_sf_sequence_loop_fields{"_Entity_comp_index.Comp_ID"}{"conversion"} = sub { my ($cols, $elems) = @_; return &convert_aa3to1($$cols[$$elems{"_Entity_comp_index.Comp_ID"}]); }; 
    }
  else
    { $$entity_sf_sequence_loop_fields{"_Entity_comp_index.Comp_ID"}{"conversion"} = 0; }
  
  &process_frame($save_frame, $frame_description, $bmrb_hlist, $read_options);
  
  if (exists $$save_frame{"sections"} && ref($$save_frame{"sections"}) eq "ARRAY" && @{$$save_frame{"sections"}} && exists $$save_frame{"data"}{$$frame_description{"list_id"}} && 
      exists $$bmrb_hlist{$$frame_description{"list_name"}} && exists $$bmrb_hlist{$$frame_description{"list_name"}}{$$save_frame{"data"}{$$frame_description{"list_id"}}})
    { &update_entity($$bmrb_hlist{$$frame_description{"list_name"}}{$$save_frame{"data"}{$$frame_description{"list_id"}}},1); }
  }


# update_entity
#   Update a given entity structure
#
#   Parameters:
#	$entity - ref to entity hash structure
#	$force - boolean to force update.
#
sub update_entity
  {
  my $entity = shift @_;
  my $force = shift @_;

  if ($force || ! exists $$entity{"name_array"})
    { $$entity{"name_array"} = [ sort { ($a =~ /^[a-zA-Z]+(\-?\d+)$/)[0] <=> ($b =~ /^[A-Za-z]+(\-?\d+)$/)[0]; } (keys %{$$entity{"rlist"}}) ]; }

  if ($force || ! exists $$entity{"index_array"})
    { $$entity{"index_array"} = [map { $$entity{"rlist"}{$_}{"index"}; } (@{$$entity{"name_array"}})]; }
  
  if ($force || ! exists $$entity{"residue_count"})
    { $$entity{"residue_count"} = scalar(@{$$entity{"name_array"}}); }

  if ($force || ! exists $$entity{"sequence"})
    {
    $$entity{"sequence"} = "";
    foreach my $name (@{$$entity{"name_array"}})
      { $$entity{"sequence"} .=  &convert_aa3to1($$entity{"rlist"}{$name}{"aa"}); }
    }
    
  for(my $x = 0; $x < @{$$entity{"name_array"}}; $x++)
    {
    my $name = $$entity{"name_array"}[$x];      
    
    if (exists $$entity{"rlist"}{$name}{"author_index"})
	{ $$entity{"rlist"}{$name}{"author_name"} = $$entity{"rlist"}{$name}{"aa"} . $$entity{"rlist"}{$name}{"author_index"}; }
  
    if ($x && ($$entity{"index_array"}[$x]-1 == $$entity{"index_array"}[$x-1]))
      { $$entity{"rlist"}{$name}{"prev"} = $$entity{"name_array"}[$x-1]; }
    if ($x+1 < @{$$entity{"name_array"}} && ($$entity{"index_array"}[$x]+1 == $$entity{"index_array"}[$x+1]))
      { $$entity{"rlist"}{$name}{"next"} = $$entity{"name_array"}[$x+1]; }
    }

  # update aa/index/author_index in shift structure.
  foreach my $residue (values %{$$entity{"rlist"}})
    {
    if (exists $$residue{"shifts"})
      {
      foreach my $shift (values %{$$residue{"shifts"}})
	{
	if (exists $$residue{"aa"})
	  { $$shift{"aa"} = $$residue{"aa"}; }

	if (exists $$residue{"index"})
	  { $$shift{"index"} = $$residue{"index"}; }

	if (exists $$residue{"author_index"})
	  { $$shift{"author_index"} = $$residue{"author_index"}; }
	}
      }
    }

  # create sequence_startpos field
  if ($force || ! exists $$entity{"sequence_startpos"})
    {
    if (exists $$entity{"rlist"}{$$entity{"name_array"}[0]}{"author_index"})
      { $$entity{"sequence_startpos"} = $$entity{"rlist"}{$$entity{"name_array"}[0]}{"author_index"}; }
    else
      { $$entity{"sequence_startpos"} = $$entity{"rlist"}{$$entity{"name_array"}[0]}{"index"}; }
    }

  }


# process_assigned_chemical_shifts_frame
#   Processes the assigned chemical shift lines and puts them in the bmrb hash structure.
#
#   Parameters:
#       $save_frame - save_frame hash
#	$frame_description - description of the save frame and how to process it.
#	$bmrb_hlist - bmrb hash structure to fill.
#	$read_options - hash of read options.
#
sub process_assigned_chemical_shifts_frame
  {
  my $save_frame = shift @_;
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $read_options = shift @_;

  if (! (exists $$read_options{"convert_aa_names"} && ! $$read_options{"convert_aa_names"}))
    { $$acs_sf_shift_loop_fields{"_Atom_chem_shift.Comp_ID"}{"conversion"} = sub { my ($cols, $elems) = @_; return &convert_aa3to1($$cols[$$elems{"_Atom_chem_shift.Comp_ID"}]); }; }
  else
    { $$acs_sf_shift_loop_fields{"_Atom_chem_shift.Comp_ID"}{"conversion"} = 0; }

  my $shift_conversion_hash = \%degeneracy_shift_conversion;
  if (exists $$read_options{"shift_conversion_hash"} && ref $$read_options{"shift_conversion_hash"} eq "HASH")
    { $shift_conversion_hash = $$read_options{"shift_conversion_hash"}; }

  if (exists $$read_options{"convert_shift_names"} && $$read_options{"convert_shift_names"})
    { 
    $$acs_sf_shift_loop_fields{"_Atom_chem_shift.Atom_ID"}{"conversion"} = sub 
      { 
      my ($cols, $elems) = @_; 
      if (exists $$shift_conversion_hash{lc($$cols[$$elems{"_Atom_chem_shift.Atom_ID"}])}) 
	{ return $$shift_conversion_hash{lc($$cols[$$elems{"_Atom_chem_shift.Atom_ID"}])}; }
      else 
	{ return  $$cols[$$elems{"_Atom_chem_shift.Atom_ID"}]; }
      }; 
    }
  else
    { $$acs_sf_shift_loop_fields{"_Atom_chem_shift.Atom_ID"}{"conversion"} = 0; }

  &process_frame($save_frame, $frame_description, $bmrb_hlist, $read_options);
  }


# get_sort_acs_list_ids
#   Returns list of list_id's found with shifts.
#
#   Parameters:
#	$bmrb_hlist - reference to bmrb hash structure.
sub get_sort_acs_list_ids
  {
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $save_frames = shift @_;

  my $list_id_hlist = {};
  if (&has_shifts($bmrb_hlist))
    {
    if (exists $$bmrb_hlist{"entity_list"} && ref($$bmrb_hlist{"entity_list"}) eq "HASH")
      {
      foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
	{
	if (exists $$entity{"rlist"} && ref($$entity{"rlist"}) eq "HASH")
	  {
	  foreach my $residue (values %{$$entity{"rlist"}})
	    {
	    if (exists $$residue{"shifts"} && ref($$residue{"shifts"}) eq "HASH")
	      {
	      foreach my $shift (values %{$$residue{"shifts"}})
		{
		if (exists $$shift{"list_id_list"} && ref($$shift{"list_id_list"}) eq "ARRAY")
		  { 
		  foreach my $list_id (@{$$shift{"list_id_list"}})
		    { $$list_id_hlist{$list_id} = 1; }
		  }
		}
	      }
	    } 
	  }
	}
      }
    
    if (! %$list_id_hlist && ! (grep {$$_{"type"} eq "assigned_chemical_shifts" && ($$_{"data"}{"list_id"} eq "" || $$_{"data"}{"list_id"} eq "." || $$_{"data"}{"list_id"} eq "?"); } (@$save_frames)))
      { return ("?"); }
    }

  return (sort { $a <=> $b } (keys %$list_id_hlist));
  }


# create_assigned_chemical_shifts_frame_description
#   Create and return an assigned chemical shift frame description
#
#   Parameters:
#	$frame_description - ref to save_frame description.
#	$bmrb_hlist - ref to BMRB hash structure.
#	$list_id - list_id.
#
sub create_assigned_chemical_shifts_frame_description
  {
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $list_id = shift @_;

  my $description = &create_frame_description($frame_description, $bmrb_hlist, $list_id);
  unshift @{$$description{"sections"}}, { "type" => "text", 
					  "value" => [ "",
						       "    _Assigned_chem_shift_list.ID                                   " . $list_id, 
						       "    _Assigned_chem_shift_list.Sample_condition_list_ID             ?", 
						       "    _Assigned_chem_shift_list.Sample_condition_list_label          ?",
						       "    _Assigned_chem_shift_list.Chem_shift_reference_ID              ?",
						       "    _Assigned_chem_shift_list.Chem_shift_reference_label           ?",
						       ] };
  return $description;
  }

# create_assigned_chemical_shifts_frame
#   Returns an array of text_lines given the description of the save_frame and the bmrb hash structure.
#
#   Parameters:
#	$frame_description - ref to save_frame description.
#	$save_frame - ref to save_frame hash structure.
#	$bmrb_hlist - ref to bmrb hash structure.
#	$write_options - ref to write options hash
#
sub create_assigned_chemical_shifts_frame
 {
 my $frame_description = shift @_;
 my $save_frame = shift @_;
 my $bmrb_hlist = shift @_;
 my $write_options = shift @_;

 my $shift_section = 0;
 my $all_tags = 0;
 my $extra_tags = 0;
 if (exists $$write_options{"extra_tags"} && exists $$write_options{"extra_tags"}{"shifts"} && ref($$write_options{"extra_tags"}{"shifts"}) eq "ARRAY" && (grep { $$_{"type"} eq "chemical_shift_loop"; } (@{$$save_frame{"sections"}})))
   {
   $shift_section = (grep { $$_{"type"} eq "chemical_shift_loop"; } (@{$$save_frame{"sections"}}))[0];
   $all_tags = $$shift_section{"all_tags"};
   $extra_tags = $$shift_section{"extra_tags"};
   $$shift_section{"all_tags"} = [ grep { my $test = $_; ! (grep { $_ eq $test; } (@{$$shift_section{"extra_tags"}})) || (grep { $_ eq $test; } (@{$$write_options{"extra_tags"}{"shifts"}}));  } (@{$$shift_section{"all_tags"}}) ];
   $$shift_section{"extra_tags"} = [ @{$$write_options{"extra_tags"}{"shifts"}} ];
   }

 my $shift_loop = &find_loop_by_name("chemical_shifts_loop", $$assigned_chemical_shifts_frame_description{"loops"});
 my $ambiguity_loop = &find_loop_by_name("ambiguity_loop", $$assigned_chemical_shifts_frame_description{"loops"});
 if (exists $$save_frame{"data"}{"list_id"} && $$save_frame{"data"}{"list_id"} ne "" && $$save_frame{"data"}{"list_id"} ne "." && $$save_frame{"data"}{"list_id"} ne "?")
   { 
   $$shift_loop{"valid_record_sub"} = sub { my $record = shift @_;  return ($$save_frame{"data"}{"list_id"} == $$record{"_Atom_chem_shift.Assigned_chem_shift_list_ID"}); }; 
   $$ambiguity_loop{"valid_record_sub"} = sub { my $record = shift @_;  return ($$save_frame{"data"}{"list_id"} == $$record{"_Ambiguous_atom_chem_shift.Assigned_chem_shift_list_ID"}); };
   }
 else
   { 
   $$shift_loop{"valid_record_sub"} = 0; 
   $$ambiguity_loop{"valid_record_sub"} = 0; 
   }

 my $text_lines = &create_frame($frame_description, $save_frame, $bmrb_hlist, $write_options);

 if ($shift_section)
   {
   $$shift_section{"all_tags"} = $all_tags;
   $$shift_section{"extra_tags"} = $extra_tags;
   }

 return $text_lines;
 }


# has_shifts
#   Returns true if the given bmrb hash structure has any shifts
#
#   Parameters:
#	$bmrb_hlist - reference to bmrb hash structure.
sub has_shifts
  {
  my $bmrb_hlist = shift @_;

  if (exists $$bmrb_hlist{"entity_list"} && ref($$bmrb_hlist{"entity_list"}) eq "HASH")
    {
    foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
      {
      if (exists $$entity{"rlist"} && ref($$entity{"rlist"}) eq "HASH")
	{
	foreach my $residue (values %{$$entity{"rlist"}})
	  {
	  if (exists $$residue{"shifts"} && ref($$residue{"shifts"}) eq "HASH")
	    {
	    foreach my $shift (values %{$$residue{"shifts"}})
	      {
	      if (exists $$shift{"list"} && @{$$shift{"list"}})
		{ return 1; }
	      }
	    }
	  } 
	}
      }
    }

  return 0;
  }

# update_shift_ids
#   updates the shift ids in the bmrb hash structure.
#
#   Parameters:
#	$bmrb_hlist - ref to bmrb hash structure.
#
sub update_shift_ids
  {
  my $bmrb_hlist = shift @_;

  if (! &has_shifts($bmrb_hlist))
    { return; }
 
  my $id_conversion_hash = {};
  my $shift_id = 1;

  # update assigned chemical shifts
  foreach my $entity (sort { $$a{"entity_id"} <=> $$a{"entity_id"}; } (values %{$$bmrb_hlist{"entity_list"}}))
    {     
    foreach my $residue (map { $$entity{"rlist"}{$_}; } (@{$$entity{"name_array"}}))
      {
      foreach my $shift_name (&sort_shift_names(keys %{$$residue{"shifts"}}))
	{
	if (exists $$residue{"shifts"}{$shift_name}{"list"})
	  {
	  for(my $x=0; $x < @{$$residue{"shifts"}{$shift_name}{"list"}}; $x++)
	    {
	    if (! exists $$residue{"shifts"}{$shift_name}{"idlist"} || (ref $$residue{"shifts"}{$shift_name}{"idlist"} ne "ARRAY"))
	      { $$residue{"shifts"}{$shift_name}{"idlist"} = []; }
	    
	    if ($x < @{$$residue{"shifts"}{$shift_name}{"idlist"}})
	      { 
	      $$id_conversion_hash{$$residue{"shifts"}{$shift_name}{"idlist"}[$x]} = $shift_id; 
	      if ($x < @{$$residue{"shifts"}{$shift_name}{"list_id_list"}})
		{ $$id_conversion_hash{$$residue{"shifts"}{$shift_name}{"list_id_list"}[$x] . "_" . $$residue{"shifts"}{$shift_name}{"idlist"}[$x]} = $shift_id; }
	      }
	    
	    $$residue{"shifts"}{$shift_name}{"idlist"}[$x] = $shift_id;
	    $shift_id++;
	    }
	  }
	}
      }
    }
  
  # update ambiguous settings
  if (exists $$bmrb_hlist{"ambiguity_lists"} && ref($$bmrb_hlist{"ambiguity_lists"}) eq "HASH")
    {
    foreach my $ambiguity_list (values %{$$bmrb_hlist{"ambiguity_lists"}})
      {
      for(my $x=0; $x  < @{$$ambiguity_list{"list"}}; $x++)	
	{
	my $shift_id = $$ambiguity_list{"list"}[$x];
	if ($x < @{$$ambiguity_list{"list_id"}})
	  {
	  if (exists $$id_conversion_hash{$$ambiguity_list{"list_id"}[$x] . "_" . $shift_id})
	    { $shift_id = $$id_conversion_hash{$shift_id}; }
	  }
	elsif (exists $$id_conversion_hash{$shift_id})
	  { $shift_id = $$id_conversion_hash{$shift_id}; }
	}
      }
    }
  
  # update peak assignments
  if (exists $$bmrb_hlist{"save_frames"} && (ref $$bmrb_hlist{"save_frames"} eq "ARRAY"))
    {
    foreach my $save_frame (grep {$$_{"type"} eq "spectral_peak_list"; } (@{$$bmrb_hlist{"save_frames"}}))
      {
      if (exists $$save_frame{"data"} && $$save_frame{"data"}{"plist"})
	{
	foreach my $peak (values %{$$save_frame{"data"}{"plist"}})
	  {
	  foreach my $dimension (values %{$$peak{"dimensions"}})
	    {
	    if (exists $$dimension{"assignments"})
	      {
	      foreach my $assignment (@{$$dimension{"assignments"}})
		{
		if (exists $$assignment{"shift_id"})
		  {
		  if (exists $$assignment{"list_id"})
		    {
		    if (exists $$id_conversion_hash{$$assignment{"list_id"} . "_" . $$assignment{"shift_id"}})
		      { $$assignment{"shift_id"} = $$id_conversion_hash{$$assignment{"shift_id"}}; }
		    }
		  elsif (exists $$id_conversion_hash{$$assignment{"shift_id"}})
		    { $$assignment{"shift_id"} = $$id_conversion_hash{$$assignment{"shift_id"}}; }
		  }
		}
	      }
	    }
	  }
	}
      }
    }  
  }

# process_spectral_peak_list_frame
#   Processes a spectral peak list frame and creates an organized data hash structure.
#
#   Parameters:
#       $save_frame - save_frame hash
#	$frame_description - description of the save frame and how to process it.
#	$bmrb_hlist - bmrb hash structure to fill.
#	$read_options - hash of read options.
#
sub process_spectral_peak_list_frame
  {
  my $save_frame = shift @_;
  my $frame_description = shift @_;
  my $bmrb_hlist = shift @_;
  my $read_options = shift @_;

  &process_frame($save_frame, $frame_description, $bmrb_hlist, $read_options);

  if (exists $$save_frame{"data"}{"peak_list_id"} && $$save_frame{"data"}{"peak_list_id"} ne "" && exists $$bmrb_hlist{"peak_lists"} && 
      exists $$bmrb_hlist{"peak_lists"}{$$save_frame{"data"}{"peak_list_id"}} && exists $$bmrb_hlist{"peak_lists"}{$$save_frame{"data"}{"peak_list_id"}}{"plist"} &&
      ref($$bmrb_hlist{"peak_lists"}{$$save_frame{"data"}{"peak_list_id"}}{"plist"}) eq "HASH")
    { $$bmrb_hlist{"peak_lists"}{$$save_frame{"data"}{"peak_list_id"}}{"index_array"} = [ sort { $a <=> $b; } (keys %{$$bmrb_hlist{"peak_lists"}{$$save_frame{"data"}{"peak_list_id"}}{"plist"}}) ]; }
  }

# update_spectral_peak_lists
#   Updates the shift ids in each peak list
#
#   Parameters:
#	$bmrb_hlist - ref to bmrb hash structure.
#	
sub update_spectral_peak_lists
  {
  my $bmrb_hlist = shift @_;

  #build shift id list
  my $shift_id_hash = {};
  foreach my $entity_id (keys %{$$bmrb_hlist{"entity_list"}})
    {
    foreach my $residue (values %{$$bmrb_hlist{"entity_list"}{$entity_id}{"rlist"}})
      {
      foreach my $atom_name (keys %{$$residue{"shifts"}})
	{
	for(my $x=0; $x < @{$$residue{"shifts"}{$atom_name}{"idlist"}}; $x++)
	  {
	  my $id = $$residue{"shifts"}{$atom_name}{"idlist"}[$x];
	  if ($x < @{$$residue{"shifts"}{$atom_name}{"list_id_list"}})
	    { $$shift_id_hash{$$residue{"shifts"}{$atom_name}{"list_id_list"}[$x] . "_" . $id} = [ $residue, $atom_name ]; }
	  else
	    { $$shift_id_hash{$id} = [ $residue, $atom_name ]; }
	  }
	}
      }
    }
  
  # update each peak list
  foreach my $peak_list (values %{$$bmrb_hlist{"peak_lists"}})
    {
    foreach my $peak (values %{$$peak_list{"plist"}})
      {
      foreach my $dimension (values %{$$peak{"dimensions"}})
	{
	if (exists $$dimension{"assignments"})
	  {
	  foreach my $assignment (@{$$dimension{"assignments"}})
	    {
	    my $test_id = $$assignment{"shift_id"};
	    if (exists $$assignment{"list_id"})
	      { $test_id = $$assignment{"list_id"} . "_" . $$assignment{"shift_id"}; }
	    if (exists $$shift_id_hash{$test_id})
	      {
	      $$assignment{"aa"} = $$shift_id_hash{$test_id}[0]{"aa"};
	      $$assignment{"index"} = $$shift_id_hash{$test_id}[0]{"index"};
	      $$assignment{"atom_name"} = $$shift_id_hash{$test_id}[1];
	      }
	    }
	  }
	}
      }
    }
  }

# module must return true
return 1;
