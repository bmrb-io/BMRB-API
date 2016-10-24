#!/usr/bin/perl
#
#  validate_assignments.pl
#	Validates assignments in bmrb format. 
#
#  usage: validate_assignments.pl [options] input_bmrb_file
#
#		bmrb_file  - current assignments in bmrb format
#		options:
#			-author - print report using author indexing.
#			-aromatic - consider aromatic carbons in typing.
#			-clean - remove unknown atom and convert ambiguous atoms (i.e. HB converted to ambiguous HB2 and HB3). 
#			-Ctolerance Cequiv - sets the tolerence for resolving equivalent carbons when analyzing a hCCcoNH TOCSY.
#			-deuteration fraction - set the amount of deuteration to the given fraction (default is 0).
#			-fmean - force the printing of mean values.
#			-fixCACB - fix CA,CB shifts during suspicious typing.
#			-limit n - limit tocsy typing analysis to n peaks per residue.
#			-nitrogen - test the nitrogen shifts too.
#			-nosidechain - don't type considering CG, CD, etc.
#			-notocsy - don't type considering the tocsy data.
#			-output bmrb_file - output bmrb file.
#			-rules consistency - check shift order rules of given/better consistency; range [0.5-1] (default 0.99).
#			-shift min - minimum probability considered consistent (default 0.001).
#			-std - print standard deviation info with mean.
#			-sterilize - remove missassigned atoms
#			-tocsy peak_file - hCCcoNH TOCSY peak list file to analyze.
#			-tolerance Hmax Nratio - tolerance for detecting amide overlap (default 0.04 7 respectively).
#			-type sum  - sum of top typing probabilities used as a cutoff in type checking (default 0.999).
#			-verbose - print out extra info while cleaning or sterilizing.
# XXX David Tolmie Addition
#			-anomalous - only display items with an overall_status of Anomalous.
#			-anno_ltr - generate output to be used for BMRB annotators to send back to the author.  Generally a very short output.
#			-notconsistent - Only print out information that does not have an overal_status value of Consistent.
#			-star_output - output in NMR-STAR 3.0 format.
#			-suspicious - only display items with an overall_status of Suspicious.
# XXX_end
#
#
#   Written by Hunter Moseley, 4/24/2001
#   Copyright Hunter Moseley, 4/24/2001. All rights reserved.   
#
#
#  Updated to use new BMRBParsing/CMapParsing modules.
#  Copyright Hunter Moseley 2005. All rights reserved.
#
#  Updated to include BioMagResBank additions developed by David Tolmie 2006
#  
#

# This version supercedes validate_assignments_31.pl

# These modules allow me to use modules rather than hardcoding everything into one script
use FindBin;
use lib $FindBin::Bin;

# Parser module parses in/out the cmap data and the peak file
use BMRB31Parsing qw(:ALL);
use Peak31Parsing qw(:ALL);

use strict;


# Load needed Modules for Bayesian statistics use BMRB::ChemicalShift;
use BMRB::BayesianCalculations2 qw(:ALL);
use BMRB::BayesianCalculations3 qw(:ALL);
use BMRB::BayesianCalculations4 qw(:ALL);



# Set up the standard variables
my @amino_acid_alist = ("A", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y");

my @carbon_atom_type_alist = qw(CA CB CG CG1 CG2 CD CD1 CD2 CE CE1 CZ CZ2 CZ3 CH2);

my @shift_order_alist = ("", "A", "B", "G", "D", "E", "Z", "H");
my %shift_reverse_order;
for(my $x=0; $x < @shift_order_alist; $x++)
  { $shift_reverse_order{$shift_order_alist[$x]} = scalar(@shift_order_alist) - $x; }

my @nuclei_alist = qw(C H);
# XXX David Tolmie Addition
my @nuclei_alist_bmrb = qw(H C);
# XXX_end

my %average_rank_in_PRTL = (
			    A => 1.072,
			    C => 2.590,
			    D => 2.094,
			    E => 2.095,
			    F => 2.409,
			    G => 1.040,
			    H => 3.019,
			    I => 1.864,
			    K => 1.917,
			    L => 1.503,
			    M => 3.292,
			    N => 1.902,
			    P => 2.123,
			    Q => 2.605,
			    R => 2.720,
			    S => 1.003,
			    T => 1.186,
			    V => 1.620,
			    W => 5.803,
			    Y => 2.946
			   );

# output the usage message if there aren't enough variables or the user asks for help
if ((scalar(@ARGV) < 1) || ($ARGV[0] eq "-h"))
  {
  if (!($ARGV[0] =~ /^-h/))
    {
    print STDERR "\nError:: not enough parameters given.\n";
    print STDERR "\n";
    }

  print STDERR "  validate_assignments.pl\n";
  print STDERR "	Validates assignments in bmrb format. \n";
  print STDERR "\n";
  print STDERR "  usage: validate_assignments.pl [options] input_bmrb_file\n";
  print STDERR "\n";
  print STDERR "		bmrb_file  - current assignments in bmrb format\n";
  print STDERR "		options:\n";
  print STDERR "			-author - print report using author indexing.\n";
  print STDERR "			-aromatic - consider aromatic carbons in typing.\n";
  print STDERR "			-Ctolerance Cequiv - sets the tolerence for resolving equivalent carbons when analyzing a hCCcoNH TOCSY.\n";
  print STDERR "			-clean - remove unknown atom and convert ambiguous atoms (i.e. HB converted to ambiguous HB2 and HB3). \n";
  print STDERR "			-deuteration fraction - set the amount of deuteration to the given fraction (default is 0).\n";
  print STDERR "			-fmean - force the printing of mean values.\n";
  print STDERR "			-fixCACB - fix CA,CB shifts during suspicious typing.\n";
  print STDERR "			-limit n - limit tocsy typing analysis to n peaks per residue.\n";
  print STDERR "			-nitrogen - test the nitrogen shifts too.\n";
  print STDERR "			-nosidechain - don't type considering CG, CD, etc.\n";
  print STDERR "			-notocsy - don't type considering the tocsy data.\n";
  print STDERR "			-output bmrb_file - output bmrb file.\n";
  print STDERR "			-rules consistency - check shift order rules of given/better consistency; range [0.5-1] (default 0.99).\n";
  print STDERR "			-shift min - minimum probability considered consistent (default 0.001).\n";
  print STDERR "			-std - print standard deviation info with mean.\n";
  print STDERR "			-sterilize - remove missassigned atoms\n";
  print STDERR "			-tocsy peak_file - hCCcoNH TOCSY peak list file to analyze.\n";
  print STDERR "			-tolerance Hmax Nratio - tolerance for detecting amide overlap (default 0.04 7 respectively).\n";
  print STDERR "			-type sum  - sum of top typing probabilities used as a cutoff in type checking (default 0.999).\n";
  print STDERR "			-verbose - print out extra info while cleaning or sterilizing.\n";
# XXX David Tolmie Addition
  print STDERR "			-anomalous - only display items with an overall_status of Anomalous.\n";
  print STDERR "			-anno_ltr - generate output to be used for BMRB annotators to send back to the author.  Generally a very short output.\n";
  print STDERR "			-notconsistent - Only print out information that does not have an overal_status value of Consistent.\n";
  print STDERR "			-star_output - output in NMR-STAR 3.0 format.\n";
  print STDERR "			-suspicious - only display items with an overall_status of Suspicious.\n";
# XXX_end

  print STDERR "\n";
  exit(1);
  }


# parse optional command line arguments
my $type_sum_check = 0.999;
my $min_shift_prob = 0.001;
my $use_aromatics = 0;
my $use_sidechains = 1;
my $test_nitrogen = 0;
my $print_std = 0;
my $force_mean_print = 0;
my $clean = 0;
my $sterilize = 0;
my $output_bmrb_filename = "";
my $verbose = 0;
my $H_tolerance = 0.04;
my $N_ratio = 7;
my $C_tolerance = 0.3;
my $tocsy_peaklist_filename = "";
my $limit_peaks = 0;
my $fix_CACB = 0;
my $tocsy_typing = 1;
my $min_rule_consistency = 0.99;
my $deuteration = 0;
my $use_author_indexing = 0;
# XXX David Tolmie Addition
my $star_output = 0;
my $anomalous_output = 0;
my $anno_ltr_output = 0;
my $not_consistent_output = 0;
my $suspicious_output = 0;
my $entry_id = "";
my $entry_line_start = "";
my $entry_line_end = "";
my $skip_output = 0;
# XXX_end

while (@ARGV && ($ARGV[0] =~ /^\-/))
  {
  my $switch = shift @ARGV;
  if ($switch =~ /^\-ty/)
    { $type_sum_check = shift @ARGV; }
  elsif ($switch =~ /^\-sh/)
    { $min_shift_prob = shift @ARGV; }
  elsif ($switch =~ /^\-tol/)
    { 
    $H_tolerance = shift @ARGV; 
    $N_ratio = shift @ARGV; 
    }
  elsif ($switch =~ /^\-toc/)
    { $tocsy_peaklist_filename = shift @ARGV; }
  elsif ($switch =~ /^\-Ct/)
    { $C_tolerance = shift @ARGV; }
  elsif ($switch =~ /^\-l/)
    { $limit_peaks = shift @ARGV; }
  elsif ($switch =~ /^\-aro/)
    { $use_aromatics = 1; }
  elsif ($switch =~ /^\-au/)
    { $use_author_indexing = 1; }
  elsif ($switch =~ /^\-nos/)
    { $use_sidechains = 0; }
  elsif ($switch =~ /^\-notocsy/)
    { $tocsy_typing = 0; }
  elsif ($switch =~ /^\-ni/)
    { $test_nitrogen = 1; }
  elsif ($switch =~ /^\-r/)
    { $min_rule_consistency = shift @ARGV; }
  elsif ($switch =~ /^\-std/)
    { $print_std = 1; }
  elsif ($switch =~ /^\-ste/)
    { $sterilize = 1; }
  elsif ($switch =~ /^\-c/)
    { $clean = 1; }
  elsif ($switch =~ /^\-fm/)
    { $force_mean_print = 1; }
  elsif ($switch =~ /^\-fi/)
    { $fix_CACB = 1; }
  elsif ($switch =~ /^\-o/)
    { $output_bmrb_filename = shift @ARGV; }
  elsif ($switch =~ /^\-v/)
    { $verbose = 1; }
  elsif ($switch =~ /^\-d/)
    { $deuteration = shift @ARGV; }
# XXX David Tolmie Addition
  elsif ($switch =~ /^\-sus/)
    { $suspicious_output = 1; }
  elsif ($switch =~ /^\-notc/)
    { $not_consistent_output = 1; }
  elsif ($switch =~ /^\-anom/)
    { $anomalous_output = 1; }
  elsif ($switch =~ /^\-anno/)
    { 
    $anno_ltr_output = 1; 
    $star_output = 1;
    }
  elsif ($switch =~ /^\-star/)
    { 
    $star_output = 1; 
    # Set up other required flags for NMR-Star output
    $force_mean_print = 1; 
    $print_std = 1; 
    $use_aromatics = 1;
    $test_nitrogen = 1;
    }
# XXX_end
  else
    { 
    print STDERR "INVALID OPTION: $switch\n\nExiting Program ...\n\n";  
    exit(1);
    }
  }

# set the precision to use in printing PRTL lists
my $type_precision = int((-1*log(1-$type_sum_check))/log(10));


if ($test_nitrogen)
  { 
  push @nuclei_alist, "N"; 
# XXX David Tolmie Addition
  push @nuclei_alist_bmrb, "N";
# XXX_end
  }

# parse required command line arguments
my $input_bmrb_filename = shift @ARGV;

if ($input_bmrb_filename =~ /^\s*$/)
  {
  print STDERR "Error:  No filename given.\n";
  exit(1);
  }
# XXX David Tolmie Addition
else 
  {
  # Strip out entry_id value from filename.
  # Filename is in bmr#####.str format.
  $entry_id = $input_bmrb_filename;
  $entry_id =~ s/^[^0-9]*([0-9]*).*$/\1/g;
  }
# XXX_end

if (($deuteration < 0) || ($deuteration > 1))
  {
  print STDERR "Error:  deuteration level outside of [0,1] range.\n";
  exit(1);
  }


# Initialize amino acid statistics for amino acid typing
my ($mean_count, $mean, $variance, $restricted_type_lists, $min_value, $max_value, $ambiguity, $invisible) = &initialize_amino_acid_stats($use_aromatics, $use_sidechains, $deuteration);

my $shift_order_rules = &initialize_rules();

# read the bmrb assignment file
my $bmrb_hlist = &read_bmrb_file($input_bmrb_filename);


# set PRTL hash values for amino acid typing
my %PRTL_props;
$PRTL_props{"mean"} = $mean;
$PRTL_props{"mean_count"} = $mean_count;
$PRTL_props{"variance"} = $variance;
$PRTL_props{"File_ResType_frequencies"} = &aa_frequencies($bmrb_hlist);
$PRTL_props{"restricted_type_lists"} = $restricted_type_lists;
$PRTL_props{"covariance_type_lists"} = $restricted_type_lists;
$PRTL_props{"single_bp_sub"} = \&singleBProbByMeanVarianceChiSquare; 
$PRTL_props{"prior_sub"} = \&deltaPrior; 
$PRTL_props{"CX_prior_sub"} = \&simplePrior; 


# set PRTL hash values for tocsy evaluation
my %PRTL_props_tocsy;
$PRTL_props_tocsy{"mean"} = $mean;
$PRTL_props_tocsy{"mean_count"} = $mean_count;
$PRTL_props_tocsy{"variance"} = $variance;
$PRTL_props_tocsy{"File_ResType_frequencies"} = &aa_frequencies($bmrb_hlist);
$PRTL_props_tocsy{"restricted_type_lists"} = $restricted_type_lists;
$PRTL_props_tocsy{"covariance_type_lists"} = $restricted_type_lists;
$PRTL_props_tocsy{"single_bp_sub"} = \&singleBProbByMeanVarianceChiSquare; 
$PRTL_props_tocsy{"prior_sub"} = \&deltaPrior; 
$PRTL_props_tocsy{"CX_prior_sub"} = \&shiftCountWeightExpPrior; 
$PRTL_props_tocsy{"print_inclusion_statistics"} = 0.05;
$PRTL_props_tocsy{"Shift_Count_Prior_Weight"} = 2.0;


if ($verbose)
  { print "\n"; }

# add ChemicalShift objects for each carbon shift
foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
  {
  foreach my $residue (values %{$$entity{"rlist"}})
    {
    # convert ambiguous shifts and delete extra shifts if clean option given.
    if ($clean)
      {
      my $AA = $$residue{"aa"};
      foreach my $atom (keys %{$$residue{"shifts"}})
	{
	if (exists $$ambiguity{$AA}{$atom} && ! exists $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"first"}} && ! exists $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"second"}})
	  {
	  $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"first"}}{"atom_type"} = $$residue{"shifts"}{$atom}{"atom_type"};
	  $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"second"}}{"atom_type"} = $$residue{"shifts"}{$atom}{"atom_type"};
	  $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"first"}}{"ambiguity_code"} = $$ambiguity{$AA}{$atom}{"value"};
	  $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"second"}}{"ambiguity_code"} = $$ambiguity{$AA}{$atom}{"value"};
	  $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"first"}}{"list"} = [ $$residue{"shifts"}{$atom}{"list"}[0] ];
	  $$residue{"shifts"}{$atom . $$ambiguity{$AA}{$atom}{"second"}}{"list"} = [ $$residue{"shifts"}{$atom}{"list"}[0] ];
	  delete $$residue{"shifts"}{$atom};
	  
	  if ($verbose)
	    { print "Converted ", $$residue{"name"},".$atom to ambiguous ", $atom,$$ambiguity{$AA}{$atom}{"first"}," and ", $atom,$$ambiguity{$AA}{$atom}{"second"}, "\n"; }
	  }
	else
	  { splice(@{$$residue{"shifts"}{$atom}{"list"}},1); }
	}
      }
    
    foreach my $atom (@carbon_atom_type_alist)
      {
      if (exists $$residue{"shifts"}{$atom})
	{ $$residue{"carbon_typing_shifts"}{$atom} = BMRB::ChemicalShift->new( [ $$bmrb_hlist{"filename"}, $$residue{"index"}, $$residue{"aa"}, $atom, $$residue{"shifts"}{$atom}{"list"}[0] ] ); }
      }
    }
  }


# check for overlapping H-N
my $distance2_test = $H_tolerance * $H_tolerance * 8;
foreach my $entity1 (values %{$$bmrb_hlist{"entity_list"}})
  {
  foreach my $residue1 (values %{$$entity1{"rlist"}})
    {
    next if ((! exists $$residue1{"shifts"}{"H"}) || (! exists $$residue1{"shifts"}{"N"}));
    foreach my $entity2 (values %{$$bmrb_hlist{"entity_list"}})
      {
      foreach my $residue2 (values %{$$entity2{"rlist"}})
	{
	next if (($residue1 == $residue2) || (! exists $$residue2{"shifts"}{"H"}) || (! exists $$residue2{"shifts"}{"N"}));
	
	# check for overlap
	if ((($$residue1{"shifts"}{"H"}{"list"}[0] - $$residue2{"shifts"}{"H"}{"list"}[0]) ** 2 + 
	     ($$residue1{"shifts"}{"N"}{"list"}[0] - $$residue2{"shifts"}{"N"}{"list"}[0]) ** 2) <= $distance2_test)
	  {
	  if (! exists $$residue1{"overlap"})
	    { $$residue1{"overlap"} = []; }
	  
	  if (! exists $$residue2{"overlap"})
	    { $$residue2{"overlap"} = []; }
	  
	  push @{$$residue1{"overlap"}}, $$entity2{"entity_id"} . "." . $$residue2{"name"};
	  push @{$$residue2{"overlap"}}, $$entity1{"entity_id"} . "." .  $$residue1{"name"};
	  }
	}  
      }
    }
  }

# read TOCSY peaklist file and add TOCSY peaks as ChemicalShift objects
if ($tocsy_peaklist_filename ne "")
  {
  my $tocsy_peaks_hlist = {};
  $tocsy_peaks_hlist = &parsePeakfile($tocsy_peaklist_filename, ("H", "N", "CX")); 
  
  # cycle through each peak
 PEAK1:  foreach my $peak_index (keys %{$$tocsy_peaks_hlist{"plist"}})
   {
   my $peak = $$tocsy_peaks_hlist{"plist"}{$peak_index};
   my $curr_uses_hlist = {};
   my $closest = 0;
   
   # cycle through each residue
   foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
     {
     foreach my $residue (values %{$$entity{"rlist"}})
       {
       next if ((! exists $$residue{"shifts"}{"H"}) || (! exists $$residue{"shifts"}{"N"}));
       
       my $distance2 = ($$residue{"shifts"}{"H"}{"list"}[0] - $$peak{"shifts"}{"H"}) ** 2 + (($$residue{"shifts"}{"N"}{"list"}[0] - $$peak{"shifts"}{"N"})/$N_ratio) ** 2;
       
       if (($distance2 <= $distance2_test) && exists $$residue{"prev"})
	 {
	 my $update_residue = $$entity{"rlist"}{$$residue{"prev"}};
	 
	 foreach my $atom (grep { $$update_residue{"shifts"}{$_}{"atom_type"} eq "C"; } (keys %{$$update_residue{"shifts"}}))
	   {
	   if (abs($$update_residue{"shifts"}{$atom}{"list"}[0] - $$peak{"shifts"}{"CX"}) <= $C_tolerance)
	     {
	     foreach my $name (keys %$curr_uses_hlist)
	       {
	       my ($entity_id, $res_name) = ($name =~ /^(\d*)[.](\w+)/);
	       delete $$bmrb_hlist{"entity_list"}{$entity_id}{"rlist"}{$res_name}{"carbon_typing_shifts"}{$$curr_uses_hlist{$name}}; 
	       }
	     next PEAK1; 
	     }
	   }
	 
	 $$update_residue{"CX_count"}++;
	 my $atom_name = "CX" . $$update_residue{"CX_count"};
	 my @params = ("PEAK", $peak_index, "X", $atom_name, $$peak{"shifts"}{"CX"});
	 $$update_residue{"carbon_typing_shifts"}{$atom_name} = BMRB::ChemicalShift->new(\@params);
	 $$update_residue{"distance2"}{$atom_name} = $distance2;
	 $$curr_uses_hlist{$$entity{"entity_id"} . "." . $$update_residue{"name"}} = $atom_name;
	 
	 if ((! $closest) || ($$update_residue{"distance2"}{$atom_name} < $$closest[0]{"rlist"}{$$closest[1]}{"distance2"}{$$curr_uses_hlist{$$closest[2]}}))
	   { $closest = [ $entity, $$residue{"prev"}, $$entity{"entity_id"} . "." . $$residue{"prev"} ]; } 
	 }
       }
     }
   
   if ($closest ne "")
     { $$closest[0]{"rlist"}{$$closest[1]}{"closest_CX_count"}++; }
   }  
  
  
  # keep a count of the CX shifts added.  
  foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
    {
    foreach my $residue (values %{$$entity{"rlist"}})
      {
      next if (! exists $$residue{"carbon_typing_shifts"});
      $$residue{"true_CX_count"} = scalar(grep { $_ =~ /^CX/; } (keys %{$$residue{"carbon_typing_shifts"}}));
      }
    }
  
  # remove excess shifts
  if ($limit_peaks)
    {
    foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
      {
      foreach my $residue (values %{$$entity{"rlist"}})
	{
	next if (! exists $$residue{"carbon_typing_shifts"});
	
	my $assigned_count = scalar(grep { $_ !~ /^CX/; } (keys %{$$residue{"carbon_typing_shifts"}}));
	my @CX_shift_alist = sort { $$residue{"distance2"}{$a} <=> $$residue{"distance2"}{$b}; } (grep { $_ =~ /^CX/; } (keys %{$$residue{"carbon_typing_shifts"}}));
	
	next if ($assigned_count + scalar(@CX_shift_alist) <= $limit_peaks);
	
	my $count = 0;
	foreach my $atom (@CX_shift_alist)
	  { 
	  $count++;
	  if (($count + $assigned_count) > $limit_peaks)
	    { delete $$residue{"carbon_typing_shifts"}{$atom}; }
	  }
	}
      }
    }
  }

# initialize PRTL statistics variables
my $rank_in_PRTL = {};
my $typing_statistics = {};
my $shift_statistics = {};
my $overall_statistics = {};
my $tocsy_statistics = {};
my $rule_break_statistics = {};
my $error_summary = [];

# XXX David Tolmie Addition
if (! $star_output)
  {
  print "\nAssignment Validation Software (AVS)\n";
  print "(c) Hunter Moseley and Gaetano Montelione, 2004\n";
  }
# XXX_end

print "\n\n";

# XXX David Tolmie Addition
#  STAR file output Variables
my @avs_star_chem_shift_table;  # used to generate chemical shift loop.
my @avs_star_prtl_table;        # used to generate prtl loop.
my @avs_star_residue_table;
# XXX_end


# iterate through each residue and calculate its PRTL
foreach my $entity (sort { $$a{"entity_id"} <=> $$b{"entity_id"}; } (values %{$$bmrb_hlist{"entity_list"}}))
  {
  foreach my $res_name (@{$$entity{"name_array"}})
    {
    my $residue = $$entity{"rlist"}{$res_name};
    next if (! exists $$residue{"shifts"});
    my $full_res_name;
    if ($use_author_indexing)
      { $full_res_name = $$entity{"entity_id"} . "." . $$entity{"rlist"}{$res_name}{"author_name"}; }
    else
      { $full_res_name = $$entity{"entity_id"} . "." . $res_name; }
    

    # get the current hlist of BMRB::ChemicalShift objects.
    my $shift_hlist = $$residue{"carbon_typing_shifts"};
  
    my @at = (keys %$shift_hlist);
    my $AA = $$residue{"aa"};
  
    if (($$entity{"polymer_class"} !~ /polypeptide/) || ! (grep /^$AA$/, (@amino_acid_alist))) 
      {
# XXX David Tolmie Addition
      if ($star_output && ! $anno_ltr_output)
	{
	# fix by Dimitri Maziuk 9/9/2010
	my ($comp_id, $comp_index_id) = ($res_name =~ /^([^0-9]*)([0-9]+)$/);
        if ($comp_index_id != "")
          {
	  push @avs_star_residue_table, "1 1 " . $$entity{"entity_id" } . " " . $comp_index_id . " " . uc(&convert_aa1to3($comp_id)) . " " . "UNSUPPORTED . . . . . . . " . $entry_id . " 1\n";
	  }
	}
      elsif ($star_output && $anno_ltr_output)
	{
	}
      else
# XXX_end
	{ print $full_res_name, " Overall Status: Residue type $AA not supported.\n\n\n\n"; }
      
      next;
      }
    
    # Determing typing and typing consistency
    my $typing_status;
    my $aatyping = [];  
    if ((ref($shift_hlist) eq "HASH") && scalar(grep { $_ !~ /CX/; } (keys %$shift_hlist)))
      {
      $aatyping = [ &createPRTL($shift_hlist, \%PRTL_props, (($tocsy_peaklist_filename ne "") && $tocsy_typing) + (2 * $fix_CACB), $AA) ];
  
      $$rank_in_PRTL{"count"}{$AA}++;
      my $found = 0;
      $$rank_in_PRTL{"sum"}{$AA} += (grep {$found |= ($$_[0] =~ /$AA/); !$found || ($$_[0] =~ /$AA/); } @$aatyping);
      $$rank_in_PRTL{"diff"}{$AA} += $average_rank_in_PRTL{$AA};
      
      my $sum = 0;
      if (grep { $$_[0] =~ /^$AA$/; } (grep {my $test = ($sum <= $type_sum_check); $sum += $$_[1]; $test; } @$aatyping))
	{ 
	$typing_status = "Consistent"; 
	$$typing_statistics{"Consistent"}++;
	$$rank_in_PRTL{"count_c"}{$AA}++;
	my $found = 0;
	$$rank_in_PRTL{"sum_c"}{$AA} += (grep {$found |= ($$_[0] =~ /$AA/); !$found || ($$_[0] =~ /$AA/); } @$aatyping);
	$$rank_in_PRTL{"diff_c"}{$AA} += $average_rank_in_PRTL{$AA};
	}
      else
	{
	my $alt_aatyping = [ &createPRTL($shift_hlist, \%PRTL_props, 4 + ($tocsy_peaklist_filename ne "") + (2 * $fix_CACB), $AA) ];
	my $sum = 0;
	if (grep { $$_[0] =~ /^$AA$/; } (grep {my $test = ($sum <= $type_sum_check); $sum += $$_[1]; $test; } @$alt_aatyping))
	  { 
	  $typing_status = "Suspicious"; 
	  $$typing_statistics{"Suspicious"}++;
	  }
	else
	  { 
	  $typing_status = "Mistyped"; 
	  $$typing_statistics{"Mistyped"}++;
	  }
	}
      }
    else
      { 
      $typing_status = "Indeterminable"; 
      $$typing_statistics{"Indeterminable"}++;
      }
    

    # determine shift consistency
    my $shift_comments = {};
    my $shift_testing = {};
    foreach my $shift (keys %{$$residue{"shifts"}})
      {
      my $nuclei = substr($shift,0,1);
      if (exists $$mean{$AA}{$shift})
	{
	if (($$residue{"shifts"}{$shift}{"list"}[0] < $$min_value{$AA}{$shift}) || ($$residue{"shifts"}{$shift}{"list"}[0] > $$max_value{$AA}{$shift}))
	  {
	  $$shift_testing{$nuclei . "_Anomalous"} = 1;
	  $$shift_statistics{$nuclei . "_Anomalous"}++;
	  $$shift_comments{$shift} = "(A)";
	  }
	elsif(Statistics::Distributions::chisqrprob(1, (($$mean{$AA}{$shift} - $$residue{"shifts"}{$shift}{"list"}[0]) ** 2)/$$variance{$AA}{$shift} ) < $min_shift_prob)
	  {
	  $$shift_testing{$nuclei . "_Suspicious"} = 1;
	  $$shift_statistics{$nuclei . "_Suspicious"}++;
	  $$shift_comments{$shift} = "(S)";
	  }
	elsif (@{$$residue{"shifts"}{$shift}{"list"}} > 1)
	  {
	  $$shift_testing{$nuclei . "_Duplicate"} = 1;
	  $$shift_statistics{$nuclei . "_Duplicate"}++;
	  $$shift_comments{$shift} = "(D)";
	  }
	else
	  {
	  $$shift_testing{$nuclei . "_Consistent"} = 1;
	  $$shift_statistics{$nuclei . "_Consistent"}++;
	  }
	}
      else
	{ 
	$$shift_testing{$nuclei . "_Unknown"} = 1;
	$$shift_statistics{$nuclei . "_Unknown"}++;
	$$shift_comments{$shift} = "(U)"; 
	}
      }
    
    # determine shifts status
    my @shift_status_alist;
    foreach my $nuclei (@nuclei_alist)
      {
      if ($$shift_testing{$nuclei . "_Anomalous"})
	{ $$shift_testing{$nuclei . "_status"} = "Anomalous"; }
      elsif($$shift_testing{$nuclei . "_Suspicious"})
	{ $$shift_testing{$nuclei . "_status"} = "Suspicious"; }
      elsif($$shift_testing{$nuclei . "_Unknown"})
	{ $$shift_testing{$nuclei . "_status"} = "Unknown"; }
      elsif($$shift_testing{$nuclei . "_Duplicate"})
	{ $$shift_testing{$nuclei . "_status"} = "Duplicate"; }
      elsif($$shift_testing{$nuclei . "_Consistent"})
	{ $$shift_testing{$nuclei . "_status"} = "Consistent"; }
      else
	{ $$shift_testing{$nuclei . "_status"} = "Indeterminable"; }
      
      push @shift_status_alist, $$shift_testing{$nuclei . "_status"};
      }
    
    # determine tocsy assignment status
    my $tocsy_status = "";
    my $tocsy_assignable;
    my $tocsy_missing;
    my $tocsy_missing_unique;
    my $tocsy_expected;
    my $tocsy_usable;
    my $tocsy_total_unique;
    my $tocsy_usable_unique;
    if ($tocsy_peaklist_filename ne "")
      {
      $tocsy_expected = scalar(@{$$restricted_type_lists{$AA}});
      $tocsy_assignable = &count_assignable($shift_hlist, $AA);
      $tocsy_usable = scalar(keys %$shift_hlist);
      $tocsy_total_unique = $$residue{"closest_CX_count"} + scalar(grep { $_ !~ /CX/; } (keys %$shift_hlist)); 
      $tocsy_usable_unique = $tocsy_total_unique;
      if ($tocsy_total_unique > $tocsy_usable)
	{ $tocsy_usable_unique = $tocsy_usable; }
      $tocsy_missing = -($tocsy_assignable);
      $tocsy_missing_unique = -($tocsy_assignable);
      if ($tocsy_usable < $tocsy_expected)
	{ $tocsy_missing += $tocsy_usable; }
      else
	{ $tocsy_missing += $tocsy_expected; }
      if ($tocsy_usable_unique < $tocsy_expected)
	{ $tocsy_missing_unique += $tocsy_usable_unique; }
      else
	{ $tocsy_missing_unique += $tocsy_expected; }
      
      if (($tocsy_missing_unique > 1) || (($tocsy_missing_unique == 1) && ($tocsy_usable_unique > $tocsy_expected)))
	{ 
	$tocsy_status = "Suspicious"; 
	$$tocsy_statistics{"Suspicious"}++;
	}
      else
	{ 
	$tocsy_status = "Consistent"; 
	$$tocsy_statistics{"Consistent"}++;
	}
      }
    
    
    # Check for breaking of shift order rules
    my $rule_break_status = "";
    my @rule_breaks = ();
    if ($min_rule_consistency)
      {
      foreach my $rule (@{$$shift_order_rules{$AA}})
	{
	if (($$rule{"consistency"} >= $min_rule_consistency) && exists $$residue{"shifts"}{$$rule{"shift1"}} && exists $$residue{"shifts"}{$$rule{"shift2"}} && ($$residue{"shifts"}{$$rule{"shift1"}}{"list"}[0] < $$residue{"shifts"}{$$rule{"shift2"}}{"list"}[0]))
	  { push @rule_breaks, $rule; }
	}

      if (@rule_breaks)
	{ 
	$rule_break_status = "Suspicious"; 
	$$rule_break_statistics{"Suspicious"}++;
	}
      else
	{ 
	$rule_break_status = "Consistent"; 
	$$rule_break_statistics{"Consistent"}++;
	}
      }
    
    
    # determine overall status
    my $overall_status;
    if ($typing_status eq "Mistyped")
      { 
      $overall_status = "Mistyped"; 
      $$overall_statistics{"Mistyped"}++;
      }
    elsif (grep { $_ eq "Anomalous" } (@shift_status_alist))
      { 
      $overall_status = "Anomalous"; 
      $$overall_statistics{"Anomalous"}++;
      }
    elsif(($typing_status eq "Suspicious") || (grep { $_ eq "Suspicious" } (@shift_status_alist)) || ($tocsy_status eq "Suspicious") || ($rule_break_status eq "Suspicious"))
      { 
      $overall_status = "Suspicious"; 
      $$overall_statistics{"Suspicious"}++;
      }
    elsif((grep { $_ eq "Unknown" } (@shift_status_alist)) || (grep { $_ eq "Duplicate" } (@shift_status_alist)))
      { 
      $overall_status = "Clerical"; 
      $$overall_statistics{"Clerical"}++;
      }
    elsif(($typing_status eq "Consistent") || (grep { $_ eq "Consistent" } (@shift_status_alist)) || ($tocsy_status eq "Consistent") || ($rule_break_status eq "Consistent"))
      { 
      $overall_status = "Consistent"; 
      $$overall_statistics{"Consistent"}++;
      }
    else
      { 
      $overall_status = "Indeterminable"; 
      $$overall_statistics{"Indeterminable"}++;
      }
    

# XXX David Tolmie Addition
    #
    #  Skip printing of information if the "skip_output"
    #  flag is set.  This is set by command line 
    #  arguments that are used to filter on Overall 
    #  status values.
    #
    if (($anomalous_output) || ($not_consistent_output) || ($suspicious_output))
      {
      $skip_output = 1;
      if (($not_consistent_output) && ($overall_status ne "Consistent"))
        { $skip_output = 0; }
      elsif (($anomalous_output) && ($overall_status eq "Anomalous"))
        { $skip_output = 0; }
      elsif (($suspicious_output) && ($overall_status eq "Suspicious"))
        { $skip_output = 0; }
      next if ($skip_output);
      }
    
    # print Status Info
    if ($star_output && ! $anno_ltr_output)
      {
	# fix by Dimitri Maziuk 9/9/2010
      my ($comp_id, $comp_index_id) = ($res_name =~ /^([^0-9]*)([0-9]+)$/);
# XXX David Tolmie added
      #  $entry_line_start = $entry_id . " 1 1 1 " . $$entity{"entity_id"} . " " . $comp_index_id . " " . uc(&convert_aa1to3($comp_id)) . " ";
      $entry_line_start = " 1 1 " . $$entity{"entity_id"} . " " . $comp_index_id . " " . uc(&convert_aa1to3($comp_id)) . " ";
      $entry_line_end = " " . $entry_id . " 1 ";
      my $residue_row = $entry_line_start . $overall_status . " " . $typing_status . " ";
      if ($rule_break_status ne "")
	{ $residue_row .= $rule_break_status . " "; }
      else
	{ $residue_row .= ". "; }

      foreach my $nuclei (@nuclei_alist_bmrb)
	{ $residue_row .= $$shift_testing{$nuclei . "_status"} . " "; }

      if (@rule_breaks)
	{
	my $first_rb_row = 1;
        foreach my $rule (@rule_breaks)
          { 
	  if (! $first_rb_row )
            { $residue_row = $entry_line_start . ". . . . . . "; }
	   $residue_row .= sprintf " \"%s > %s\" %5.4f ",$$rule{"shift1"},$$rule{"shift2"},$$rule{"consistency"}; 
          $residue_row .= $entry_line_end . "\n";
	  push @avs_star_residue_table, $residue_row;
	  $first_rb_row = 0;
          }
	}
      else
	{
	$residue_row .= " . . " . $entry_line_end . "\n";
	push @avs_star_residue_table, $residue_row;
	}
      }
    elsif ($star_output && $anno_ltr_output)
      {
      # fix by Dimitri Maziuk 9/9/2010
      my ($comp_id, $comp_index_id) = ($res_name =~ /^([^0-9]*)([0-9]+)$/);
      my $ws1 = "       ";
      if (length($comp_index_id) == 2) 
	{ $ws1 = "      "; }
      elsif (length($comp_index_id) == 3) 
	{ $ws1 = "     "; }
      elsif (length($comp_index_id) == 4) 
	{ $ws1 = "   "; }
      my $ws2 = "     ";
      $entry_line_start = " 1   " . $comp_index_id . $ws1 . uc(&convert_aa1to3($comp_id)) . $ws2;
      }
    else
# XXX_end
      {
      # print Status Info
      print $full_res_name, "\tOverall: $overall_status \tTyping: $typing_status";
      if ($tocsy_status ne "")
	{ print " \tTOCSY: $tocsy_status"; }
      if ($rule_break_status ne "")
	{ print " \tSRO: $rule_break_status"; }
      foreach my $nuclei (@nuclei_alist)
	{ print " \t$nuclei Shifts: ",$$shift_testing{$nuclei . "_status"}; }
      print "\n\n";

      # print PRTL Info
      if (@$aatyping)
	{
	print "\tPRTL>>\t";
	foreach my $typed (@$aatyping)
	  {
	  my $value = ((int ($$typed[1] * (10 ** $type_precision))) / (10 ** $type_precision));
	  if ($value > 0)
	    { print $$typed[0], " ", $value, "   "; }
	  }
	print "\n";
	}
      
      print "\n";
    
    
      # print overlap info
      if (exists $$residue{"overlap"})
	{ print "\tHN Overlap>>\t ",join(" ",@{$$residue{"overlap"}}),"\n\n"; }
    
      # print tocsy assignment info
      if ($tocsy_peaklist_filename ne "")
	{ 
	print "\tTOCSY Evaluation>>  Expected: $tocsy_expected  Usable: $tocsy_usable  Unique:$tocsy_total_unique($tocsy_usable_unique)  Assignable: $tocsy_assignable  Missing: $tocsy_missing($tocsy_missing_unique)\n\n";
	}
    
      # Create error_summary 
      if (($typing_status ne "Consistent") && ($typing_status ne "Indeterminable"))
	{ push @$error_summary,  $full_res_name . "\tTyping: " . $typing_status . "\n"; }
      if (($tocsy_status ne "") && ($tocsy_status ne "Consistent") && ($tocsy_status ne "Indeterminable"))
	{ push @$error_summary,  $full_res_name . "\tTOCSY: " . $tocsy_status . "\n"; }    
      }


    # print shifts Info
    foreach my $nuclei (@nuclei_alist)
      {
      my @shift_alist = (sort { ($shift_reverse_order{substr($b,1,1)} . (1 / (1 + substr($b,2)))) <=> ($shift_reverse_order{substr($a,1,1)} . (1 / (1 + substr($a,2)))) } 
			 (grep /^$nuclei/, (keys %{$$residue{"shifts"}})));

      if (@shift_alist)
	{
# XXX David Tolmie Addition
	if ($star_output && ! $anno_ltr_output)
	  {
          for(my $x=0; $x < @shift_alist; $x++)
	    {
	    my $val1 = "";
	    my $val2 = "";
	    my $val3 = "";
	    my $val4 = "";
      	    $val1 = $shift_alist[$x] . " " . $$residue{"shifts"}{$shift_alist[$x]}{"list"}[0];
            if ($$shift_comments{$shift_alist[$x]} ne "")
              { 
	      my $shift_typing = $$shift_comments{$shift_alist[$x]};
	      $shift_typing =~ s/^[^A-Z]*([A-Z]*).*$/\1/g;
	      $val2 = " " . $shift_typing . " "; 
              }
            else
              { $val2 = " . "; }
	    if (($$shift_testing{$nuclei . "_status"} ne "Consistent") || ($nuclei eq "C" && $typing_status ne "Consistent") || $force_mean_print )
	      {
              my $chem_shift_row = "";
    	      my $std_info = sqrt($$variance{$AA}{$shift_alist[$x]}) . " ";
	      if ($$mean{$AA}{$shift_alist[$x]} ne  "")
		{ $val3 = $$mean{$AA}{$shift_alist[$x]} . " " . $std_info . " "; }
	      else
		{ $val3 = ". " . $std_info . " "; }
	      if ($$shift_comments{$shift_alist[$x]} ne "(U)")
		{ $val4 = sprintf("%6.4e ",Statistics::Distributions::chisqrprob(1, (($$mean{$AA}{$shift_alist[$x]} - $$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) ** 2)/$$variance{$AA}{$shift_alist[$x]})); }
	      else
		{ $val4 = "."; }

	      $chem_shift_row = $entry_line_start . $val1 . $val2 . $val3 . $val4 . $entry_line_end . "\n";
	      push @avs_star_chem_shift_table, $chem_shift_row; 
	      }
	    }
	  }
	elsif ($star_output && $anno_ltr_output)
	  {
          for(my $x=0; $x < @shift_alist; $x++)
	    {
	    my $val1 = "";
	    my $val2 = "";
	    my $val3 = "";
	    my $print_cs_row = 0;
	    my $ws3 = "     ";
            if (length($shift_alist[$x]) == 2)
	      { $ws3 = "      "; }
            elsif (length($shift_alist[$x]) == 4)
            { $ws3 = "    "; }
            elsif (length($shift_alist[$x]) == 1)
	      { $ws3 = "       "; }
      	    $val1 = $shift_alist[$x] . $ws3 . $$residue{"shifts"}{$shift_alist[$x]}{"list"}[0];
            if ($$shift_comments{$shift_alist[$x]} ne "")
              { 
	      my $shift_typing = $$shift_comments{$shift_alist[$x]};
	      $shift_typing =~ s/^[^A-Z]*([A-Z]*).*$/\1/g;
	      if ($shift_typing eq "A" || $shift_typing eq "D" || $shift_typing eq "S")
                { $print_cs_row = 1; }
	      else
                { $print_cs_row = 0; }
	      if ( length($$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) == 6 )
                { $val2 = "    " . $shift_typing; }
	      elsif ( length($$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) == 4 )
                { $val2 = "      " . $shift_typing; }
	      elsif ( length($$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) == 3 )
                { $val2 = "       " . $shift_typing; }
	      elsif ( length($$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) == 5 )
                { $val2 = "     " . $shift_typing; }
	      elsif ( length($$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) == 7 )
                { $val2 = "   " . $shift_typing; }
	      elsif ( length($$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) == 8 )
                { $val2 = "  " . $shift_typing; }
	      else
                { $val2 = "    " . $shift_typing; }
              }
            else
              { 
	      $val2 = "."; 
	      $print_cs_row = 0;
              }
	    if (($$shift_testing{$nuclei . "_status"} ne "Consistent") || ($nuclei eq "C" && $typing_status ne "Consistent") || $force_mean_print )
	      {
              my $chem_shift_row = "";
    	      my $std_info = sqrt($$variance{$AA}{$shift_alist[$x]}) . " ";
	      if ($$mean{$AA}{$shift_alist[$x] } ne  "")
		{
		if (length($$mean{$AA}{$shift_alist[$x] }) ==  5)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "     " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  6)
		  { $val3 = "    " . $$mean{$AA}{$shift_alist[$x]} . "    " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  7)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "   " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  8)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "  " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  4)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "      " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  3)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "       " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  2)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "        " . $std_info; }
		elsif (length($$mean{$AA}{$shift_alist[$x] }) ==  1)
		  { $val3 = "     " . $$mean{$AA}{$shift_alist[$x]} . "         " . $std_info; }
		}
	      else
		{ $val3 = "     .         " . $std_info; }
	      if ($print_cs_row)
		{
		my $ws4 = "    ";
		if (length($std_info) == 3)
		  { $ws4 = "     "; }
		elsif (length($std_info) == 5)
		  { $ws4 = "   "; }
		elsif (length($std_info) == 6)
		  { $ws4 = "  "; }
		elsif (length($std_info) == 2)
		  { $ws4 = "      "; }
		elsif (length($std_info) == 1)
		  { $ws4 = "       "; }
		$chem_shift_row = $entry_line_start . $val1 . $val2 . $val3 . $ws4 . " ?       ? " . $entry_line_end . "\n";
		push @avs_star_chem_shift_table, $chem_shift_row; 
		}
	      }
	    }
	  }
	else
# XXX_end
	  {
	  print "\t$nuclei Shift Assignments>>";
	  for(my $x=0; $x < @shift_alist; $x++)
	    {
	    print "\n\t\t\t" if ($x && ! ($x % 6));
	    print " \t",$shift_alist[$x]," :: ", $$residue{"shifts"}{$shift_alist[$x]}{"list"}[0],$$shift_comments{$shift_alist[$x]}, "\t" x $print_std;
	    if ($$shift_comments{$shift_alist[$x]} ne "")
	      {
	      my $extra_info = ",\t Expected = " . sprintf("%5.2f",$$mean{$AA}{$shift_alist[$x]}) . ", Std = " . sprintf("%5.4f",sqrt($$variance{$AA}{$shift_alist[$x]})) . ", ChiSquare = " . sprintf("%6.4e",Statistics::Distributions::chisqrprob(1, (($$mean{$AA}{$shift_alist[$x]} - $$residue{"shifts"}{$shift_alist[$x]}{"list"}[0]) ** 2)/$$variance{$AA}{$shift_alist[$x]})) if ($$shift_comments{$shift_alist[$x]} ne "(U)");
	      push @$error_summary, $full_res_name . "\t" . $shift_alist[$x] . " = " . $$residue{"shifts"}{$shift_alist[$x]}{"list"}[0] . $$shift_comments{$shift_alist[$x]} . $extra_info . "\n"; 
	      }
	    }
	  
	  print "\n";
	  if (($$shift_testing{$nuclei . "_status"} ne "Consistent") || ($nuclei eq "C" && $typing_status ne "Consistent") || $force_mean_print )
	    {
	    print "\tAve $nuclei Shift Values>>";
	    my @shift_alist = (sort { ($shift_reverse_order{substr($b,1,1)} . (1 / (1 + substr($b,2)))) <=> ($shift_reverse_order{substr($a,1,1)} . ( 1 / ( 1 + substr($a,2)))) } 
			       (grep { ! $$invisible{$AA}{$_}; } (grep /^$nuclei/, (keys %{$$mean{$AA}}))));
	    for(my $x=0; $x < @shift_alist; $x++)
	      {
	      print "\n\t\t\t" if ($x && ! ($x % 6));
	      my $std_info = "(" . sqrt($$variance{$AA}{$shift_alist[$x]}) . ")";
	      print " \t",$shift_alist[$x]," :: ", $$mean{$AA}{$shift_alist[$x]},$std_info x $print_std;
	      }
	    
	    print "\n";
	    }
	  
	  my $deletion = 0;
	  for(my $x=0; $x < @shift_alist; $x++)
	    {
	    if (($sterilize && $$shift_comments{$shift_alist[$x]} eq "(M)") || ($clean && $$shift_comments{$shift_alist[$x]} eq "(U)"))
	      { 
	      print "\tDeletions>>" if (! $deletion && $verbose);
	      print " \t",$shift_alist[$x] if ($verbose);
	      $deletion = 1;
	      delete $$residue{"shifts"}{$shift_alist[$x]}; 
	      }
	    }
	  if ($deletion && $verbose)
	    { print "\n"; }
	  
	  print "\n";
	  }
	}
      }
    
# XXX David Tolmie Addition
    # print PRTL Info if BMRB output is selected.
    if ($star_output && ! $anno_ltr_output)
      {
      if (@$aatyping)
	{
	foreach my $typed (@$aatyping)
	  {
	  my $value = ((int ($$typed[1] * (10 ** $type_precision))) / (10 ** $type_precision));
	  if ($value > 0)
	    { 
	    my $prtl_row = $entry_line_start . uc(&convert_aa1to3($$typed[0])) . " " . $value . " " . $entry_line_end . "\n"; 
	    push @avs_star_prtl_table, $prtl_row;
	    }
	  }
	}
      }
    elsif (! $star_output)
# XXX_end
      {

      if (@rule_breaks)
	{
	print "\tSRO Rule Breaks>> ";
	my $count = 1;
	foreach my $rule (@rule_breaks)
	  { 
	  if ( !($count++ % 5) )
	    { print "\n\t\t"; }
	  printf " \t(%s > %s : %5.4f)",$$rule{"shift1"},$$rule{"shift2"},$$rule{"consistency"}; 
	  push @$error_summary, $full_res_name . "\tSRO Rule Break>>  " . $$rule{"shift1"} . " > " . $$rule{"shift2"} . " : " . $$rule{"consistency"} . "\n";
	  }
	print "\n";
	}

      print "\n\n";
      }
    }
  }


# XXX David Tolmie Addition
if ($star_output && ! $anno_ltr_output)
  {
  #  Print output in NMR-STAR 3.0 format if requested.
  print "data_AVS_bmrb_pdb_report_" . $entry_id . "\n\n";
  print "save_AVS_chem_shift_analysis\n";
  print "    _AVS_report.Sf_category          AVS_report\n";
  print "    _AVS_report.Sf_framecode         AVS_chem_shift_analysis\n";
  print "    _AVS_report.Entry_ID             $entry_id\n";
  print "    _AVS_report.ID                   1\n";
  print "    _AVS_report.Software_ID          1\n";
  print "    _AVS_report.Software_label       \$AVS\n\n";

  if (@avs_star_residue_table)
    {  
    print "loop_\n";
    print "    _AVS_analysis.Assembly_ID\n";
    print "    _AVS_analysis.Entity_assembly_ID\n";
    print "    _AVS_analysis.Entity_ID\n";
    print "    _AVS_analysis.Comp_index_ID\n";
    print "    _AVS_analysis.Comp_ID\n";
    print "    _AVS_analysis.Comp_overall_assignment_score\n";
    print "    _AVS_analysis.Comp_typing_score\n";
    print "    _AVS_analysis.Comp_SRO_score\n";
    print "    _AVS_analysis.Comp_1H_shifts_analysis_status\n";
    print "    _AVS_analysis.Comp_13C_shifts_analysis_status\n";
    print "    _AVS_analysis.Comp_15N_shifts_analysis_status\n";
    print "    _AVS_analysis.SRO_rule_break\n";
    print "    _AVS_analysis.SRO_rule_break_probability\n";
    print "    _AVS_analysis.Entry_ID\n";
    print "    _AVS_analysis.AVS_report_ID\n\n";

    foreach my $row (@avs_star_residue_table)
      { print $row; }
    
    print "\nstop_\n\n";
    }
  
  # Print chem shift table
  if (@avs_star_chem_shift_table)
    {
    print "loop_\n";
    print "    _AVS_analysis.Assembly_ID\n";
    print "    _AVS_analysis.Entity_assembly_ID\n";
    print "    _AVS_analysis.Entity_ID\n";
    print "    _AVS_analysis.Comp_index_ID\n";
    print "    _AVS_analysis.Comp_ID\n";
    print "    _AVS_analysis.Atom_ID\n";
    print "    _AVS_analysis.Observed_chem_shift\n";
    print "    _AVS_analysis.Observed_chem_shift_typing\n";
    print "    _AVS_analysis.Stat_chem_shift_expected\n";
    print "    _AVS_analysis.Stat_chem_shift_std\n";
    print "    _AVS_analysis.Stat_chem_shift_chi_sqr\n";
    print "    _AVS_analysis.Entry_ID\n";
    print "    _AVS_analysis.AVS_report_ID\n\n";
    
    foreach my $row (@avs_star_chem_shift_table)
      { print $row; }

    print "\nstop_\n\n";
    }
  
  #  Print PRTL table
  if (@avs_star_prtl_table)
    {
    print "loop_\n";
    print "    _AVS_analysis.Assembly_ID\n";
    print "    _AVS_analysis.Entity_assembly_ID\n";
    print "    _AVS_analysis.Entity_ID\n";
    print "    _AVS_analysis.Comp_index_ID\n";
    print "    _AVS_analysis.Comp_ID\n";
    print "    _AVS_analysis.PRTL_comp_type\n";
    print "    _AVS_analysis.PRTL_probability_score\n";
    print "    _AVS_analysis.Entry_ID\n";
    print "    _AVS_analysis.AVS_report_ID\n\n";
    foreach my $row (@avs_star_prtl_table)
      { print $row; }
   
    print "\nstop_\n\n";
    }
  
  print "\nsave_\n\n";
  
  print "save_AVS\n";
  print "_Software.Sf_category          software\n";
  print "_Software.Sf_framecode         AVS\n";
  print "_Software.Entry_ID             $entry_id\n";
  print "_Software.ID                   1\n";
  print "_Software.Name                \"AutoPeak - validate_assignments\"\n";
  print "_Software.Version              2011-12-10\n"; # 2011-12-10
  print "_Software.Details             \n";
  print ";\nOriginal version modified by BMRB to export results in a BMRB STAR format. Changed status \"Misassigned\" to \"Anomalous\"\n;\n\n";
  
  print "  loop_\n";
  print "     _Vendor.Name\n";
  print "     _Vendor.Address\n";
  print "     _Vendor.Electronic_address\n";
  print "     _Vendor.Entry_ID\n";
  print "     _Vendor.Software_ID\n\n";
  print "  \"Hunter Moseley\"\n";
  print "\n;\nCenter for Advanced Biotechnology and Medicine\n";
  print "Rutgers University\n679 Hoes Lane, Piscataway NJ 08854-5638\n;\n\n";
  print "  hunter\@cabm.rutgers.edu\n";
  print "  $entry_id   1 \n\n";
  print "  stop_\n\n";
  
  print "  loop_\n";
  print "    _Task.Task\n";
  print "    _Task.Entry_ID\n";
  print "    _Task.Software_ID\n\n";
  print "  \"validate protein chemical shift assignments\"  $entry_id   1 \n\n";
  print "  stop_\n\n";
  
  print "  loop_\n";
  print "    _Software_citation.Citation_ID\n";
  print "    _Software_citation.Citation_label\n";
  print "    _Software_citation.Entry_ID\n";
  print "    _Software_citation.Software_ID\n\n";
  print "  2  \$AVS_citation  $entry_id   1 \n\n";
  print "  stop_\n\n";
  print "save_\n\n";
  
  print "save_AVS_citation\n";
  print "  _Citation.Sf_category       citation\n";
  print "  _Citation.Sf_framecode      AVS_citation\n";
  print "  _Citation.Entry_ID          $entry_id\n";
  print "  _Citation.ID                2\n";
  print "  _Citation.Class             citation\n";
  print "  _Citation.PubMed_ID         14872126\n";
  print "  _Citation.Full_citation\n";
  print ";\nMoseley HN, Sahota G, Montelione GT., Assignment validation software suite \nfor the evaluation and presentation of protein resonance assignment data.\nJ Biomol NMR. 28, 341-55 (2004)\n;\n\n";
  print "  _Citation.Status           published\n";
  print "  _Citation.Type             journal\n\n";
  print "save_\n";
  
  }
elsif ($star_output && $anno_ltr_output)
  {
  if (@avs_star_chem_shift_table)
    {
    print "Anomalous Chemical Shift Assignments:\n\n";
    
    print "The assigned chemical shifts in the following table have been reported as \nanomalous, suspicious, or duplicate (A, S or D respectively, in the Error Msg. \ncolumn) by the software currently employed by BMRB to check for chemical shift \noutliers [Moseley, et al., J. Biomol. NMR 28, 341-355 (2004)].  Please verify \nthese assignments by replacing the question marks in the 'Code' column of the \ntable with the appropriate code.  The codes to use are: V = verified, \nD = delete, and R = replace.  Where R is indicated, please supply the revised \nchemical shift value in the Replace C.S. column of the table.  If there are a \nlarge number of revised chemical shifts, it may be more convenient to edit the \nfull NMR-STAR file.  Please inform the annotator in charge of the entry of your \nmodifications.\n\n";
    
    print "                                                               Author Verify\n";
    print "Mol  Res.    Res.    Atom    Observed  Error Expected  Std.    Code    Replace\n";
    print "ID   #       Type    ID      C.S.      Msg.  C.S.      Dev.            C.S.\n";
      print "-----------------------------------------------------------------------------\n";
    foreach my $row (@avs_star_chem_shift_table)
      { print $row; }

    print "\nThe full report is available from this URL:\n\n";
    }
  }
elsif (! $star_output)
# XXX_end
  {  
  # print overall results
  print "\n\n";
  print "###########################################################################\n\n";
  print "Overall Results:\n\n\t";
  foreach my $category (qw(Consistent Clerical Suspicious Anomalous Mistyped Indeterminable))
    { printf "      \#%s: %3d", $category, $$overall_statistics{$category} * 1; }
  print "\n";
  
  # print typing overall results
  print "\n\n";
  print "Typing Results:\n\n\t";
  foreach my $category (qw(Consistent Suspicious Mistyped Indeterminable))
    { printf "      \#%s: %3d", $category,$$typing_statistics{$category} * 1; }
  print "\n";
  
  
  # print TOCSY overall results
  if ($tocsy_peaklist_filename ne "")
    {
    print "\n\n";
    print "TOCSY Results:\n\n\t";
    foreach my $category (qw(Consistent Suspicious))
      { printf "      \#%s: %3d", $category,$$tocsy_statistics{$category} * 1; }
    print "\n";
    }
  
  # print Shift Order overall results
  print "\n\n";
  print "Shift Relative Order (SRO) Results:\n\n\t";
  foreach my $category (qw(Consistent Suspicious))
    { printf "      \#%s: %3d", $category,$$rule_break_statistics{$category} * 1; }
  print "\n";
  
  
  
  # print shift overall results
  foreach my $nuclei (@nuclei_alist)
    {
    print "\n\n";
    print "$nuclei Shift Results:\n\n\t";
    foreach my $category (qw(Consistent Duplicate Unknown Suspicious Anomalous))
      { printf "      \#%s:%4d", $category, $$shift_statistics{$nuclei . "_" . $category} * 1; }
    print "\n";
    }
  
  
  # print error summary
  if (@$error_summary)
    {
    print "\n\n\nError Summary:\n\n";
    foreach my $error_line (@$error_summary)
      { print $error_line; }
    }
  
#
#   NOT USED
#
# Print average PRTL Statistics
##print "\nRank in PRTL:\n\n";
##print "\t     Full\tFull\t\tConsistent\tConsistent\n";
##print "\tAA:  Average\tDiff\t\tAverage\t\tDiff\n";
##foreach my $AA (@amino_acid_alist)
##  {
##  $$rank_in_PRTL{"average"}{$AA} = $$rank_in_PRTL{"sum"}{$AA} / $$rank_in_PRTL{"count"}{$AA}   if ($$rank_in_PRTL{"count"}{$AA});
##  $$rank_in_PRTL{"avg_diff"}{$AA} = ( $$rank_in_PRTL{"sum"}{$AA} - $$rank_in_PRTL{"diff"}{$AA}) / $$rank_in_PRTL{"count"}{$AA}   if ($$rank_in_PRTL{"count"}{$AA});
##  $$rank_in_PRTL{"average_aa"} += $$rank_in_PRTL{"average"}{$AA};
##  $$rank_in_PRTL{"avg_diff_aa"} += $$rank_in_PRTL{"avg_diff"}{$AA};
##
##  $$rank_in_PRTL{"average_c"}{$AA} = $$rank_in_PRTL{"sum_c"}{$AA} / $$rank_in_PRTL{"count_c"}{$AA}   if ($$rank_in_PRTL{"count_c"}{$AA});
##  $$rank_in_PRTL{"avg_diff_c"}{$AA} = ( $$rank_in_PRTL{"sum_c"}{$AA} - $$rank_in_PRTL{"diff_c"}{$AA}) / $$rank_in_PRTL{"count_c"}{$AA}   if ($$rank_in_PRTL{"count_c"}{$AA});
##  $$rank_in_PRTL{"average_aa_c"} += $$rank_in_PRTL{"average_c"}{$AA};
##  $$rank_in_PRTL{"avg_diff_aa_c"} += $$rank_in_PRTL{"avg_diff_c"}{$AA};
##  
##  printf("\t%s:   %3.6f\t%3.6f\t%3.6f\t%3.6f\n", $AA, $$rank_in_PRTL{"average"}{$AA}, $$rank_in_PRTL{"avg_diff"}{$AA}, $$rank_in_PRTL{"average_c"}{$AA}, $$rank_in_PRTL{"avg_diff_c"}{$AA} );
##  }
##
##print "\t---------------------------------------------------------\n";
##$$rank_in_PRTL{"average_aa"} /= scalar(@amino_acid_alist);
##$$rank_in_PRTL{"avg_diff_aa"} /= scalar(@amino_acid_alist);
##
##$$rank_in_PRTL{"average_aa_c"} /= scalar(@amino_acid_alist);
##$$rank_in_PRTL{"avg_diff_aa_c"} /= scalar(@amino_acid_alist);
##
##printf("\tAve: %3.6f\t%3.6f\t%3.6f\t%3.6f\n\n", $$rank_in_PRTL{"average_aa"}, $$rank_in_PRTL{"avg_diff_aa"}, $$rank_in_PRTL{"average_aa_c"}, $$rank_in_PRTL{"avg_diff_aa_c"});
##
##print "\n\n";
  }

# print output bmrb file
if ($output_bmrb_filename ne "")
  { &write_bmrb_file($bmrb_hlist,$output_bmrb_filename); }



#
#  Subroutines
#


# aa_frequencies
#   returns the frequency of the 20 amino acids in the given bmrb file as a hash.
#	$$protein_hlist{"bmrb_filename"}{$residue_type}
#
# Parameters:
#	$bmrb_hlist - reference to bmrb hash structure.
#
sub aa_frequencies
  {
    my $bmrb_hlist = shift @_;

    my $protein_hlist={};
    foreach my $entity (values %{$$bmrb_hlist{"entity_list"}})
      {
      foreach my $residue (split("",$$entity{"sequence"}))
	{ 
	$$protein_hlist{$$bmrb_hlist{"filename"}}{$residue}++; 
	$$protein_hlist{"HNCO"}{$residue}++; 
	$$protein_hlist{"PEAK"}{$residue}++; 
	}
      }

    return $protein_hlist;
  }


# createPRTL
#   Creates and returns a PRTL by calling the appropriate Bayesian Typing method
#
# Parameters:
#	$res_shift_hlist - hash of shift_name to ChemicalShift
#	$PRTL_props - hash of properties used by Bayesian Typing methods
#	$typing_regime - code for the typing method to use.
#	$actual_AA - actual amino acid for the $res_shift_hlist
#
sub createPRTL
  {
  my $res_shift_hlist = shift @_;
  my $PRTL_props = shift @_;
  my $typing_regime = shift @_;
  my $actual_AA = shift @_;

  my @prob_list = ();
  my $total_prob = 0.0;

  # determine proper probability subroutine and res_shift_hlist components to use.
  my $option1;
  my $list1;
  my $option2;
  my $list2;
  my $optional_arg = 0;
  if ($typing_regime == 0) # perform 2/3
    { 
    $option1 = \&bayesianProbabilityByChiSquare; 
    $list1 = {};
    foreach my $shift_name (grep {$_ !~ /CX/; } (keys %$res_shift_hlist))
      { $$list1{$shift_name} = $$res_shift_hlist{$shift_name}; }
    $option2 = \&allBayesianProbCombinations; 
    $list2 = $list1; 
    }
  elsif ($typing_regime == 1) # perform 4/4stripped
    { 
    $option1 = \&allBayesianProbCombinationsCXrecomb;
    $list1 = $res_shift_hlist; 
    $option2 = \&allBayesianProbCombinationsCXrecomb;
    $list2 = {}; 
    my $extra_count = 100;
    foreach my $shift_name (keys %$res_shift_hlist)
      {
      if ($shift_name =~ /CX/)
	{ $$list2{$shift_name} = $$res_shift_hlist{$shift_name}; }
      else
	{ 
	my $new_shift_name = "CX" . $extra_count; $extra_count++;
	$$list2{$new_shift_name} = $$res_shift_hlist{$shift_name}; 
	}
      }

    $optional_arg = scalar(grep { $_ !~ /CX/; } (keys %$res_shift_hlist));
    }
  elsif ($typing_regime == 2) # perform 2/4CACB
    { 
    $option1 = \&bayesianProbabilityByChiSquare; 
    $list1 = $res_shift_hlist; 

    $option2 = \&allBayesianProbCombinationsCXrecomb;
    $list2 = {}; 
    my $extra_count = 100;
    foreach my $shift_name (keys %$res_shift_hlist)
      {
      next if (!$tocsy_typing && ($shift_name =~ /CX/)); 
      if (($shift_name =~ /CX/) || ($shift_name eq "CA") || ($shift_name eq "CB"))
	{ $$list2{$shift_name} = $$res_shift_hlist{$shift_name}; }
      else
	{ 
	my $new_shift_name = "CX" . $extra_count; $extra_count++;
	$$list2{$new_shift_name} = $$res_shift_hlist{$shift_name}; 
	}
      }
    }
  elsif ($typing_regime == 3) # perform 4/4CACB
    { 
    $option1 = \&allBayesianProbCombinationsCXrecomb;
    $list1 = $res_shift_hlist; 
    $option2 = \&allBayesianProbCombinationsCXrecomb;
    $list2 = {}; 
    my $extra_count = 100;
    foreach my $shift_name (keys %$res_shift_hlist)
      {
      if (($shift_name =~ /CX/) || ($shift_name eq "CA") || ($shift_name eq "CB"))
	{ $$list2{$shift_name} = $$res_shift_hlist{$shift_name}; }
      else
	{ 
	my $new_shift_name = "CX" . $extra_count; $extra_count++;
	$$list2{$new_shift_name} = $$res_shift_hlist{$shift_name}; 
	}
      }
    }
  elsif ($typing_regime == 4) # perform 3
    { 
    $option1 = \&allBayesianProbCombinations; 
    $list1 = {}; 
    foreach my $shift_name (grep {$_ !~ /CX/; } (keys %$res_shift_hlist))
      { $$list1{$shift_name} = $$res_shift_hlist{$shift_name}; }
    $option2 = \&allBayesianProbCombinations; 
    $list2 = $list1; 
    }
  elsif ($typing_regime == 5) # perform 4stripped
    { 
    $option1 = \&allBayesianProbCombinationsCXrecomb;
    $list1 = {}; 
    my $extra_count = 100;
    foreach my $shift_name (keys %$res_shift_hlist)
      {
      if ($shift_name =~ /CX/)
	{ $$list1{$shift_name} = $$res_shift_hlist{$shift_name}; }
      else
	{ 
	my $new_shift_name = "CX" . $extra_count; $extra_count++;
	$$list1{$new_shift_name} = $$res_shift_hlist{$shift_name}; 
	}
      }

    $option2 = $option1;
    $list2 = $list1;

    $optional_arg = scalar(grep { $_ !~ /CX/; } (keys %$res_shift_hlist));
    }
  elsif (($typing_regime == 6) || ($typing_regime == 7)) # perform 4CACB
    { 
    $option1 = \&allBayesianProbCombinationsCXrecomb;
    $list1 = {}; 
    my $extra_count = 100;
    foreach my $shift_name (keys %$res_shift_hlist)
      {
      next if (!$tocsy_typing && ($shift_name =~ /CX/)); 
      if (($shift_name =~ /CX/) || ($shift_name eq "CA") || ($shift_name eq "CB"))
	{ $$list1{$shift_name} = $$res_shift_hlist{$shift_name}; }
      else
	{ 
	my $new_shift_name = "CX" . $extra_count; $extra_count++;
	$$list1{$new_shift_name} = $$res_shift_hlist{$shift_name}; 
	}
      }

    $option2 = $option1;
    $list2 = $list1;
    }



  # creates an array of arrays where each row is the aminoacid type and the its probability
  foreach my $aa_type (@amino_acid_alist)
    { 
    my $prob_sub;
    my $used_res_shift_hlist;

    if ($aa_type eq $actual_AA)
      { 
      $prob_sub = $option1; 
      $used_res_shift_hlist = $list1;
      }
    else
      { 
      $prob_sub = $option2; 
      $used_res_shift_hlist = $list2;
      }

    my ($prob_value, $junk) = &$prob_sub($aa_type, $used_res_shift_hlist, $PRTL_props, 0, $optional_arg);
    push @prob_list, [ $aa_type, $prob_value ];
    $total_prob += $prob_list[$#prob_list][1]; 
    }


  # normalize each probablilty by the total
  if ($total_prob > 0)
    {
    foreach my $prob (@prob_list)
      { $$prob[1] = $$prob[1] / $total_prob; } 
    }

  # return the probabilites in descending order
  return (sort { $$b[1] <=> $$a[1] } @prob_list);
  }



# count_assignable 
#   Returns the number of assignable shifts that Bayesian4 methods can determine.
#
# Parameters:
#	$res_shift_hlist - hash of shift_name to ChemicalShift
#	$actual_AA - actual amino acid for the $res_shift_hlist
#
sub count_assignable
  {
  my $res_shift_hlist = shift @_;
  my $actual_AA = shift @_;

  my $results_res_shift_hlist = &allBayesianProbCombinationsCXrecomb($actual_AA, $res_shift_hlist, \%PRTL_props_tocsy,0);
  return scalar(keys %$results_res_shift_hlist);
  }


###############################################################################
# initialize_amino_acid_stats :: initializes amino acid statistics for typing #
###############################################################################
sub initialize_amino_acid_stats
  {
  my $use_aromatics = shift @_;
  my $use_sidechains = shift @_;
  my $deuteration = shift @_;


  my $count = {};
  my $mean = {};
  my $variance = {};
  my $min = {};
  my $max = {};
  my $ambiguity = {};
  my $invisible = {};

  $$min{A}{H} = 3.53;
  $$max{A}{H} = 11.48;
  $$mean{A}{H} = 8.20;
  $$count{A}{H} = 1;
  $$variance{A}{H} = 0.60 * 0.60;       

  $$min{A}{HA} = 0.87;
  $$max{A}{HA} = 6.51;
  $$mean{A}{HA} = 4.26;
  $$count{A}{HA} = 1;
  $$variance{A}{HA} = 0.44 * 0.44;       

  $$min{A}{HB} = -0.88;
  $$max{A}{HB} = 3.12;
  $$mean{A}{HB} = 1.35;
  $$count{A}{HB} = 1;
  $$variance{A}{HB} = 0.26 * 0.26;       

  $$min{A}{HB1} = -0.88;
  $$max{A}{HB1} = 3.12;
  $$mean{A}{HB1} = 1.35;
  $$count{A}{HB1} = 1;
  $$variance{A}{HB1} = 0.26 * 0.26;       
  $$invisible{A}{HB1} = 1;

  $$min{A}{HB2} = -0.88;
  $$max{A}{HB2} = 3.12;
  $$mean{A}{HB2} = 1.35;
  $$count{A}{HB2} = 1;
  $$variance{A}{HB2} = 0.26 * 0.26;       
  $$invisible{A}{HB2} = 1;

  $$min{A}{HB3} = -0.88;
  $$max{A}{HB3} = 3.12;
  $$mean{A}{HB3} = 1.35;
  $$count{A}{HB3} = 1;
  $$variance{A}{HB3} = 0.26 * 0.26;       
  $$invisible{A}{HB3} = 1;

  $$min{A}{C} = 164.48;
  $$max{A}{C} = 187.20;
  $$mean{A}{C} = 177.74;
  $$count{A}{C} = 1;
  $$variance{A}{C} = 2.13 * 2.13;       

  $$min{A}{CA} = 44.22;
  $$max{A}{CA} = 65.52;
  $$mean{A}{CA} = 53.14;
  $$count{A}{CA} = 1;
  $$variance{A}{CA} = 1.98 * 1.98;       

  $$min{A}{CB} = 0.00;
  $$max{A}{CB} = 38.70;
  $$mean{A}{CB} = 19.01;
  $$count{A}{CB} = 1;
  $$variance{A}{CB} = 1.83 * 1.83;       

  $$min{A}{N} = 77.10;
  $$max{A}{N} = 142.81;
  $$mean{A}{N} = 123.23;
  $$count{A}{N} = 1;
  $$variance{A}{N} = 3.54 * 3.54;       


  $$min{R}{H} = 3.57;
  $$max{R}{H} = 12.69;
  $$mean{R}{H} = 8.24;
  $$count{R}{H} = 1;
  $$variance{R}{H} = 0.61 * 0.61;       

  $$min{R}{HA} = 1.34;
  $$max{R}{HA} = 6.52;
  $$mean{R}{HA} = 4.30;
  $$count{R}{HA} = 1;
  $$variance{R}{HA} = 0.46 * 0.46;       

  $$min{R}{HB2} = -0.77;
  $$max{R}{HB2} = 3.44;
  $$mean{R}{HB2} = 1.79;
  $$count{R}{HB2} = 1;
  $$variance{R}{HB2} = 0.27 * 0.27;       

  $$min{R}{HB3} = -0.86;
  $$max{R}{HB3} = 3.32;
  $$mean{R}{HB3} = 1.76;
  $$count{R}{HB3} = 1;
  $$variance{R}{HB3} = 0.28 * 0.28;       

  $$min{R}{HG2} = -0.72;
  $$max{R}{HG2} = 3.51;
  $$mean{R}{HG2} = 1.57;
  $$count{R}{HG2} = 1;
  $$variance{R}{HG2} = 0.27 * 0.27;       

  $$min{R}{HG3} = -0.74;
  $$max{R}{HG3} = 3.51;
  $$mean{R}{HG3} = 1.54;
  $$count{R}{HG3} = 1;
  $$variance{R}{HG3} = 0.29 * 0.29;       

  $$min{R}{HD2} = 0.96;
  $$max{R}{HD2} = 4.69;
  $$mean{R}{HD2} = 3.12;
  $$count{R}{HD2} = 1;
  $$variance{R}{HD2} = 0.24 * 0.24;       

  $$min{R}{HD3} = 0.76;
  $$max{R}{HD3} = 4.56;
  $$mean{R}{HD3} = 3.10;
  $$count{R}{HD3} = 1;
  $$variance{R}{HD3} = 0.26 * 0.26;       

  $$min{R}{HE} = 2.99;
  $$max{R}{HE} = 11.88;
  $$mean{R}{HE} = 7.40;
  $$count{R}{HE} = 1;
  $$variance{R}{HE} = 0.63 * 0.63;       

  $$min{R}{HH11} = 5.88;
  $$max{R}{HH11} = 9.82;
  $$mean{R}{HH11} = 6.91;
  $$count{R}{HH11} = 1;
  $$variance{R}{HH11} = 0.46 * 0.46;       

  $$min{R}{HH12} = 5.99;
  $$max{R}{HH12} = 8.76;
  $$mean{R}{HH12} = 6.80;
  $$count{R}{HH12} = 1;
  $$variance{R}{HH12} = 0.33 * 0.33;       

  $$min{R}{HH21} = 5.90;
  $$max{R}{HH21} = 11.35;
  $$mean{R}{HH21} = 6.81;
  $$count{R}{HH21} = 1;
  $$variance{R}{HH21} = 0.48 * 0.48;       

  $$min{R}{HH22} = 5.97;
  $$max{R}{HH22} = 10.18;
  $$mean{R}{HH22} = 6.76;
  $$count{R}{HH22} = 1;
  $$variance{R}{HH22} = 0.36 * 0.36;       

  $$min{R}{C} = 167.44;
  $$max{R}{C} = 184.51;
  $$mean{R}{C} = 176.41;
  $$count{R}{C} = 1;
  $$variance{R}{C} = 2.03 * 2.03;       

  $$min{R}{CA} = 43.27;
  $$max{R}{CA} = 67.98;
  $$mean{R}{CA} = 56.77;
  $$count{R}{CA} = 1;
  $$variance{R}{CA} = 2.31 * 2.31;       

  $$min{R}{CB} = 20.95;
  $$max{R}{CB} = 42.50;
  $$mean{R}{CB} = 30.70;
  $$count{R}{CB} = 1;
  $$variance{R}{CB} = 1.83 * 1.83;       

  $$min{R}{CG} = 18.22;
  $$max{R}{CG} = 40.94;
  $$mean{R}{CG} = 27.21;
  $$count{R}{CG} = 1;
  $$variance{R}{CG} = 1.20 * 1.20;       

  $$min{R}{CD} = 35.05;
  $$max{R}{CD} = 50.88;
  $$mean{R}{CD} = 43.16;
  $$count{R}{CD} = 1;
  $$variance{R}{CD} = 0.88 * 0.88;       

  $$min{R}{CZ} = 156.20;
  $$max{R}{CZ} = 177.70;
  $$mean{R}{CZ} = 159.97;
  $$count{R}{CZ} = 1;
  $$variance{R}{CZ} = 2.95 * 2.95;       

  $$min{R}{N} = 102.78;
  $$max{R}{N} = 137.60;
  $$mean{R}{N} = 120.80;
  $$count{R}{N} = 1;
  $$variance{R}{N} = 3.68 * 3.68;       

  $$min{R}{NE} = 67.00;
  $$max{R}{NE} = 99.81;
  $$mean{R}{NE} = 84.63;
  $$count{R}{NE} = 1;
  $$variance{R}{NE} = 1.68 * 1.68;       

  $$min{R}{NH1} = 67.60;
  $$max{R}{NH1} = 87.07;
  $$mean{R}{NH1} = 73.82;
  $$count{R}{NH1} = 1;
  $$variance{R}{NH1} = 4.62 * 4.62;       

  $$min{R}{NH2} = 70.10;
  $$max{R}{NH2} = 85.28;
  $$mean{R}{NH2} = 73.26;
  $$count{R}{NH2} = 1;
  $$variance{R}{NH2} = 3.32 * 3.32;       


  $$min{D}{H} = 3.56;
  $$max{D}{H} = 12.68;
  $$mean{D}{H} = 8.31;
  $$count{D}{H} = 1;
  $$variance{D}{H} = 0.58 * 0.58;       

  $$min{D}{HA} = 2.33;
  $$max{D}{HA} = 6.33;
  $$mean{D}{HA} = 4.59;
  $$count{D}{HA} = 1;
  $$variance{D}{HA} = 0.32 * 0.32;       

  $$min{D}{HB2} = -0.39;
  $$max{D}{HB2} = 4.58;
  $$mean{D}{HB2} = 2.72;
  $$count{D}{HB2} = 1;
  $$variance{D}{HB2} = 0.26 * 0.26;       

  $$min{D}{HB3} = -0.23;
  $$max{D}{HB3} = 4.58;
  $$mean{D}{HB3} = 2.66;
  $$count{D}{HB3} = 1;
  $$variance{D}{HB3} = 0.28 * 0.28;       

  $$min{D}{HD2} = 4.65;
  $$max{D}{HD2} = 6.03;
  $$mean{D}{HD2} = 5.25;
  $$count{D}{HD2} = 1;
  $$variance{D}{HD2} = 0.58 * 0.58;       

  $$min{D}{C} = 166.80;
  $$max{D}{C} = 182.70;
  $$mean{D}{C} = 176.40;
  $$count{D}{C} = 1;
  $$variance{D}{C} = 1.75 * 1.75;       

  $$min{D}{CA} = 41.88;
  $$max{D}{CA} = 67.17;
  $$mean{D}{CA} = 54.69;
  $$count{D}{CA} = 1;
  $$variance{D}{CA} = 2.03 * 2.03;       

  $$min{D}{CB} = 27.48;
  $$max{D}{CB} = 51.09;
  $$mean{D}{CB} = 40.88;
  $$count{D}{CB} = 1;
  $$variance{D}{CB} = 1.62 * 1.62;       

  $$min{D}{CG} = 170.72;
  $$max{D}{CG} = 186.50;
  $$mean{D}{CG} = 179.17;
  $$count{D}{CG} = 1;
  $$variance{D}{CG} = 1.79 * 1.79;       

  $$min{D}{N} = 101.90;
  $$max{D}{N} = 143.52;
  $$mean{D}{N} = 120.65;
  $$count{D}{N} = 1;
  $$variance{D}{N} = 3.86 * 3.86;       

  $$min{D}{OD1} = 177.59;
  $$max{D}{OD1} = 180.97;
  $$mean{D}{OD1} = 179.66;
  $$count{D}{OD1} = 1;
  $$variance{D}{OD1} = 0.91 * 0.91;       


  $$min{N}{H} = 2.61;
  $$max{N}{H} = 12.40;
  $$mean{N}{H} = 8.34;
  $$count{N}{H} = 1;
  $$variance{N}{H} = 0.63 * 0.63;       

  $$min{N}{HA} = 2.46;
  $$max{N}{HA} = 6.43;
  $$mean{N}{HA} = 4.67;
  $$count{N}{HA} = 1;
  $$variance{N}{HA} = 0.36 * 0.36;       

  $$min{N}{HB2} = 0.23;
  $$max{N}{HB2} = 4.47;
  $$mean{N}{HB2} = 2.81;
  $$count{N}{HB2} = 1;
  $$variance{N}{HB2} = 0.31 * 0.31;       

  $$min{N}{HB3} = -0.04;
  $$max{N}{HB3} = 4.47;
  $$mean{N}{HB3} = 2.75;
  $$count{N}{HB3} = 1;
  $$variance{N}{HB3} = 0.33 * 0.33;       

  $$min{N}{HD21} = 3.55;
  $$max{N}{HD21} = 10.38;
  $$mean{N}{HD21} = 7.35;
  $$count{N}{HD21} = 1;
  $$variance{N}{HD21} = 0.48 * 0.48;       

  $$min{N}{HD22} = 3.05;
  $$max{N}{HD22} = 10.80;
  $$mean{N}{HD22} = 7.14;
  $$count{N}{HD22} = 1;
  $$variance{N}{HD22} = 0.49 * 0.49;       

  $$min{N}{C} = 167.04;
  $$max{N}{C} = 181.90;
  $$mean{N}{C} = 175.27;
  $$count{N}{C} = 1;
  $$variance{N}{C} = 1.79 * 1.79;       

  $$min{N}{CA} = 41.31;
  $$max{N}{CA} = 61.80;
  $$mean{N}{CA} = 53.54;
  $$count{N}{CA} = 1;
  $$variance{N}{CA} = 1.88 * 1.88;       

  $$min{N}{CB} = 26.45;
  $$max{N}{CB} = 55.09;
  $$mean{N}{CB} = 38.69;
  $$count{N}{CB} = 1;
  $$variance{N}{CB} = 1.69 * 1.69;       

  $$min{N}{CG} = 166.40;
  $$max{N}{CG} = 183.10;
  $$mean{N}{CG} = 176.76;
  $$count{N}{CG} = 1;
  $$variance{N}{CG} = 1.38 * 1.38;       

  $$min{N}{N} = 101.71;
  $$max{N}{N} = 137.49;
  $$mean{N}{N} = 118.93;
  $$count{N}{N} = 1;
  $$variance{N}{N} = 4.03 * 4.03;       

  $$min{N}{ND2} = 99.40;
  $$max{N}{ND2} = 133.86;
  $$mean{N}{ND2} = 112.75;
  $$count{N}{ND2} = 1;
  $$variance{N}{ND2} = 2.23 * 2.23;       


  $$min{C}{H} = 4.73;
  $$max{C}{H} = 12.12;
  $$mean{C}{H} = 8.39;
  $$count{C}{H} = 1;
  $$variance{C}{H} = 0.67 * 0.67;       

  $$min{C}{HA} = 1.64;
  $$max{C}{HA} = 6.43;
  $$mean{C}{HA} = 4.66;
  $$count{C}{HA} = 1;
  $$variance{C}{HA} = 0.55 * 0.55;       

  $$min{C}{HB2} = -0.54;
  $$max{C}{HB2} = 4.72;
  $$mean{C}{HB2} = 2.96;
  $$count{C}{HB2} = 1;
  $$variance{C}{HB2} = 0.44 * 0.44;       

  $$min{C}{HB3} = -0.83;
  $$max{C}{HB3} = 4.69;
  $$mean{C}{HB3} = 2.89;
  $$count{C}{HB3} = 1;
  $$variance{C}{HB3} = 0.46 * 0.46;       

  $$min{C}{HG} = 0.25;
  $$max{C}{HG} = 7.39;
  $$mean{C}{HG} = 1.98;
  $$count{C}{HG} = 1;
  $$variance{C}{HG} = 1.38 * 1.38;       

  $$min{C}{C} = 166.73;
  $$max{C}{C} = 182.73;
  $$mean{C}{C} = 174.95;
  $$count{C}{C} = 1;
  $$variance{C}{C} = 2.07 * 2.07;       

  $$min{C}{CA} = 42.45;
  $$max{C}{CA} = 67.64;
  $$mean{C}{CA} = 58.30;
  $$count{C}{CA} = 1;
  $$variance{C}{CA} = 3.33 * 3.33;       

  $$min{C}{CB} = 17.99;
  $$max{C}{CB} = 62.07;
  $$mean{C}{CB} = 32.49;
  $$count{C}{CB} = 1;
  $$variance{C}{CB} = 6.01 * 6.01;       

  $$min{C}{N} = 100.48;
  $$max{C}{N} = 175.10;
  $$mean{C}{N} = 120.17;
  $$count{C}{N} = 1;
  $$variance{C}{N} = 4.64 * 4.64;       


  $$min{E}{H} = 4.20;
  $$max{E}{H} = 12.17;
  $$mean{E}{H} = 8.33;
  $$count{E}{H} = 1;
  $$variance{E}{H} = 0.59 * 0.59;       

  $$min{E}{HA} = 1.39;
  $$max{E}{HA} = 6.29;
  $$mean{E}{HA} = 4.25;
  $$count{E}{HA} = 1;
  $$variance{E}{HA} = 0.41 * 0.41;       

  $$min{E}{HB2} = 0.34;
  $$max{E}{HB2} = 3.44;
  $$mean{E}{HB2} = 2.02;
  $$count{E}{HB2} = 1;
  $$variance{E}{HB2} = 0.21 * 0.21;       

  $$min{E}{HB3} = -0.49;
  $$max{E}{HB3} = 3.44;
  $$mean{E}{HB3} = 1.99;
  $$count{E}{HB3} = 1;
  $$variance{E}{HB3} = 0.23 * 0.23;       

  $$min{E}{HG2} = 0.53;
  $$max{E}{HG2} = 3.77;
  $$mean{E}{HG2} = 2.27;
  $$count{E}{HG2} = 1;
  $$variance{E}{HG2} = 0.21 * 0.21;       

  $$min{E}{HG3} = 0.56;
  $$max{E}{HG3} = 3.80;
  $$mean{E}{HG3} = 2.25;
  $$count{E}{HG3} = 1;
  $$variance{E}{HG3} = 0.22 * 0.22;       

  $$min{E}{C} = 166.80;
  $$max{E}{C} = 182.99;
  $$mean{E}{C} = 176.87;
  $$count{E}{C} = 1;
  $$variance{E}{C} = 1.95 * 1.95;       

  $$min{E}{CA} = 44.35;
  $$max{E}{CA} = 64.60;
  $$mean{E}{CA} = 57.32;
  $$count{E}{CA} = 1;
  $$variance{E}{CA} = 2.09 * 2.09;       

  $$min{E}{CB} = 18.71;
  $$max{E}{CB} = 43.70;
  $$mean{E}{CB} = 30.01;
  $$count{E}{CB} = 1;
  $$variance{E}{CB} = 1.72 * 1.72;       

  $$min{E}{CG} = 25.31;
  $$max{E}{CG} = 44.34;
  $$mean{E}{CG} = 36.11;
  $$count{E}{CG} = 1;
  $$variance{E}{CG} = 1.19 * 1.19;       

  $$min{E}{CD} = 173.41;
  $$max{E}{CD} = 188.01;
  $$mean{E}{CD} = 182.40;
  $$count{E}{CD} = 1;
  $$variance{E}{CD} = 1.78 * 1.78;       

  $$min{E}{N} = 104.54;
  $$max{E}{N} = 138.60;
  $$mean{E}{N} = 120.67;
  $$count{E}{N} = 1;
  $$variance{E}{N} = 3.48 * 3.48;       



  $$min{Q}{H} = 3.51;
  $$max{Q}{H} = 12.04;
  $$mean{Q}{H} = 8.22;
  $$count{Q}{H} = 1;
  $$variance{Q}{H} = 0.59 * 0.59;       

  $$min{Q}{HA} = 1.57;
  $$max{Q}{HA} = 6.34;
  $$mean{Q}{HA} = 4.27;
  $$count{Q}{HA} = 1;
  $$variance{Q}{HA} = 0.44 * 0.44;       

  $$min{Q}{HB2} = -0.11;
  $$max{Q}{HB2} = 4.00;
  $$mean{Q}{HB2} =2.05;
  $$count{Q}{HB2} = 1;
  $$variance{Q}{HB2} = 0.25 * 0.25;       

  $$min{Q}{HB3} = -0.58;
  $$max{Q}{HB3} = 4.04;
  $$mean{Q}{HB3} = 2.02;
  $$count{Q}{HB3} = 1;
  $$variance{Q}{HB3} = 0.28 * 0.28;       

  $$min{Q}{HG2} = 0.09;
  $$max{Q}{HG2} = 3.66;
  $$mean{Q}{HG2} = 2.32;
  $$count{Q}{HG2} = 1;
  $$variance{Q}{HG2} = 0.27 * 0.27;       

  $$min{Q}{HG3} = -0.55;
  $$max{Q}{HG3} = 3.66;
  $$mean{Q}{HG3} = 2.29;
  $$count{Q}{HG3} = 1;
  $$variance{Q}{HG3} = 0.29 * 0.29;       

  $$min{Q}{HE21} = 3.39;
  $$max{Q}{HE21} = 11.11;
  $$mean{Q}{HE21} = 7.24;
  $$count{Q}{HE21} = 1;
  $$variance{Q}{HE21} = 0.45 * 0.45;       

  $$min{Q}{HE22} = 3.59;
  $$max{Q}{HE22} = 9.79;
  $$mean{Q}{HE22} = 7.02;
  $$count{Q}{HE22} = 1;
  $$variance{Q}{HE22} = 0.44 * 0.44;       

  $$min{Q}{C} = 168.09;
  $$max{Q}{C} = 182.22;
  $$mean{Q}{C} = 176.31;
  $$count{Q}{C} = 1;
  $$variance{Q}{C} = 1.95 * 1.95;       

  $$min{Q}{CA} = 47.87;
  $$max{Q}{CA} = 66.60;
  $$mean{Q}{CA} = 56.57;
  $$count{Q}{CA} = 1;
  $$variance{Q}{CA} = 2.14 * 2.14;       

  $$min{Q}{CB} = 20.27;
  $$max{Q}{CB} = 42.20;
  $$mean{Q}{CB} = 29.19;
  $$count{Q}{CB} = 1;
  $$variance{Q}{CB} = 1.82 * 1.82;       

  $$min{Q}{CG} = 21.64;
  $$max{Q}{CG} = 42.80;
  $$mean{Q}{CG} = 33.76;
  $$count{Q}{CG} = 1;
  $$variance{Q}{CG} = 1.11 * 1.11;       

  $$min{Q}{CD} = 171.37;
  $$max{Q}{CD} = 183.50;
  $$mean{Q}{CD} = 179.69;
  $$count{Q}{CD} = 1;
  $$variance{Q}{CD} = 1.29 * 1.29;       

  $$min{Q}{N} = 104.10;
  $$max{Q}{N} = 139.55;
  $$mean{Q}{N} = 119.89;
  $$count{Q}{N} = 1;
  $$variance{Q}{N} = 3.60 * 3.60;       

  $$min{Q}{NE2} = 97.90;
  $$max{Q}{NE2} = 124.30;
  $$mean{Q}{NE2} = 111.87;
  $$count{Q}{NE2} = 1;
  $$variance{Q}{NE2} = 1.72 * 1.72;       


  $$min{G}{H} = 3.01;
  $$max{G}{H} = 12.22;
  $$mean{G}{H} = 8.33;
  $$count{G}{H} = 1;
  $$variance{G}{H} = 0.65 * 0.65;       

  $$min{G}{HA2} = 0.84;
  $$max{G}{HA2} = 6.43;
  $$mean{G}{HA2} = 3.97;
  $$count{G}{HA2} = 1;
  $$variance{G}{HA2} = 0.37 * 0.37;       

  $$min{G}{HA3} = 1.01;
  $$max{G}{HA3} = 6.39;
  $$mean{G}{HA3} = 3.90;
  $$count{G}{HA3} = 1;
  $$variance{G}{HA3} = 0.37 * 0.37;       

  $$min{G}{C} = 163.27;
  $$max{G}{C} = 184.32;
  $$mean{G}{C} = 173.87;
  $$count{G}{C} = 1;
  $$variance{G}{C} = 1.88 * 1.88;       

  $$min{G}{CA} = 35.78;
  $$max{G}{CA} = 58.67;
  $$mean{G}{CA} = 45.35;
  $$count{G}{CA} = 1;
  $$variance{G}{CA} = 1.34 * 1.34;       

  $$min{G}{N} = 42.65;
  $$max{G}{N} = 162.19;
  $$mean{G}{N} = 109.67;
  $$count{G}{N} = 1;
  $$variance{G}{N} = 3.87 * 3.87;       


  $$min{H}{H} = 5.12;
  $$max{H}{H} = 12.39;
  $$mean{H}{H} = 8.24;
  $$count{H}{H} = 1;
  $$variance{H}{H} = 0.68 * 0.68;       

  $$min{H}{HA} = 1.93;
  $$max{H}{HA} = 8.90;
  $$mean{H}{HA} = 4.61;
  $$count{H}{HA} = 1;
  $$variance{H}{HA} = 0.43 * 0.43;       

  $$min{H}{HB2} = 0.17;
  $$max{H}{HB2} = 8.70;
  $$mean{H}{HB2} = 3.10;
  $$count{H}{HB2} = 1;
  $$variance{H}{HB2} = 0.36 * 0.36;       

  $$min{H}{HB3} = 0.06;
  $$max{H}{HB3} = 8.70;
  $$mean{H}{HB3} = 3.04;
  $$count{H}{HB3} = 1;
  $$variance{H}{HB3} = 0.38 * 0.38;       

  $$min{H}{HD1} = 3.79;
  $$max{H}{HD1} = 17.20;
  $$mean{H}{HD1} = 8.68;
  $$count{H}{HD1} = 1;
  $$variance{H}{HD1} = 2.62 * 2.62;       

  $$min{H}{HD2} = 3.46;
  $$max{H}{HD2} = 9.01;
  $$mean{H}{HD2} = 7.00;
  $$count{H}{HD2} = 1;
  $$variance{H}{HD2} = 0.43 * 0.43;       

  $$min{H}{HE1} = 3.21;
  $$max{H}{HE1} = 10.88;
  $$mean{H}{HE1} = 7.95;
  $$count{H}{HE1} = 1;
  $$variance{H}{HE1} = 0.48 * 0.48;       

  $$min{H}{HE2} = 6.57;
  $$max{H}{HE2} = 16.53;
  $$mean{H}{HE2} = 9.64;
  $$count{H}{HE2} = 1;
  $$variance{H}{HE2} = 2.60 * 2.60;       

  $$min{H}{C} = 166.90;
  $$max{H}{C} = 182.80;
  $$mean{H}{C} = 175.25;
  $$count{H}{C} = 1;
  $$variance{H}{C} = 1.97 * 1.97;       

  $$min{H}{CA} = 46.01;
  $$max{H}{CA} = 66.98;
  $$mean{H}{CA} = 56.52;
  $$count{H}{CA} = 1;
  $$variance{H}{CA} = 2.31 * 2.31;       

  $$min{H}{CB} = 18.75;
  $$max{H}{CB} = 43.30;
  $$mean{H}{CB} = 30.24;
  $$count{H}{CB} = 1;
  $$variance{H}{CB} = 2.07 * 2.07;       

  $$min{H}{CG} = 122.67;
  $$max{H}{CG} = 137.19;
  $$mean{H}{CG} = 131.52;
  $$count{H}{CG} = 1;
  $$variance{H}{CG} = 3.27 * 3.27;       

  $$min{H}{CD2} = 112.07;
  $$max{H}{CD2} = 159.95;
  $$mean{H}{CD2} = 120.49;
  $$count{H}{CD2} = 1;
  $$variance{H}{CD2} = 3.42 * 3.42;       

  $$min{H}{CE1} = 104.67;
  $$max{H}{CE1} = 144.54;
  $$mean{H}{CE1} = 137.71;
  $$count{H}{CE1} = 1;
  $$variance{H}{CE1} = 2.12 * 2.12;       

  $$min{H}{N} = 105.00;
  $$max{H}{N} = 136.48;
  $$mean{H}{N} = 119.69;
  $$count{H}{N} = 1;
  $$variance{H}{N} = 4.00 * 4.00;       

  $$min{H}{ND1} = 162.04;
  $$max{H}{ND1} = 229.14;
  $$mean{H}{ND1} = 195.02;
  $$count{H}{ND1} = 1;
  $$variance{H}{ND1} = 18.51 * 18.51;       

  $$min{H}{NE2} = 161.70;
  $$max{H}{NE2} = 226.29;
  $$mean{H}{NE2} = 182.41;
  $$count{H}{NE2} = 1;
  $$variance{H}{NE2} = 14.40 * 14.40;       


  $$min{I}{H} = 3.43;
  $$max{I}{H} = 11.69;
  $$mean{I}{H} = 8.28;
  $$count{I}{H} = 1;
  $$variance{I}{H} = 0.68 * 0.68;       

  $$min{I}{HA} = 1.32;
  $$max{I}{HA} = 6.36;
  $$mean{I}{HA} = 4.18;
  $$count{I}{HA} = 1;
  $$variance{I}{HA} = 0.56 * 0.56;       

  $$min{I}{HB} = -1.28;
  $$max{I}{HB} = 3.87;
  $$mean{I}{HB} = 1.78;
  $$count{I}{HB} = 1;
  $$variance{I}{HB} = 0.29 * 0.29;       

  $$min{I}{HG12} = -2.38;
  $$max{I}{HG12} = 2.69;
  $$mean{I}{HG12} = 1.28;
  $$count{I}{HG12} = 1;
  $$variance{I}{HG12} = 0.40 * 0.40;       

  $$min{I}{HG13} = -2.04;
  $$max{I}{HG13} = 2.99;
  $$mean{I}{HG13} = 1.19;
  $$count{I}{HG13} = 1;
  $$variance{I}{HG13} = 0.41 * 0.41;       

  $$min{I}{HG2} = -1.33;
  $$max{I}{HG2} = 2.20;
  $$mean{I}{HG2} = 0.77;
  $$count{I}{HG2} = 1;
  $$variance{I}{HG2} = 0.27 * 0.27;       

  $$min{I}{HG21} = -1.33;
  $$max{I}{HG21} = 2.20;
  $$mean{I}{HG21} = 0.77;
  $$count{I}{HG21} = 1;
  $$variance{I}{HG21} = 0.27 * 0.27;       
  $$invisible{I}{HG21} = 1;

  $$min{I}{HG22} = -1.33;
  $$max{I}{HG22} = 2.20;
  $$mean{I}{HG22} = 0.77;
  $$count{I}{HG22} = 1;
  $$variance{I}{HG22} = 0.27 * 0.27;       
  $$invisible{I}{HG22} = 1;

  $$min{I}{HG23} = -1.33;
  $$max{I}{HG23} = 2.20;
  $$mean{I}{HG23} = 0.77;
  $$count{I}{HG23} = 1;
  $$variance{I}{HG23} = 0.27 * 0.27;       
  $$invisible{I}{HG23} = 1;

  $$min{I}{HD1} = -1.08;
  $$max{I}{HD1} = 2.82;
  $$mean{I}{HD1} = 0.68;
  $$count{I}{HD1} = 1;
  $$variance{I}{HD1} = 0.29 * 0.29;       

  $$min{I}{HD11} = -1.08;
  $$max{I}{HD11} = 2.82;
  $$mean{I}{HD11} = 0.68;
  $$count{I}{HD11} = 1;
  $$variance{I}{HD11} = 0.29 * 0.29;       
  $$invisible{I}{HD11} = 1;

  $$min{I}{HD12} = -1.08;
  $$max{I}{HD12} = 2.82;
  $$mean{I}{HD12} = 0.68;
  $$count{I}{HD12} = 1;
  $$variance{I}{HD12} = 0.29 * 0.29;       
  $$invisible{I}{HD12} = 1;

  $$min{I}{HD13} = -1.08;
  $$max{I}{HD13} = 2.82;
  $$mean{I}{HD13} = 0.68;
  $$count{I}{HD13} = 1;
  $$variance{I}{HD13} = 0.29 * 0.29;       
  $$invisible{I}{HD13} = 1;

  $$min{I}{C} = 167.00;
  $$max{I}{C} = 183.40;
  $$mean{I}{C} = 175.85;
  $$count{I}{C} = 1;
  $$variance{I}{C} = 1.92 * 1.92;       

  $$min{I}{CA} = 51.15;
  $$max{I}{CA} = 71.86;
  $$mean{I}{CA} = 61.61;
  $$count{I}{CA} = 1;
  $$variance{I}{CA} = 2.68 * 2.68;       

  $$min{I}{CB} = 20.94;
  $$max{I}{CB} = 51.88;
  $$mean{I}{CB} = 38.63;
  $$count{I}{CB} = 1;
  $$variance{I}{CB} = 2.02 * 2.02;       

  $$min{I}{CG1} = 12.90;
  $$max{I}{CG1} = 39.05;
  $$mean{I}{CG1} = 27.71;
  $$count{I}{CG1} = 1;
  $$variance{I}{CG1} = 1.68 * 1.68;       

  $$min{I}{CG2} = 3.45;
  $$max{I}{CG2} = 29.80;
  $$mean{I}{CG2} = 17.53;
  $$count{I}{CG2} = 1;
  $$variance{I}{CG2} = 1.36 * 1.36;       

  $$min{I}{CD1} = 2.70;
  $$max{I}{CD1} = 29.60;
  $$mean{I}{CD1} = 13.43;
  $$count{I}{CD1} = 1;
  $$variance{I}{CD1} = 1.67 * 1.67;       

  $$min{I}{N} = 99.00;
  $$max{I}{N} = 138.12;
  $$mean{I}{N} = 121.46;
  $$count{I}{N} = 1;
  $$variance{I}{N} = 4.28 * 4.28;       


  $$min{L}{H} = 4.08;
  $$max{L}{H} = 13.22;
  $$mean{L}{H} = 8.23;
  $$count{L}{H} = 1;
  $$variance{L}{H} = 0.65 * 0.65;       

  $$min{L}{HA} = 1.93;
  $$max{L}{HA} = 6.24;
  $$mean{L}{HA} = 4.32;
  $$count{L}{HA} = 1;
  $$variance{L}{HA} = 0.47 * 0.47;       

  $$min{L}{HB2} = -1.25;
  $$max{L}{HB2} = 3.18;
  $$mean{L}{HB2} = 1.61;
  $$count{L}{HB2} = 1;
  $$variance{L}{HB2} = 0.34 * 0.34;       

  $$min{L}{HB3} = -1.47;
  $$max{L}{HB3} = 3.18;
  $$mean{L}{HB3} = 1.52;
  $$count{L}{HB3} = 1;
  $$variance{L}{HB3} = 0.36 * 0.36;       

  $$min{L}{HG} = -1.06;
  $$max{L}{HG} = 3.90;
  $$mean{L}{HG} = 1.51;
  $$count{L}{HG} = 1;
  $$variance{L}{HG} = 0.33 * 0.33;       

  $$min{L}{HD1} = -1.73;
  $$max{L}{HD1} = 2.36;
  $$mean{L}{HD1} = 0.75;
  $$count{L}{HD1} = 1;
  $$variance{L}{HD1} = 0.28 * 0.28;       

  $$min{L}{HD11} = -1.73;
  $$max{L}{HD11} = 2.36;
  $$mean{L}{HD11} = 0.75;
  $$count{L}{HD11} = 1;
  $$variance{L}{HD11} = 0.28 * 0.28;       
  $$invisible{L}{HD11} = 1;

  $$min{L}{HD12} = -1.73;
  $$max{L}{HD12} = 2.36;
  $$mean{L}{HD12} = 0.75;
  $$count{L}{HD12} = 1;
  $$variance{L}{HD12} = 0.28 * 0.28;       
  $$invisible{L}{HD12} = 1;

  $$min{L}{HD13} = -1.73;
  $$max{L}{HD13} = 2.36;
  $$mean{L}{HD13} = 0.75;
  $$count{L}{HD13} = 1;
  $$variance{L}{HD13} = 0.28 * 0.28;       
  $$invisible{L}{HD13} = 1;

  $$min{L}{HD2} = -1.65;
  $$max{L}{HD2} = 2.78;
  $$mean{L}{HD2} = 0.73;
  $$count{L}{HD2} = 1;
  $$variance{L}{HD2} = 0.29 * 0.29;       

  $$min{L}{HD21} = -1.65;
  $$max{L}{HD21} = 2.78;
  $$mean{L}{HD21} = 0.73;
  $$count{L}{HD21} = 1;
  $$variance{L}{HD21} = 0.29 * 0.29;       
  $$invisible{L}{HD21} = 1;

  $$min{L}{HD22} = -1.65;
  $$max{L}{HD22} = 2.78;
  $$mean{L}{HD22} = 0.73;
  $$count{L}{HD22} = 1;
  $$variance{L}{HD22} = 0.29 * 0.29;       
  $$invisible{L}{HD22} = 1;

  $$min{L}{HD23} = -1.65;
  $$max{L}{HD23} = 2.78;
  $$mean{L}{HD23} = 0.73;
  $$count{L}{HD23} = 1;
  $$variance{L}{HD23} = 0.29 * 0.29;       
  $$invisible{L}{HD23} = 1;

  $$min{L}{C} = 167.49;
  $$max{L}{C} = 189.78;
  $$mean{L}{C} = 176.99;
  $$count{L}{C} = 1;
  $$variance{L}{C} = 1.98 * 1.98;       

  $$min{L}{CA} = 46.36;
  $$max{L}{CA} = 65.83;
  $$mean{L}{CA} = 55.62;
  $$count{L}{CA} = 1;
  $$variance{L}{CA} = 2.13 * 2.13;       

  $$min{L}{CB} = 26.40;
  $$max{L}{CB} = 53.70;
  $$mean{L}{CB} = 42.31;
  $$count{L}{CB} = 1;
  $$variance{L}{CB} = 1.88 * 1.88;       

  $$min{L}{CG} = 15.57;
  $$max{L}{CG} = 37.70;
  $$mean{L}{CG} = 26.78;
  $$count{L}{CG} = 1;
  $$variance{L}{CG} = 1.10 * 1.10;       

  $$min{L}{CD1} = 10.95;
  $$max{L}{CD1} = 31.83;
  $$mean{L}{CD1} = 24.72;
  $$count{L}{CD1} = 1;
  $$variance{L}{CD1} = 1.59 * 1.59;       

  $$min{L}{CD2} = 11.71;
  $$max{L}{CD2} = 30.40;
  $$mean{L}{CD2} = 24.05;
  $$count{L}{CD2} = 1;
  $$variance{L}{CD2} = 1.70 * 1.70;       

  $$min{L}{N} = 98.56;
  $$max{L}{N} = 144.55;
  $$mean{L}{N} = 121.86;
  $$count{L}{N} = 1;
  $$variance{L}{N} = 3.90 * 3.90;       


  $$min{K}{H} = 4.11;
  $$max{K}{H} = 12.03;
  $$mean{K}{H} = 8.19;
  $$count{K}{H} = 1;
  $$variance{K}{H} = 0.60 * 0.60;       

  $$min{K}{HA} = 1.30;
  $$max{K}{HA} = 6.54;
  $$mean{K}{HA} = 4.27;
  $$count{K}{HA} = 1;
  $$variance{K}{HA} = 0.44 * 0.44;       

  $$min{K}{HB2} = -0.75;
  $$max{K}{HB2} = 4.05;
  $$mean{K}{HB2} = 1.78;
  $$count{K}{HB2} = 1;
  $$variance{K}{HB2} = 0.25 * 0.25;       

  $$min{K}{HB3} = -0.97;
  $$max{K}{HB3} = 3.95;
  $$mean{K}{HB3} = 1.74;
  $$count{K}{HB3} = 1;
  $$variance{K}{HB3} = 0.27 * 0.27;       

  $$min{K}{HG2} = -1.16;
  $$max{K}{HG2} = 3.13;
  $$mean{K}{HG2} = 1.37;
  $$count{K}{HG2} = 1;
  $$variance{K}{HG2} = 0.26 * 0.26;       

  $$min{K}{HG3} = -1.16;
  $$max{K}{HG3} = 3.03;
  $$mean{K}{HG3} = 1.35;
  $$count{K}{HG3} = 1;
  $$variance{K}{HG3} = 0.28 * 0.28;       

  $$min{K}{HD2} = -0.67;
  $$max{K}{HD2} = 7.71;
  $$mean{K}{HD2} = 1.61;
  $$count{K}{HD2} = 1;
  $$variance{K}{HD2} = 0.22 * 0.22;       

  $$min{K}{HD3} = -1.02;
  $$max{K}{HD3} = 3.61;
  $$mean{K}{HD3} = 1.60;
  $$count{K}{HD3} = 1;
  $$variance{K}{HD3} = 0.22 * 0.22;       

  $$min{K}{HE2} = 1.25;
  $$max{K}{HE2} = 4.36;
  $$mean{K}{HE2} = 2.92;
  $$count{K}{HE2} = 1;
  $$variance{K}{HE2} = 0.19 * 0.19;       

  $$min{K}{HE3} = 1.22;
  $$max{K}{HE3} = 4.55;
  $$mean{K}{HE3} = 2.91;
  $$count{K}{HE3} = 1;
  $$variance{K}{HE3} = 0.20 * 0.20;       

  $$min{K}{HZ} = 1.95;
  $$max{K}{HZ} = 9.90;
  $$mean{K}{HZ} = 7.42;
  $$count{K}{HZ} = 1;
  $$variance{K}{HZ} = 0.67 * 0.67;       

  $$min{K}{C} = 121.16;
  $$max{K}{C} = 185.00;
  $$mean{K}{C} = 176.64;
  $$count{K}{C} = 1;
  $$variance{K}{C} = 2.00 * 2.00;       

  $$min{K}{CA} = 40.73;
  $$max{K}{CA} = 64.57;
  $$mean{K}{CA} = 56.95;
  $$count{K}{CA} = 1;
  $$variance{K}{CA} = 2.20 * 2.20;       

  $$min{K}{CB} = 21.19;
  $$max{K}{CB} = 46.60;
  $$mean{K}{CB} = 32.79;
  $$count{K}{CB} = 1;
  $$variance{K}{CB} = 1.78 * 1.78;       

  $$min{K}{CG} = 12.11;
  $$max{K}{CG} = 36.22;
  $$mean{K}{CG} = 24.89;
  $$count{K}{CG} = 1;
  $$variance{K}{CG} = 1.13 * 1.13;       

  $$min{K}{CD} = 21.24;
  $$max{K}{CD} = 40.10;
  $$mean{K}{CD} = 28.96;
  $$count{K}{CD} = 1;
  $$variance{K}{CD} = 1.08 * 1.08;       

  $$min{K}{CE} = 30.70;
  $$max{K}{CE} = 52.20;
  $$mean{K}{CE} = 41.89;
  $$count{K}{CE} = 1;
  $$variance{K}{CE} = 0.82 * 0.82;       

  $$min{K}{N} = 101.10;
  $$max{K}{N} = 140.30;
  $$mean{K}{N} = 121.05;
  $$count{K}{N} = 1;
  $$variance{K}{N} = 3.77 * 3.77;       

  $$min{K}{NZ} = 29.48;
  $$max{K}{NZ} = 43.69;
  $$mean{K}{NZ} = 33.81;
  $$count{K}{NZ} = 1;
  $$variance{K}{NZ} = 2.81 * 2.81;       


  $$min{M}{H} = 4.87;
  $$max{M}{H} = 12.46;
  $$mean{M}{H} = 8.26;
  $$count{M}{H} = 1;
  $$variance{M}{H} = 0.60 * 0.60;       

  $$min{M}{HA} = 1.13;
  $$max{M}{HA} = 6.35;
  $$mean{M}{HA} = 4.41;
  $$count{M}{HA} = 1;
  $$variance{M}{HA} = 0.48 * 0.48;       

  $$min{M}{HB2} = -1.05;
  $$max{M}{HB2} = 3.87;
  $$mean{M}{HB2} = 2.03;
  $$count{M}{HB2} = 1;
  $$variance{M}{HB2} = 0.34 * 0.34;       

  $$min{M}{HB3} = -0.99;
  $$max{M}{HB3} = 3.22;
  $$mean{M}{HB3} = 1.99;
  $$count{M}{HB3} = 1;
  $$variance{M}{HB3} = 0.34 * 0.34;       

  $$min{M}{HG2} = -0.36;
  $$max{M}{HG2} = 4.40;
  $$mean{M}{HG2} = 2.42;
  $$count{M}{HG2} = 1;
  $$variance{M}{HG2} = 0.35 * 0.35;       

  $$min{M}{HG3} = -0.30;
  $$max{M}{HG3} = 4.24;
  $$mean{M}{HG3} = 2.39;
  $$count{M}{HG3} = 1;
  $$variance{M}{HG3} = 0.38 * 0.38;       

  $$min{M}{HE} = -0.21;
  $$max{M}{HE} = 17.06;
  $$mean{M}{HE} = 1.89;
  $$count{M}{HE} = 1;
  $$variance{M}{HE} = 0.46 * 0.46;       

  $$min{M}{HE1} = -0.21;
  $$max{M}{HE1} = 17.06;
  $$mean{M}{HE1} = 1.89;
  $$count{M}{HE1} = 1;
  $$variance{M}{HE1} = 0.46 * 0.46;       
  $$invisible{M}{HE1} = 1;

  $$min{M}{HE2} = -0.21;
  $$max{M}{HE2} = 17.06;
  $$mean{M}{HE2} = 1.89;
  $$count{M}{HE2} = 1;
  $$variance{M}{HE2} = 0.46 * 0.46;       
  $$invisible{M}{HE2} = 1;

  $$min{M}{HE3} = -0.21;
  $$max{M}{HE3} = 17.06;
  $$mean{M}{HE3} = 1.89;
  $$count{M}{HE3} = 1;
  $$variance{M}{HE3} = 0.46 * 0.46;       
  $$invisible{M}{HE3} = 1;

  $$min{M}{C} = 167.40;
  $$max{M}{C} = 183.16;
  $$mean{M}{C} = 176.18;
  $$count{M}{C} = 1;
  $$variance{M}{C} = 2.09 * 2.09;       

  $$min{M}{CA} = 45.50;
  $$max{M}{CA} = 66.56;
  $$mean{M}{CA} = 56.11;
  $$count{M}{CA} = 1;
  $$variance{M}{CA} = 2.23 * 2.23;       

  $$min{M}{CB} = 20.98;
  $$max{M}{CB} = 46.46;
  $$mean{M}{CB} = 32.99;
  $$count{M}{CB} = 1;
  $$variance{M}{CB} = 2.24 * 2.24;       

  $$min{M}{CG} = 20.46;
  $$max{M}{CG} = 38.58;
  $$mean{M}{CG} = 32.01;
  $$count{M}{CG} = 1;
  $$variance{M}{CG} = 1.24 * 1.24;       

  $$min{M}{CE} = 0.00;
  $$max{M}{CE} = 37.40;
  $$mean{M}{CE} = 17.07;
  $$count{M}{CE} = 1;
  $$variance{M}{CE} = 1.58 * 1.58;       

  $$min{M}{N} = 87.60;
  $$max{M}{N} = 135.66;
  $$mean{M}{N} = 120.09;
  $$count{M}{N} = 1;
  $$variance{M}{N} = 3.57 * 3.57;       


  $$min{F}{H} = 4.81;
  $$max{F}{H} = 12.18;
  $$mean{F}{H} = 8.36;
  $$count{F}{H} = 1;
  $$variance{F}{H} = 0.72 * 0.72;       

  $$min{F}{HA} = 1.78;
  $$max{F}{HA} = 6.87;
  $$mean{F}{HA} = 4.63;
  $$count{F}{HA} = 1;
  $$variance{F}{HA} = 0.57 * 0.57;       

  $$min{F}{HB2} = 0.16;
  $$max{F}{HB2} = 4.46;
  $$mean{F}{HB2} = 3.00;
  $$count{F}{HB2} = 1;
  $$variance{F}{HB2} = 0.37 * 0.37;       

  $$min{F}{HB3} = -0.21;
  $$max{F}{HB3} = 4.69;
  $$mean{F}{HB3} = 2.93;
  $$count{F}{HB3} = 1;
  $$variance{F}{HB3} = 0.40 * 0.40;       

  $$min{F}{HD1} = 4.97;
  $$max{F}{HD1} = 8.15;
  $$mean{F}{HD1} = 7.06;
  $$count{F}{HD1} = 1;
  $$variance{F}{HD1} = 0.31 * 0.31;       

  $$min{F}{HD2} = 4.97;
  $$max{F}{HD2} = 8.15;
  $$mean{F}{HD2} = 7.06;
  $$count{F}{HD2} = 1;
  $$variance{F}{HD2} = 0.31 * 0.31;       

  $$min{F}{HE1} = 4.38;
  $$max{F}{HE1} = 8.80;
  $$mean{F}{HE1} = 7.08;
  $$count{F}{HE1} = 1;
  $$variance{F}{HE1} = 0.31 * 0.31;       

  $$min{F}{HE2} = 4.38;
  $$max{F}{HE2} = 8.80;
  $$mean{F}{HE2} = 7.08;
  $$count{F}{HE2} = 1;
  $$variance{F}{HE2} = 0.32 * 0.32;       

  $$min{F}{HZ} = 4.32;
  $$max{F}{HZ} = 9.50;
  $$mean{F}{HZ} = 7.00;
  $$count{F}{HZ} = 1;
  $$variance{F}{HZ} = 0.42 * 0.42;       

  $$min{F}{C} = 166.85;
  $$max{F}{C} = 184.16;
  $$mean{F}{C} = 175.42;
  $$count{F}{C} = 1;
  $$variance{F}{C} = 1.99 * 1.99;       

  $$min{F}{CA} = 47.31;
  $$max{F}{CA} = 69.82;
  $$mean{F}{CA} = 58.08;
  $$count{F}{CA} = 1;
  $$variance{F}{CA} = 2.57 * 2.57;       

  $$min{F}{CB} = 25.52;
  $$max{F}{CB} = 48.53;
  $$mean{F}{CB} = 39.99;
  $$count{F}{CB} = 1;
  $$variance{F}{CB} = 2.09 * 2.09;       

  $$min{F}{CG} = 128.30;
  $$max{F}{CG} = 144.00;
  $$mean{F}{CG} = 138.41;
  $$count{F}{CG} = 1;
  $$variance{F}{CG} = 2.04 * 2.04;       

  $$min{F}{CD1} = 116.95;
  $$max{F}{CD1} = 136.73;
  $$mean{F}{CD1} = 131.58;
  $$count{F}{CD1} = 1;
  $$variance{F}{CD1} = 1.18 * 1.18;       

  $$min{F}{CD2} = 120.00;
  $$max{F}{CD2} = 138.25;
  $$mean{F}{CD2} = 131.63;
  $$count{F}{CD2} = 1;
  $$variance{F}{CD2} = 1.12 * 1.12;       

  $$min{F}{CE1} = 114.75;
  $$max{F}{CE1} = 139.56;
  $$mean{F}{CE1} = 130.71;
  $$count{F}{CE1} = 1;
  $$variance{F}{CE1} = 1.30 * 1.30;       

  $$min{F}{CE2} = 114.70;
  $$max{F}{CE2} = 139.70;
  $$mean{F}{CE2} = 130.76;
  $$count{F}{CE2} = 1;
  $$variance{F}{CE2} = 1.13 * 1.13;       

  $$min{F}{CZ} = 116.46;
  $$max{F}{CZ} = 138.60;
  $$mean{F}{CZ} = 129.21;
  $$count{F}{CZ} = 1;
  $$variance{F}{CZ} = 1.43 * 1.43;       

  $$min{F}{N} = 102.20;
  $$max{F}{N} = 139.02;
  $$mean{F}{N} = 120.45;
  $$count{F}{N} = 1;
  $$variance{F}{N} = 4.18 * 4.18;       


  $$min{P}{HA} = 1.63;
  $$max{P}{HA} = 6.05;
  $$mean{P}{HA} = 4.40;
  $$count{P}{HA} = 1;
  $$variance{P}{HA} = 0.33 * 0.33;       

  $$min{P}{HB2} = -0.28;
  $$max{P}{HB2} = 4.35;
  $$mean{P}{HB2} = 2.08;
  $$count{P}{HB2} = 1;
  $$variance{P}{HB2} = 0.35 * 0.35;       

  $$min{P}{HB3} = -1.07;
  $$max{P}{HB3} = 3.79;
  $$mean{P}{HB3} = 2.00;
  $$count{P}{HB3} = 1;
  $$variance{P}{HB3} = 0.36 * 0.36;       

  $$min{P}{HG2} = -0.47;
  $$max{P}{HG2} = 4.42;
  $$mean{P}{HG2} = 1.93;
  $$count{P}{HG2} = 1;
  $$variance{P}{HG2} = 0.31 * 0.31;       

  $$min{P}{HG3} = -0.90;
  $$max{P}{HG3} = 4.42;
  $$mean{P}{HG3} = 1.90;
  $$count{P}{HG3} = 1;
  $$variance{P}{HG3} = 0.33 * 0.33;       

  $$min{P}{HD2} = 0.63;
  $$max{P}{HD2} = 5.36;
  $$mean{P}{HD2} = 3.65;
  $$count{P}{HD2} = 1;
  $$variance{P}{HD2} = 0.35 * 0.35;       

  $$min{P}{HD3} = -0.26;
  $$max{P}{HD3} = 5.36;
  $$mean{P}{HD3} = 3.61;
  $$count{P}{HD3} = 1;
  $$variance{P}{HD3} = 0.39 * 0.39;       

  $$min{P}{C} = 168.38;
  $$max{P}{C} = 182.84;
  $$mean{P}{C} = 176.75;
  $$count{P}{C} = 1;
  $$variance{P}{C} = 1.51 * 1.51;       

  $$min{P}{CA} = 50.12;
  $$max{P}{CA} = 70.67;
  $$mean{P}{CA} = 63.33;
  $$count{P}{CA} = 1;
  $$variance{P}{CA} = 1.52 * 1.52;       

  $$min{P}{CB} = 23.33;
  $$max{P}{CB} = 43.70;
  $$mean{P}{CB} = 31.85;
  $$count{P}{CB} = 1;
  $$variance{P}{CB} = 1.18 * 1.18;       

  $$min{P}{CG} = 18.28;
  $$max{P}{CG} = 33.90;
  $$mean{P}{CG} = 27.17;
  $$count{P}{CG} = 1;
  $$variance{P}{CG} = 1.09 * 1.09;       

  $$min{P}{CD} = 40.05;
  $$max{P}{CD} = 58.30;
  $$mean{P}{CD} = 50.32;
  $$count{P}{CD} = 1;
  $$variance{P}{CD} = 0.99 * 0.99;       

  $$min{P}{N} = 110.91;
  $$max{P}{N} = 145.26;
  $$mean{P}{N} = 134.16;
  $$count{P}{N} = 1;
  $$variance{P}{N} = 6.62 * 6.62;       


  $$min{S}{H} = 2.32;
  $$max{S}{H} = 13.13;
  $$mean{S}{H} = 8.28;
  $$count{S}{H} = 1;
  $$variance{S}{H} = 0.59 * 0.59;       

  $$min{S}{HA} = 1.58;
  $$max{S}{HA} = 6.85;
  $$mean{S}{HA} = 4.48;
  $$count{S}{HA} = 1;
  $$variance{S}{HA} = 0.40 * 0.40;       

  $$min{S}{HB2} = 1.74;
  $$max{S}{HB2} = 5.41;
  $$mean{S}{HB2} = 3.88;
  $$count{S}{HB2} = 1;
  $$variance{S}{HB2} = 0.25 * 0.25;       

  $$min{S}{HB3} = 1.55;
  $$max{S}{HB3} = 5.27;
  $$mean{S}{HB3} = 3.85;
  $$count{S}{HB3} = 1;
  $$variance{S}{HB3} = 0.27 * 0.27;       

  $$min{S}{HG} = 0.00;
  $$max{S}{HG} = 8.97;
  $$mean{S}{HG} = 5.36;
  $$count{S}{HG} = 1;
  $$variance{S}{HG} = 1.03 * 1.03;       

  $$min{S}{C} = 164.47;
  $$max{S}{C} = 184.88;
  $$mean{S}{C} = 174.62;
  $$count{S}{C} = 1;
  $$variance{S}{C} = 1.72 * 1.72;       

  $$min{S}{CA} = 45.13;
  $$max{S}{CA} = 68.40;
  $$mean{S}{CA} = 58.72;
  $$count{S}{CA} = 1;
  $$variance{S}{CA} = 2.07 * 2.07;       

  $$min{S}{CB} = 46.69;
  $$max{S}{CB} = 76.39;
  $$mean{S}{CB} = 63.80;
  $$count{S}{CB} = 1;
  $$variance{S}{CB} = 1.48 * 1.48;       

  $$min{S}{N} = 99.62;
  $$max{S}{N} = 133.68;
  $$mean{S}{N} = 116.28;
  $$count{S}{N} = 1;
  $$variance{S}{N} = 3.52 * 3.52;       


  $$min{T}{H} = 5.54;
  $$max{T}{H} = 11.73;
  $$mean{T}{H} = 8.24;
  $$count{T}{H} = 1;
  $$variance{T}{H} = 0.62 * 0.62;       

  $$min{T}{HA} = 0.87;
  $$max{T}{HA} = 6.63;
  $$mean{T}{HA} = 4.46;
  $$count{T}{HA} = 1;
  $$variance{T}{HA} = 0.48 * 0.48;       

  $$min{T}{HB} = 0.92;
  $$max{T}{HB} = 8.35;
  $$mean{T}{HB} = 4.17;
  $$count{T}{HB} = 1;
  $$variance{T}{HB} = 0.33 * 0.33;       

  $$min{T}{HG1} = 0.32;
  $$max{T}{HG1} = 8.95;
  $$mean{T}{HG1} = 4.92;
  $$count{T}{HG1} = 1;
  $$variance{T}{HG1} = 1.58 * 1.58;       

  $$min{T}{HG2} = -1.19;
  $$max{T}{HG2} = 3.54;
  $$mean{T}{HG2} = 1.14;
  $$count{T}{HG2} = 1;
  $$variance{T}{HG2} = 0.23 * 0.23;       

  $$min{T}{HG21} = -1.19;
  $$max{T}{HG21} = 3.54;
  $$mean{T}{HG21} = 1.14;
  $$count{T}{HG21} = 1;
  $$variance{T}{HG21} = 0.23 * 0.23;       

  $$min{T}{HG22} = -1.19;
  $$max{T}{HG22} = 3.54;
  $$mean{T}{HG22} = 1.14;
  $$count{T}{HG22} = 1;
  $$variance{T}{HG22} = 0.23 * 0.23;       

  $$min{T}{HG23} = -1.19;
  $$max{T}{HG23} = 3.54;
  $$mean{T}{HG23} = 1.14;
  $$count{T}{HG23} = 1;
  $$variance{T}{HG23} = 0.23 * 0.23;       

  $$min{T}{C} = 165.50;
  $$max{T}{C} = 184.43;
  $$mean{T}{C} = 174.54;
  $$count{T}{C} = 1;
  $$variance{T}{C} = 1.76 * 1.76;       

  $$min{T}{CA} = 51.61;
  $$max{T}{CA} = 72.80;
  $$mean{T}{CA} = 62.22;
  $$count{T}{CA} = 1;
  $$variance{T}{CA} = 2.59 * 2.59;       

  $$min{T}{CB} = 43.10;
  $$max{T}{CB} = 80.22;
  $$mean{T}{CB} = 69.73;
  $$count{T}{CB} = 1;
  $$variance{T}{CB} = 1.63 * 1.63;       

  $$min{T}{CG2} = 11.70;
  $$max{T}{CG2} = 36.73;
  $$mean{T}{CG2} = 21.55;
  $$count{T}{CG2} = 1;
  $$variance{T}{CG2} = 1.11 * 1.11;       

  $$min{T}{N} = 95.77;
  $$max{T}{N} = 138.27;
  $$mean{T}{N} = 115.42;
  $$count{T}{N} = 1;
  $$variance{T}{N} = 4.75 * 4.75;       


  $$min{W}{H} = 5.16;
  $$max{W}{H} = 11.76;
  $$mean{W}{H} = 8.29;
  $$count{W}{H} = 1;
  $$variance{W}{H} = 0.79 * 0.79;       

  $$min{W}{HA} = 2.24;
  $$max{W}{HA} = 6.55;
  $$mean{W}{HA} = 4.68;
  $$count{W}{HA} = 1;
  $$variance{W}{HA} = 0.53 * 0.53;       

  $$min{W}{HB2} = 0.42;
  $$max{W}{HB2} = 4.54;
  $$mean{W}{HB2} = 3.19;
  $$count{W}{HB2} = 1;
  $$variance{W}{HB2} = 0.35 * 0.35;       

  $$min{W}{HB3} = 0.31;
  $$max{W}{HB3} = 4.44;
  $$mean{W}{HB3} = 3.12;
  $$count{W}{HB3} = 1;
  $$variance{W}{HB3} = 0.36 * 0.36;       

  $$min{W}{HD1} = 4.90;
  $$max{W}{HD1} = 10.75;
  $$mean{W}{HD1} = 7.14;
  $$count{W}{HD1} = 1;
  $$variance{W}{HD1} = 0.36 * 0.36;       

  $$min{W}{HE1} = 5.12;
  $$max{W}{HE1} = 14.39;
  $$mean{W}{HE1} = 10.08;
  $$count{W}{HE1} = 1;
  $$variance{W}{HE1} = 0.66 * 0.66;       

  $$min{W}{HE3} = 4.89;
  $$max{W}{HE3} = 8.92;
  $$mean{W}{HE3} = 7.31;
  $$count{W}{HE3} = 1;
  $$variance{W}{HE3} = 0.41 * 0.41;       

  $$min{W}{HZ2} = 4.90;
  $$max{W}{HZ2} = 8.60;
  $$mean{W}{HZ2} = 7.28;
  $$count{W}{HZ2} = 1;
  $$variance{W}{HZ2} = 0.33 * 0.33;       

  $$min{W}{HZ3} = 3.88;
  $$max{W}{HZ3} = 8.90;
  $$mean{W}{HZ3} = 6.86;
  $$count{W}{HZ3} = 1;
  $$variance{W}{HZ3} = 0.40 * 0.40;       

  $$min{W}{HH2} = 4.39;
  $$max{W}{HH2} = 10.90;
  $$mean{W}{HH2} = 6.98;
  $$count{W}{HH2} = 1;
  $$variance{W}{HH2} = 0.39 * 0.39;       

  $$min{W}{C} = 168.17;
  $$max{W}{C} = 181.89;
  $$mean{W}{C} = 176.12;
  $$count{W}{C} = 1;
  $$variance{W}{C} = 2.01 * 2.01;       

  $$min{W}{CA} = 44.69;
  $$max{W}{CA} = 69.76;
  $$mean{W}{CA} = 57.66;
  $$count{W}{CA} = 1;
  $$variance{W}{CA} = 2.58 * 2.58;       

  $$min{W}{CB} = 21.10;
  $$max{W}{CB} = 43.02;
  $$mean{W}{CB} = 30.01;
  $$count{W}{CB} = 1;
  $$variance{W}{CB} = 2.01 * 2.01;       

  $$min{W}{CG} = 105.30;
  $$max{W}{CG} = 116.53;
  $$mean{W}{CG} = 110.59;
  $$count{W}{CG} = 1;
  $$variance{W}{CG} = 1.88 * 1.88;       

  $$min{W}{CD1} = 108.45;
  $$max{W}{CD1} = 132.35;
  $$mean{W}{CD1} = 126.51;
  $$count{W}{CD1} = 1;
  $$variance{W}{CD1} = 1.83 * 1.83;       

  $$min{W}{CD2} = 120.20;
  $$max{W}{CD2} = 132.62;
  $$mean{W}{CD2} = 127.57;
  $$count{W}{CD2} = 1;
  $$variance{W}{CD2} = 1.55 * 1.55;       

  $$min{W}{CE2} = 113.89;
  $$max{W}{CE2} = 177.71;
  $$mean{W}{CE2} = 138.31;
  $$count{W}{CE2} = 1;
  $$variance{W}{CE2} = 6.98 * 6.98;       

  $$min{W}{CE3} = 93.34;
  $$max{W}{CE3} = 137.60;
  $$mean{W}{CE3} = 120.43;
  $$count{W}{CE3} = 1;
  $$variance{W}{CE3} = 1.79 * 1.79;       

  $$min{W}{CZ2} = 109.53;
  $$max{W}{CZ2} = 125.70;
  $$mean{W}{CZ2} = 114.26;
  $$count{W}{CZ2} = 1;
  $$variance{W}{CZ2} = 1.12 * 1.12;       

  $$min{W}{CZ3} = 98.61;
  $$max{W}{CZ3} = 138.39;
  $$mean{W}{CZ3} = 121.35;
  $$count{W}{CZ3} = 1;
  $$variance{W}{CZ3} = 1.53 * 1.53;       

  $$min{W}{CH2} = 112.43;
  $$max{W}{CH2} = 131.54;
  $$mean{W}{CH2} = 123.86;
  $$count{W}{CH2} = 1;
  $$variance{W}{CH2} = 1.42 * 1.42;       

  $$min{W}{N} = 104.80;
  $$max{W}{N} = 138.11;
  $$mean{W}{N} = 121.68;
  $$count{W}{N} = 1;
  $$variance{W}{N} = 4.18 * 4.18;       

  $$min{W}{NE1} = 107.64;
  $$max{W}{NE1} = 144.36;
  $$mean{W}{NE1} = 129.32;
  $$count{W}{NE1} = 1;
  $$variance{W}{NE1} = 2.11 * 2.11;       


  $$min{Y}{H} = 4.16;
  $$max{Y}{H} = 12.01;
  $$mean{Y}{H} = 8.32;
  $$count{Y}{H} = 1;
  $$variance{Y}{H} = 0.73 * 0.73;       

  $$min{Y}{HA} = 1.20;
  $$max{Y}{HA} = 6.73;
  $$mean{Y}{HA} = 4.63;
  $$count{Y}{HA} = 1;
  $$variance{Y}{HA} = 0.56 * 0.56;       

  $$min{Y}{HB2} = 0.31;
  $$max{Y}{HB2} = 4.70;
  $$mean{Y}{HB2} = 2.91;
  $$count{Y}{HB2} = 1;
  $$variance{Y}{HB2} = 0.37 * 0.37;       

  $$min{Y}{HB3} = -0.19;
  $$max{Y}{HB3} = 4.70;
  $$mean{Y}{HB3} = 2.84;
  $$count{Y}{HB3} = 1;
  $$variance{Y}{HB3} = 0.39 * 0.39;       

  $$min{Y}{HD1} = 4.82;
  $$max{Y}{HD1} = 8.53;
  $$mean{Y}{HD1} = 6.93;
  $$count{Y}{HD1} = 1;
  $$variance{Y}{HD1} = 0.30 * 0.30;       

  $$min{Y}{HD2} = 4.97;
  $$max{Y}{HD2} = 8.50;
  $$mean{Y}{HD2} = 6.93;
  $$count{Y}{HD2} = 1;
  $$variance{Y}{HD2} = 0.30 * 0.30;       

  $$min{Y}{HE1} = 4.58;
  $$max{Y}{HE1} = 7.86;
  $$mean{Y}{HE1} = 6.70;
  $$count{Y}{HE1} = 1;
  $$variance{Y}{HE1} = 0.23 * 0.23;       

  $$min{Y}{HE2} = 4.56;
  $$max{Y}{HE2} = 8.50;
  $$mean{Y}{HE2} = 6.71;
  $$count{Y}{HE2} = 1;
  $$variance{Y}{HE2} = 0.23 * 0.23;       

  $$min{Y}{HH} = 5.99;
  $$max{Y}{HH} = 13.75;
  $$mean{Y}{HH} = 9.30;
  $$count{Y}{HH} = 1;
  $$variance{Y}{HH} = 1.36 * 1.36;       

  $$min{Y}{C} = 167.86;
  $$max{Y}{C} = 184.78;
  $$mean{Y}{C} = 175.40;
  $$count{Y}{C} = 1;
  $$variance{Y}{C} = 1.99 * 1.99;       

  $$min{Y}{CA} = 49.08;
  $$max{Y}{CA} = 66.43;
  $$mean{Y}{CA} = 58.13;
  $$count{Y}{CA} = 1;
  $$variance{Y}{CA} = 2.51 * 2.51;       

  $$min{Y}{CB} = 28.82;
  $$max{Y}{CB} = 57.73;
  $$mean{Y}{CB} = 39.32;
  $$count{Y}{CB} = 1;
  $$variance{Y}{CB} = 2.16 * 2.16;       

  $$min{Y}{CG} = 117.70;
  $$max{Y}{CG} = 174.59;
  $$mean{Y}{CG} = 129.75;
  $$count{Y}{CG} = 1;
  $$variance{Y}{CG} = 4.96 * 4.96;       

  $$min{Y}{CD1} = 116.44;
  $$max{Y}{CD1} = 141.57;
  $$mean{Y}{CD1} = 132.77;
  $$count{Y}{CD1} = 1;
  $$variance{Y}{CD1} = 1.17 * 1.17;       

  $$min{Y}{CD2} = 113.00;
  $$max{Y}{CD2} = 137.80;
  $$mean{Y}{CD2} = 132.73;
  $$count{Y}{CD2} = 1;
  $$variance{Y}{CD2} = 1.30 * 1.30;       

  $$min{Y}{CE1} = 110.70;
  $$max{Y}{CE1} = 135.80;
  $$mean{Y}{CE1} = 117.93;
  $$count{Y}{CE1} = 1;
  $$variance{Y}{CE1} = 1.19 * 1.19;       

  $$min{Y}{CE2} = 112.58;
  $$max{Y}{CE2} = 134.01;
  $$mean{Y}{CE2} = 117.90;
  $$count{Y}{CE2} = 1;
  $$variance{Y}{CE2} = 1.18 * 1.18;       

  $$min{Y}{CZ} = 153.54;
  $$max{Y}{CZ} = 162.70;
  $$mean{Y}{CZ} = 156.76;
  $$count{Y}{CZ} = 1;
  $$variance{Y}{CZ} = 1.99 * 1.99;       

  $$min{Y}{N} = 100.09;
  $$max{Y}{N} = 144.96;
  $$mean{Y}{N} = 120.52;
  $$count{Y}{N} = 1;
  $$variance{Y}{N} = 4.20 * 4.20;       


  $$min{V}{H} = 3.98;
  $$max{V}{H} = 12.59;
  $$mean{V}{H} = 8.29;
  $$count{V}{H} = 1;
  $$variance{V}{H} = 0.67 * 0.67;       

  $$min{V}{HA} = 0.97;
  $$max{V}{HA} = 6.30;
  $$mean{V}{HA} = 4.19;
  $$count{V}{HA} = 1;
  $$variance{V}{HA} = 0.58 * 0.58;       

  $$min{V}{HB} = -1.22;
  $$max{V}{HB} = 3.32;
  $$mean{V}{HB} = 1.98;
  $$count{V}{HB} = 1;
  $$variance{V}{HB} = 0.32 * 0.32;       

  $$min{V}{HG1} = -1.12;
  $$max{V}{HG1} = 2.57;
  $$mean{V}{HG1} = 0.83;
  $$count{V}{HG1} = 1;
  $$variance{V}{HG1} = 0.26 * 0.26;       

  $$min{V}{HG11} = -1.12;
  $$max{V}{HG11} = 2.57;
  $$mean{V}{HG11} = 0.83;
  $$count{V}{HG11} = 1;
  $$variance{V}{HG11} = 0.26 * 0.26;       
  $$invisible{V}{HG11} = 1;

  $$min{V}{HG12} = -1.12;
  $$max{V}{HG12} = 2.57;
  $$mean{V}{HG12} = 0.83;
  $$count{V}{HG12} = 1;
  $$variance{V}{HG12} = 0.26 * 0.26;       
  $$invisible{V}{HG12} = 1;

  $$min{V}{HG13} = -1.12;
  $$max{V}{HG13} = 2.57;
  $$mean{V}{HG13} = 0.83;
  $$count{V}{HG13} = 1;
  $$variance{V}{HG13} = 0.26 * 0.26;       
  $$invisible{V}{HG13} = 1;

  $$min{V}{HG2} = -1.98;
  $$max{V}{HG2} = 2.78;
  $$mean{V}{HG2} = 0.80;
  $$count{V}{HG2} = 1;
  $$variance{V}{HG2} = 0.28 * 0.28;       

  $$min{V}{HG21} = -1.98;
  $$max{V}{HG21} = 2.78;
  $$mean{V}{HG21} = 0.80;
  $$count{V}{HG21} = 1;
  $$variance{V}{HG21} = 0.28 * 0.28;       
  $$invisible{V}{HG21} = 1;

  $$min{V}{HG22} = -1.98;
  $$max{V}{HG22} = 2.78;
  $$mean{V}{HG22} = 0.80;
  $$count{V}{HG22} = 1;
  $$variance{V}{HG22} = 0.28 * 0.28;       
  $$invisible{V}{HG22} = 1;

  $$min{V}{HG23} = -1.98;
  $$max{V}{HG23} = 2.78;
  $$mean{V}{HG23} = 0.80;
  $$count{V}{HG23} = 1;
  $$variance{V}{HG23} = 0.28 * 0.28;       
  $$invisible{V}{HG23} = 1;

  $$min{V}{C} = 165.65;
  $$max{V}{C} = 183.69;
  $$mean{V}{C} = 175.62;
  $$count{V}{C} = 1;
  $$variance{V}{C} = 1.90 * 1.90;       

  $$min{V}{CA} = 50.16;
  $$max{V}{CA} = 70.34;
  $$mean{V}{CA} = 62.49;
  $$count{V}{CA} = 1;
  $$variance{V}{CA} = 2.86 * 2.86;       

  $$min{V}{CB} = 20.55;
  $$max{V}{CB} = 45.33;
  $$mean{V}{CB} = 32.73;
  $$count{V}{CB} = 1;
  $$variance{V}{CB} = 1.79 * 1.79;       

  $$min{V}{CG1} = 13.53;
  $$max{V}{CG1} = 32.27;
  $$mean{V}{CG1} = 21.49;
  $$count{V}{CG1} = 1;
  $$variance{V}{CG1} = 1.36 * 1.36;       

  $$min{V}{CG2} = 13.58;
  $$max{V}{CG2} = 30.46;
  $$mean{V}{CG2} = 21.26;
  $$count{V}{CG2} = 1;
  $$variance{V}{CG2} = 1.56 * 1.56;       

  $$min{V}{N} = 97.22;
  $$max{V}{N} = 143.29;
  $$mean{V}{N} = 121.14;
  $$count{V}{N} = 1;
  $$variance{V}{N} = 4.54 * 4.54;       

  

  $$ambiguity{R}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{R}{HG} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{R}{HD} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{R}{HH1} = { "value" => 2, "first" => "1", "second" => "2" };
  $$ambiguity{R}{HH2} = { "value" => 2, "first" => "1", "second" => "2" };
  $$ambiguity{R}{NH} = { "value" => 2, "first" => "1", "second" => "2" };

  $$ambiguity{D}{HB} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{N}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{N}{HD2} = { "value" => 2, "first" => "1", "second" => "2" };

  $$ambiguity{C}{HB} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{E}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{E}{HG} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{Q}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{Q}{HG} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{Q}{HE2} = { "value" => 2, "first" => "1", "second" => "2" };

  $$ambiguity{G}{HA} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{H}{HB} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{I}{HG1} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{L}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{L}{HD} = { "value" => 2, "first" => "1", "second" => "2" };
  $$ambiguity{L}{CD} = { "value" => 2, "first" => "1", "second" => "2" };

  $$ambiguity{K}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{K}{HG} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{K}{HD} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{K}{HE} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{M}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{M}{HG} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{F}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{F}{HD} = { "value" => 3, "first" => "1", "second" => "2" };
  $$ambiguity{F}{HE} = { "value" => 3, "first" => "1", "second" => "2" };
  $$ambiguity{F}{CD} = { "value" => 3, "first" => "1", "second" => "2" };
  $$ambiguity{F}{CE} = { "value" => 3, "first" => "1", "second" => "2" };

  $$ambiguity{P}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{P}{HG} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{P}{HD} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{S}{HB} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{W}{HB} = { "value" => 2, "first" => "2", "second" => "3" };

  $$ambiguity{Y}{HB} = { "value" => 2, "first" => "2", "second" => "3" };
  $$ambiguity{Y}{HD} = { "value" => 3, "first" => "1", "second" => "2" };
  $$ambiguity{Y}{HE} = { "value" => 3, "first" => "1", "second" => "2" };
  $$ambiguity{Y}{CD} = { "value" => 3, "first" => "1", "second" => "2" };
  $$ambiguity{Y}{CE} = { "value" => 3, "first" => "1", "second" => "2" };

  $$ambiguity{V}{HG} = { "value" => 2, "first" => "1", "second" => "2" };
  $$ambiguity{V}{CG} = { "value" => 2, "first" => "1", "second" => "2" };
  
  
  my $restricted_type_lists = {};
  if (! $use_sidechains)
    {
    $$restricted_type_lists{P} = ['CA', 'CB'];
    $$restricted_type_lists{Q} = ['CA', 'CB'];
    $$restricted_type_lists{A} = ['CA', 'CB'];
    $$restricted_type_lists{R} = ['CA', 'CB'];
    $$restricted_type_lists{S} = ['CA', 'CB'];
    $$restricted_type_lists{C} = ['CA', 'CB'];
    $$restricted_type_lists{T} = ['CA', 'CB'];
    $$restricted_type_lists{D} = ['CA', 'CB'];
    $$restricted_type_lists{E} = ['CA', 'CB'];
    $$restricted_type_lists{V} = ['CA', 'CB'];
    $$restricted_type_lists{F} = ['CA', 'CB'];
    $$restricted_type_lists{W} = ['CA', 'CB'];
    $$restricted_type_lists{G} = ['CA'];
    $$restricted_type_lists{H} = ['CA', 'CB'];
    $$restricted_type_lists{Y} = ['CA', 'CB'];
    $$restricted_type_lists{I} = ['CA', 'CB'];
    $$restricted_type_lists{K} = ['CA', 'CB'];
    $$restricted_type_lists{L} = ['CA', 'CB'];
    $$restricted_type_lists{M} = ['CA', 'CB'];
    $$restricted_type_lists{N} = ['CA', 'CB'];
    }
  else
    {
    $$restricted_type_lists{P} = ['CA', 'CB', 'CD', 'CG'];
    $$restricted_type_lists{Q} = ['CA', 'CB', 'CD', 'CG'];
    $$restricted_type_lists{A} = ['CA', 'CB'];
    $$restricted_type_lists{R} = ['CA', 'CB', 'CD', 'CG'];
    $$restricted_type_lists{S} = ['CA', 'CB'];
    $$restricted_type_lists{C} = ['CA', 'CB'];
    $$restricted_type_lists{T} = ['CA', 'CB', 'CG2'];
    $$restricted_type_lists{D} = ['CA', 'CB', 'CG'];
    $$restricted_type_lists{E} = ['CA', 'CB', 'CD', 'CG'];
    $$restricted_type_lists{V} = ['CA', 'CB', 'CG1', 'CG2'];
    $$restricted_type_lists{F} = ['CA', 'CB', 'CD1', 'CD2', 'CE1', 'CE2', 'CG', 'CZ'];
    $$restricted_type_lists{W} = ['CA', 'CB', 'CD1', 'CD2', 'CE2', 'CE3', 'CG', 'CH2', 'CZ2', 'CZ3'];
    $$restricted_type_lists{G} = ['CA'];
    $$restricted_type_lists{H} = ['CA', 'CB', 'CD2', 'CE1','CG'];
    $$restricted_type_lists{Y} = ['CA', 'CB', 'CD1', 'CD2', 'CE1', 'CE2', 'CG', 'CZ'];
    $$restricted_type_lists{I} = ['CA', 'CB', 'CD1', 'CG1', 'CG2'];
    $$restricted_type_lists{K} = ['CA', 'CB', 'CD', 'CE', 'CG'];
    $$restricted_type_lists{L} = ['CA', 'CB', 'CD1', 'CD2', 'CG'];
    $$restricted_type_lists{M} = ['CA', 'CB', 'CE', 'CG'];
    $$restricted_type_lists{N} = ['CA', 'CB', 'CG'];
    }


  if (! $use_aromatics)
    {
    foreach my $aa (qw(F Y W))
      { @{$$restricted_type_lists{$aa}} = grep { $_ eq "CA" || $_ eq "CB"; } @{$$restricted_type_lists{$aa}}; }
    }


  # calculate deuteration isotope corrections if deuteration is present
  if ($deuteration > 0)
    {
    my $deuteration_corrections = {};


    # corrections for CA's calculated from Sandy Farmer's macro values.
    # corrections for sidechain carbons calculated from small molecule studies.
    # corrections for nitrogens come from a rough estimate of 0.16 for 2-bond effects and 0.06 for 3-bond effects
    # for A
    $$deuteration_corrections{A}{CA} =0.752;
    $$deuteration_corrections{A}{CB} =0.932;
    $$deuteration_corrections{A}{N} =0.34;

    # for C
    $$deuteration_corrections{C}{CA} =0.632;
    $$deuteration_corrections{C}{CB} =0.837;
    $$deuteration_corrections{C}{N} =0.28;

    # for D
    $$deuteration_corrections{D}{CA} =0.632;
    $$deuteration_corrections{D}{CB} =0.69;
    $$deuteration_corrections{D}{N} =0.28;

    # for E
    $$deuteration_corrections{E}{CA} =0.716;
    $$deuteration_corrections{E}{CB} =0.937;
    $$deuteration_corrections{E}{CG} =0.83;
    $$deuteration_corrections{E}{N} =0.28;

    # for F
    $$deuteration_corrections{F}{CA} =0.632;
    $$deuteration_corrections{F}{CB} =0.919;
    $$deuteration_corrections{F}{CG} =0.274;
    $$deuteration_corrections{F}{CD1} =0.429;
    $$deuteration_corrections{F}{CD2} =0.429;
    $$deuteration_corrections{F}{CE1} =0.500;
    $$deuteration_corrections{F}{CE2} =0.500;
    $$deuteration_corrections{F}{CZ} =0.496;
    $$deuteration_corrections{F}{N} =0.28;

    # for G
    $$deuteration_corrections{G}{CA} =0.784;
    $$deuteration_corrections{G}{N} =0.32;

    # for H
    $$deuteration_corrections{H}{CA} =0.632;
    $$deuteration_corrections{H}{CB} =0.832;
    $$deuteration_corrections{H}{CG} =0.365;
    $$deuteration_corrections{H}{CD2} =0.545;
    $$deuteration_corrections{H}{CE1} =0.475;
    $$deuteration_corrections{H}{N} =0.28;
    $$deuteration_corrections{H}{ND1} =0.34;
    $$deuteration_corrections{H}{NE2} =0.32;

    # for I
    $$deuteration_corrections{I}{CA} =0.722;
    $$deuteration_corrections{I}{CB} =1.092;
    $$deuteration_corrections{I}{CG1} =1.130;
    $$deuteration_corrections{I}{CG2} =1.020;
    $$deuteration_corrections{I}{CD1} =1.090;
    $$deuteration_corrections{I}{N} =0.22;

    # for K
    $$deuteration_corrections{K}{CA} =0.716;
    $$deuteration_corrections{K}{CB} =1.067;
    $$deuteration_corrections{K}{CG} =1.225;
    $$deuteration_corrections{K}{CD} =1.190;
    $$deuteration_corrections{K}{CE} =0.990;
    $$deuteration_corrections{K}{N} =0.28;
    $$deuteration_corrections{K}{NZ} =0.44;

    # for L
    $$deuteration_corrections{L}{CA} =0.674;
    $$deuteration_corrections{L}{CB} =1.067;
    $$deuteration_corrections{L}{CG} =1.215;
    $$deuteration_corrections{L}{CD1} =1.090;
    $$deuteration_corrections{L}{CD2} =1.090;
    $$deuteration_corrections{L}{N} =0.28;

    # for M
    $$deuteration_corrections{M}{CA} =0.716;
    $$deuteration_corrections{M}{CB} =0.917;
    $$deuteration_corrections{M}{CG} =0.995;
    $$deuteration_corrections{M}{CE} =0.855;
    $$deuteration_corrections{M}{N} =0.28;

    # for N
    $$deuteration_corrections{N}{CA} =0.632;
    $$deuteration_corrections{N}{CB} =0.757;
    $$deuteration_corrections{N}{N} =0.28;

    # for P
    $$deuteration_corrections{P}{CA} =0.716;
    $$deuteration_corrections{P}{CB} =1.027;
    $$deuteration_corrections{P}{CG} =1.158;
    $$deuteration_corrections{P}{CD} =0.952;
    $$deuteration_corrections{P}{N} =0.72;

    # for Q
    $$deuteration_corrections{Q}{CA} =0.716;
    $$deuteration_corrections{Q}{CB} =0.951;
    $$deuteration_corrections{Q}{CG} =0.915;
    $$deuteration_corrections{Q}{N} =0.28;

    # for R
    $$deuteration_corrections{R}{CA} =0.716;
    $$deuteration_corrections{R}{CB} =1.067;
    $$deuteration_corrections{R}{CG} =1.155;
    $$deuteration_corrections{R}{CD} =0.990;
    $$deuteration_corrections{R}{CZ} =0.070;
    $$deuteration_corrections{R}{N} =0.28;
    $$deuteration_corrections{R}{NE} =0.44;

    # for S
    $$deuteration_corrections{S}{CA} =0.632;
    $$deuteration_corrections{S}{CB} =0.837;
    $$deuteration_corrections{S}{N} =0.28;

    # for T
    $$deuteration_corrections{T}{CA} =0.638;
    $$deuteration_corrections{T}{CB} =0.867;
    $$deuteration_corrections{T}{CG} =0.950;
    $$deuteration_corrections{T}{N} =0.22;

    # for V
    $$deuteration_corrections{V}{CA} =0.764;
    $$deuteration_corrections{V}{CB} =1.057;
    $$deuteration_corrections{V}{CG1} =0.950;
    $$deuteration_corrections{V}{CG2} =0.950;
    $$deuteration_corrections{V}{N} =0.22;

    # for W
    $$deuteration_corrections{W}{CA} =0.632;
    $$deuteration_corrections{W}{CB} =0.832;
    $$deuteration_corrections{W}{CG} =0.365;
    $$deuteration_corrections{W}{CD1} =0.350;
    $$deuteration_corrections{W}{CD2} =0.213;
    $$deuteration_corrections{W}{CE2} =0.167;
    $$deuteration_corrections{W}{CE3} =0.429;
    $$deuteration_corrections{W}{CZ2} =0.429;
    $$deuteration_corrections{W}{CZ3} =0.511;
    $$deuteration_corrections{W}{CH2} =0.511;
    $$deuteration_corrections{W}{N} =0.28;
    $$deuteration_corrections{W}{NE1} =0.22;

    # for Y
    $$deuteration_corrections{Y}{CA} =0.632;
    $$deuteration_corrections{Y}{CB} =0.919;
    $$deuteration_corrections{Y}{CG} =0.299;
    $$deuteration_corrections{Y}{CD1} =0.418;
    $$deuteration_corrections{Y}{CD2} =0.418;
    $$deuteration_corrections{Y}{CE1} =0.390;
    $$deuteration_corrections{Y}{CE2} =0.390;
    $$deuteration_corrections{Y}{CZ} =0.220;
    $$deuteration_corrections{Y}{N} =0.28;


    # make the corrections
    foreach my $aa (keys %{$deuteration_corrections})
      {
      foreach my $atom (keys %{$$deuteration_corrections{$aa}})
	{
	$$min{$aa}{$atom} -= ($$deuteration_corrections{$aa}{$atom} * $deuteration);
	$$max{$aa}{$atom} -= ($$deuteration_corrections{$aa}{$atom} * $deuteration);
	$$mean{$aa}{$atom} -= ($$deuteration_corrections{$aa}{$atom} * $deuteration);
	}
      }
    }

  return $count, $mean, $variance, $restricted_type_lists, $min, $max, $ambiguity, $invisible;  
  }


#
#
#
#
#
sub initialize_rules
  {
  my $shift_order_rules = {};

#
# Rules for A
#
  $$shift_order_rules{A} = [];
  push @{$$shift_order_rules{A}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.999822852081488, 
				    "count" => 5645, 
				    "std" => 0.67262716017868 };
  
  push @{$$shift_order_rules{A}}, { "shift1" => "H", 
				    "shift2" => "HB", 
				    "consistency" => 0.99980578753156, 
				    "count" => 5149, 
				    "std" => 0.6411059681996 };
  
  push @{$$shift_order_rules{A}}, { "shift1" => "HA", 
				    "shift2" => "HB", 
				    "consistency" => 1, 
				    "count" => 5379, 
				    "std" => 0.481806120718844 };
  
  push @{$$shift_order_rules{A}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 0.999579478553406, 
				    "count" => 2378, 
				    "std" => 3.24949014655512 };
  
  push @{$$shift_order_rules{A}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 2131, 
				    "std" => 4.37496284156749 };
  
  push @{$$shift_order_rules{A}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.999452804377565, 
				    "count" => 3655, 
				    "std" => 3.36835701441261 };
  
  
#
# Rules for C
#
  $$shift_order_rules{C} = [];
  push @{$$shift_order_rules{C}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.999556541019956, 
				    "count" => 2255, 
				    "std" => 0.740808176021762 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 0.998581560283688, 
				    "count" => 2115, 
				    "std" => 2.49924452648262 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 0.99856184084372, 
				    "count" => 2086, 
				    "std" => 1.32389711280422 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.988351254480287, 
				    "count" => 2232, 
				    "std" => 1.20885128097665 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.988197911938266, 
				    "count" => 2203, 
				    "std" => 1.06409006345502 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 457, 
				    "std" => 3.11999058091006 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 402, 
				    "std" => 7.13701908863866 };
  
  push @{$$shift_order_rules{C}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 693, 
				    "std" => 8.75345523825386 };
  
  
#
# Rules for D
#
  $$shift_order_rules{D} = [];
  push @{$$shift_order_rules{D}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 4363, 
				    "std" => 0.665575920475457 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 3889, 
				    "std" => 0.641041913440267 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 3754, 
				    "std" => 0.636527016410019 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999496728736789, 
				    "count" => 3974, 
				    "std" => 0.391316031288384 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.999739311783107, 
				    "count" => 3836, 
				    "std" => 0.404394065888001 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 2028, 
				    "std" => 1.89742297730851 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1825, 
				    "std" => 2.50146393561638 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "CG", 
				    "shift2" => "C", 
				    "consistency" => 0.893203883495146, 
				    "count" => 103, 
				    "std" => 2.3031315414781 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.998947737635917, 
				    "count" => 2851, 
				    "std" => 3.3498593440932 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "CG", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 105, 
				    "std" => 2.71471334385783 };
  
  push @{$$shift_order_rules{D}}, { "shift1" => "CG", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 105, 
				    "std" => 2.08542439176942 };
  
  
#
# Rules for E
#
  $$shift_order_rules{E} = [];
  push @{$$shift_order_rules{E}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 5323, 
				    "std" => 0.707572563853101 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 4601, 
				    "std" => 0.654712935766439 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 4408, 
				    "std" => 0.651560774667759 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 3954, 
				    "std" => 0.63111388862318 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "H", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 3737, 
				    "std" => 0.63628636734603 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999787550456766, 
				    "count" => 4707, 
				    "std" => 0.493400869821471 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 4506, 
				    "std" => 0.501386347084964 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 4035, 
				    "std" => 0.494252903012574 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HA", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 3809, 
				    "std" => 0.495810926064176 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HG2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.93037816178312, 
				    "count" => 3993, 
				    "std" => 0.232672799551773 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HG3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.903588644884842, 
				    "count" => 3734, 
				    "std" => 0.254667445480462 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HG2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.926892950391645, 
				    "count" => 3830, 
				    "std" => 0.245790098175213 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "HG3", 
				    "shift2" => "HB3", 
				    "consistency" => 0.932038834951456, 
				    "count" => 3708, 
				    "std" => 0.221422973634797 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 2483, 
				    "std" => 1.72122158915684 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 2218, 
				    "std" => 3.14951591691102 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 1492, 
				    "std" => 2.17973382405667 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CD", 
				    "shift2" => "C", 
				    "consistency" => 0.990654205607477, 
				    "count" => 107, 
				    "std" => 2.14897586732958 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 3525, 
				    "std" => 3.35255340228967 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 2417, 
				    "std" => 2.30843759141916 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CD", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 109, 
				    "std" => 2.14912163386699 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CG", 
				    "shift2" => "CB", 
				    "consistency" => 0.99165623696287, 
				    "count" => 2397, 
				    "std" => 1.97825344074516 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CD", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 109, 
				    "std" => 2.69516160919061 };
  
  push @{$$shift_order_rules{E}}, { "shift1" => "CD", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 108, 
				    "std" => 1.31724863404979 };
  
  
#
# Rules for F
#
  $$shift_order_rules{F} = [];
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.999254287844892, 
				    "count" => 2682, 
				    "std" => 2.40245726478794 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2409, 
				    "std" => 0.822250172407837 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 0.99957337883959, 
				    "count" => 2344, 
				    "std" => 0.848040224519428 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HD1", 
				    "consistency" => 0.959357752132464, 
				    "count" => 1993, 
				    "std" => 0.815215339818829 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HD2", 
				    "consistency" => 0.959904248952723, 
				    "count" => 1671, 
				    "std" => 0.803016355040049 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HE1", 
				    "consistency" => 0.949303621169916, 
				    "count" => 1795, 
				    "std" => 0.859718409662288 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HE2", 
				    "consistency" => 0.949640287769784, 
				    "count" => 1529, 
				    "std" => 0.842548710212778 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "H", 
				    "shift2" => "HZ", 
				    "consistency" => 0.955523672883788, 
				    "count" => 1394, 
				    "std" => 0.990567053386996 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.995201919232307, 
				    "count" => 2501, 
				    "std" => 2.44820804399561 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.99548625359048, 
				    "count" => 2437, 
				    "std" => 2.4833134564353 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HD1", 
				    "shift2" => "HA", 
				    "consistency" => 0.997590361445783, 
				    "count" => 2075, 
				    "std" => 2.65104890356711 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HD2", 
				    "shift2" => "HA", 
				    "consistency" => 0.997699827487062, 
				    "count" => 1739, 
				    "std" => 2.87841623971972 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE1", 
				    "shift2" => "HA", 
				    "consistency" => 0.997334754797441, 
				    "count" => 1876, 
				    "std" => 2.79216634004746 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE2", 
				    "shift2" => "HA", 
				    "consistency" => 0.996867167919799, 
				    "count" => 1596, 
				    "std" => 3.00599910321745 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HZ", 
				    "shift2" => "HA", 
				    "consistency" => 0.993127147766323, 
				    "count" => 1455, 
				    "std" => 3.19066115566607 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HD1", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999027237354086, 
				    "count" => 2056, 
				    "std" => 0.430480450191139 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HD2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999425287356322, 
				    "count" => 1740, 
				    "std" => 0.413400564491996 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE1", 
				    "shift2" => "HB2", 
				    "consistency" => 0.998929336188437, 
				    "count" => 1868, 
				    "std" => 0.526820468069286 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE2", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1601, 
				    "std" => 0.500218710250736 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HZ", 
				    "shift2" => "HB2", 
				    "consistency" => 0.998611111111111, 
				    "count" => 1440, 
				    "std" => 0.726106078058077 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HD1", 
				    "shift2" => "HB3", 
				    "consistency" => 0.999510763209393, 
				    "count" => 2044, 
				    "std" => 0.478749716351467 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HD2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.999423631123919, 
				    "count" => 1735, 
				    "std" => 0.473600582675652 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE1", 
				    "shift2" => "HB3", 
				    "consistency" => 0.998385360602799, 
				    "count" => 1858, 
				    "std" => 0.568042519554574 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.99937343358396, 
				    "count" => 1596, 
				    "std" => 0.553040197566423 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HZ", 
				    "shift2" => "HB3", 
				    "consistency" => 0.998612074947953, 
				    "count" => 1441, 
				    "std" => 0.710924319804484 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE1", 
				    "shift2" => "HD1", 
				    "consistency" => 0.622222222222222, 
				    "count" => 2070, 
				    "std" => 0.451714867238585 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE2", 
				    "shift2" => "HD1", 
				    "consistency" => 0.632847533632287, 
				    "count" => 1784, 
				    "std" => 0.44634185425833 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HZ", 
				    "shift2" => "HD1", 
				    "consistency" => 0.57888198757764, 
				    "count" => 1610, 
				    "std" => 0.867439600697978 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE1", 
				    "shift2" => "HD2", 
				    "consistency" => 0.631019036954087, 
				    "count" => 1786, 
				    "std" => 0.48549369433106 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE2", 
				    "shift2" => "HD2", 
				    "consistency" => 0.633724176437744, 
				    "count" => 1791, 
				    "std" => 0.450760001019528 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HZ", 
				    "shift2" => "HD2", 
				    "consistency" => 0.582921665490473, 
				    "count" => 1417, 
				    "std" => 0.90507002756208 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE1", 
				    "shift2" => "HZ", 
				    "consistency" => 0.544382371198014, 
				    "count" => 1611, 
				    "std" => 0.671479813383223 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "HE2", 
				    "shift2" => "HZ", 
				    "consistency" => 0.54654442877292, 
				    "count" => 1418, 
				    "std" => 0.676765106037235 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1246, 
				    "std" => 2.69282339223356 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1111, 
				    "std" => 3.60502208170709 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CD1", 
				    "consistency" => 1, 
				    "count" => 387, 
				    "std" => 2.41510270609721 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CD2", 
				    "consistency" => 1, 
				    "count" => 239, 
				    "std" => 2.44109934477568 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CE1", 
				    "consistency" => 1, 
				    "count" => 335, 
				    "std" => 7.15965882093575 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CE2", 
				    "consistency" => 1, 
				    "count" => 205, 
				    "std" => 8.91217553862507 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "C", 
				    "shift2" => "CZ", 
				    "consistency" => 1, 
				    "count" => 263, 
				    "std" => 2.72065793152339 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.999434389140271, 
				    "count" => 1768, 
				    "std" => 3.84179566314196 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD1", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 666, 
				    "std" => 4.11157829213382 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD2", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 435, 
				    "std" => 2.87339577843206 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CE1", 
				    "shift2" => "CA", 
				    "consistency" => 0.998257839721254, 
				    "count" => 574, 
				    "std" => 6.50687028162097 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CE2", 
				    "shift2" => "CA", 
				    "consistency" => 0.997304582210243, 
				    "count" => 371, 
				    "std" => 6.86391356233657 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CZ", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 450, 
				    "std" => 5.85960174236759 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD1", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 663, 
				    "std" => 3.53126868553211 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD2", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 433, 
				    "std" => 2.30711558428963 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CE1", 
				    "shift2" => "CB", 
				    "consistency" => 0.998242530755712, 
				    "count" => 569, 
				    "std" => 6.42357909918143 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CE2", 
				    "shift2" => "CB", 
				    "consistency" => 0.997282608695652, 
				    "count" => 368, 
				    "std" => 6.94819161488477 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CZ", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 444, 
				    "std" => 5.74584452866964 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD1", 
				    "shift2" => "CE1", 
				    "consistency" => 0.74113475177305, 
				    "count" => 564, 
				    "std" => 2.55661108776269 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD1", 
				    "shift2" => "CE2", 
				    "consistency" => 0.718579234972678, 
				    "count" => 366, 
				    "std" => 1.37447346899721 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD1", 
				    "shift2" => "CZ", 
				    "consistency" => 0.896551724137931, 
				    "count" => 435, 
				    "std" => 3.16290193608521 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD2", 
				    "shift2" => "CE1", 
				    "consistency" => 0.718579234972678, 
				    "count" => 366, 
				    "std" => 1.40004885323031 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD2", 
				    "shift2" => "CE2", 
				    "consistency" => 0.715846994535519, 
				    "count" => 366, 
				    "std" => 1.36937674424878 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CD2", 
				    "shift2" => "CZ", 
				    "consistency" => 0.89419795221843, 
				    "count" => 293, 
				    "std" => 2.03533617738212 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CE1", 
				    "shift2" => "CZ", 
				    "consistency" => 0.845794392523365, 
				    "count" => 428, 
				    "std" => 1.79079286268783 };
  
  push @{$$shift_order_rules{F}}, { "shift1" => "CE2", 
				    "shift2" => "CZ", 
				    "consistency" => 0.839160839160839, 
				    "count" => 286, 
				    "std" => 1.35402382483776 };
  
  
#
# Rules for G
#
  $$shift_order_rules{G} = [];
  push @{$$shift_order_rules{G}}, { "shift1" => "H", 
				    "shift2" => "HA2", 
				    "consistency" => 0.99798460974716, 
				    "count" => 5458, 
				    "std" => 1.82862317509244 };
  
  push @{$$shift_order_rules{G}}, { "shift1" => "H", 
				    "shift2" => "HA3", 
				    "consistency" => 0.99905303030303, 
				    "count" => 5280, 
				    "std" => 1.85874574173548 };
  
  push @{$$shift_order_rules{G}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 2275, 
				    "std" => 2.33620981124134 };
  
  
#
# Rules for H
#
  $$shift_order_rules{H} = [];
  push @{$$shift_order_rules{H}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 1601, 
				    "std" => 0.775592848380883 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 0.998586572438163, 
				    "count" => 1415, 
				    "std" => 0.824586609772726 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 0.997118155619596, 
				    "count" => 1388, 
				    "std" => 0.904592266640919 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD1", 
				    "shift2" => "H", 
				    "consistency" => 0.508064516129032, 
				    "count" => 124, 
				    "std" => 2.18613850526241 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "H", 
				    "shift2" => "HD2", 
				    "consistency" => 0.950757575757576, 
				    "count" => 1056, 
				    "std" => 2.47415551235434 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "H", 
				    "shift2" => "HE1", 
				    "consistency" => 0.571580063626723, 
				    "count" => 943, 
				    "std" => 1.994434933453 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.992622401073105, 
				    "count" => 1491, 
				    "std" => 0.64933570197911 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.995208761122519, 
				    "count" => 1461, 
				    "std" => 0.720976611803773 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD1", 
				    "shift2" => "HA", 
				    "consistency" => 0.983471074380165, 
				    "count" => 121, 
				    "std" => 2.14708328443142 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD2", 
				    "shift2" => "HA", 
				    "consistency" => 0.957427536231884, 
				    "count" => 1104, 
				    "std" => 2.47887545731972 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HE1", 
				    "shift2" => "HA", 
				    "consistency" => 0.95841784989858, 
				    "count" => 986, 
				    "std" => 1.92952437485804 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD1", 
				    "shift2" => "HB2", 
				    "consistency" => 0.975206611570248, 
				    "count" => 121, 
				    "std" => 2.31023842098139 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.97005444646098, 
				    "count" => 1102, 
				    "std" => 2.93101877247117 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HE1", 
				    "shift2" => "HB2", 
				    "consistency" => 0.968527918781726, 
				    "count" => 985, 
				    "std" => 3.73011672315953 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD1", 
				    "shift2" => "HB3", 
				    "consistency" => 0.983050847457627, 
				    "count" => 118, 
				    "std" => 2.37354841182396 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.967123287671233, 
				    "count" => 1095, 
				    "std" => 3.52930844279802 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HE1", 
				    "shift2" => "HB3", 
				    "consistency" => 0.968335035750766, 
				    "count" => 979, 
				    "std" => 4.01208952142945 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HD1", 
				    "shift2" => "HE1", 
				    "consistency" => 0.676470588235294, 
				    "count" => 102, 
				    "std" => 7.01726923893498 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "HE1", 
				    "shift2" => "HD2", 
				    "consistency" => 0.925688073394495, 
				    "count" => 1090, 
				    "std" => 4.0873867485538 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 632, 
				    "std" => 2.03387722785582 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 567, 
				    "std" => 3.18994794378929 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "C", 
				    "shift2" => "CD2", 
				    "consistency" => 1, 
				    "count" => 173, 
				    "std" => 3.34467317444577 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "C", 
				    "shift2" => "CE1", 
				    "consistency" => 1, 
				    "count" => 145, 
				    "std" => 4.09038625459402 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1046, 
				    "std" => 3.47600919644619 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "CD2", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 338, 
				    "std" => 4.97931898196431 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "CE1", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 256, 
				    "std" => 4.15396757458487 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "CD2", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 336, 
				    "std" => 5.08904366363616 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "CE1", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 252, 
				    "std" => 3.59322648797044 };
  
  push @{$$shift_order_rules{H}}, { "shift1" => "CE1", 
				    "shift2" => "CD2", 
				    "consistency" => 0.991666666666667, 
				    "count" => 240, 
				    "std" => 4.61904009234843 };
  
  
#
# Rules for I
#
  $$shift_order_rules{I} = [];
  push @{$$shift_order_rules{I}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 3691, 
				    "std" => 0.753113675023218 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "H", 
				    "shift2" => "HB", 
				    "consistency" => 1, 
				    "count" => 3269, 
				    "std" => 0.753046685159366 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "H", 
				    "shift2" => "HG12", 
				    "consistency" => 1, 
				    "count" => 2763, 
				    "std" => 0.791166737800671 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "H", 
				    "shift2" => "HG13", 
				    "consistency" => 1, 
				    "count" => 2669, 
				    "std" => 0.806268308668247 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 2954, 
				    "std" => 0.737568531078201 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "H", 
				    "shift2" => "HD1", 
				    "consistency" => 0.999647639182523, 
				    "count" => 2838, 
				    "std" => 0.782919932028469 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HA", 
				    "shift2" => "HB", 
				    "consistency" => 0.998207349865551, 
				    "count" => 3347, 
				    "std" => 0.654352529374906 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HA", 
				    "shift2" => "HG12", 
				    "consistency" => 0.998940303779583, 
				    "count" => 2831, 
				    "std" => 0.694041368769399 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HA", 
				    "shift2" => "HG13", 
				    "consistency" => 0.999269005847953, 
				    "count" => 2736, 
				    "std" => 0.699903452319371 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 0.99966766367564, 
				    "count" => 3009, 
				    "std" => 0.606531996378323 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HA", 
				    "shift2" => "HD1", 
				    "consistency" => 0.999654218533887, 
				    "count" => 2892, 
				    "std" => 0.661876162103295 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HB", 
				    "shift2" => "HG12", 
				    "consistency" => 0.910821290095171, 
				    "count" => 2837, 
				    "std" => 0.393421054537535 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HB", 
				    "shift2" => "HG13", 
				    "consistency" => 0.935448577680525, 
				    "count" => 2742, 
				    "std" => 0.40781814136671 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HB", 
				    "shift2" => "HG2", 
				    "consistency" => 0.995042961004627, 
				    "count" => 3026, 
				    "std" => 0.2894411946609 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HB", 
				    "shift2" => "HD1", 
				    "consistency" => 0.994137931034483, 
				    "count" => 2900, 
				    "std" => 0.367134610974851 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HG12", 
				    "shift2" => "HG2", 
				    "consistency" => 0.91520572450805, 
				    "count" => 2795, 
				    "std" => 0.63895865355876 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HG12", 
				    "shift2" => "HD1", 
				    "consistency" => 0.945730824891462, 
				    "count" => 2764, 
				    "std" => 0.649078369394377 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HG13", 
				    "shift2" => "HG2", 
				    "consistency" => 0.878508124076809, 
				    "count" => 2708, 
				    "std" => 0.96050027242168 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HG13", 
				    "shift2" => "HD1", 
				    "consistency" => 0.926382660687593, 
				    "count" => 2676, 
				    "std" => 0.975190434361105 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "HG2", 
				    "shift2" => "HD1", 
				    "consistency" => 0.706206896551724, 
				    "count" => 2900, 
				    "std" => 0.302651587692523 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1656, 
				    "std" => 2.13708045131913 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1492, 
				    "std" => 3.25188299771541 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "C", 
				    "shift2" => "CG1", 
				    "consistency" => 1, 
				    "count" => 954, 
				    "std" => 2.4363624372191 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "C", 
				    "shift2" => "CG2", 
				    "consistency" => 1, 
				    "count" => 1042, 
				    "std" => 2.78812100840679 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "C", 
				    "shift2" => "CD1", 
				    "consistency" => 1, 
				    "count" => 1022, 
				    "std" => 4.40411058394427 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 2424, 
				    "std" => 3.90175307623504 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CA", 
				    "shift2" => "CG1", 
				    "consistency" => 0.998759305210918, 
				    "count" => 1612, 
				    "std" => 4.47668720197062 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CA", 
				    "shift2" => "CG2", 
				    "consistency" => 1, 
				    "count" => 1775, 
				    "std" => 3.32004887923088 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CA", 
				    "shift2" => "CD1", 
				    "consistency" => 0.998828353837141, 
				    "count" => 1707, 
				    "std" => 4.12995152541141 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CB", 
				    "shift2" => "CG1", 
				    "consistency" => 0.995660260384377, 
				    "count" => 1613, 
				    "std" => 4.60186371337017 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CB", 
				    "shift2" => "CG2", 
				    "consistency" => 0.998860398860399, 
				    "count" => 1755, 
				    "std" => 2.59718314428219 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CB", 
				    "shift2" => "CD1", 
				    "consistency" => 0.997048406139315, 
				    "count" => 1694, 
				    "std" => 3.36714093024261 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CG1", 
				    "shift2" => "CG2", 
				    "consistency" => 0.99435736677116, 
				    "count" => 1595, 
				    "std" => 4.51479852397375 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CG1", 
				    "shift2" => "CD1", 
				    "consistency" => 0.993514915693904, 
				    "count" => 1542, 
				    "std" => 5.41497871065412 };
  
  push @{$$shift_order_rules{I}}, { "shift1" => "CG2", 
				    "shift2" => "CD1", 
				    "consistency" => 0.960166468489893, 
				    "count" => 1682, 
				    "std" => 3.17371869633218 };
  
  
#
# Rules for K
#
  $$shift_order_rules{K} = [];
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 5719, 
				    "std" => 0.712069206076222 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 4961, 
				    "std" => 0.688219280685537 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 4680, 
				    "std" => 0.688628317509494 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 3960, 
				    "std" => 0.687467769791283 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 3660, 
				    "std" => 0.683740642866939 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HD2", 
				    "consistency" => 0.999700688416642, 
				    "count" => 3341, 
				    "std" => 2.14264124709177 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 3069, 
				    "std" => 0.656988645097823 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HE2", 
				    "consistency" => 1, 
				    "count" => 3283, 
				    "std" => 0.661242115183176 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HE3", 
				    "consistency" => 1, 
				    "count" => 2997, 
				    "std" => 0.650822623834198 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "H", 
				    "shift2" => "HZ", 
				    "consistency" => 0.952238805970149, 
				    "count" => 335, 
				    "std" => 0.733677651078609 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999415774099318, 
				    "count" => 5135, 
				    "std" => 0.502075435590429 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.999793899422918, 
				    "count" => 4852, 
				    "std" => 0.522415077230379 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 4084, 
				    "std" => 0.488496210387012 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 3772, 
				    "std" => 0.493656426081548 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HD2", 
				    "consistency" => 0.998840243548855, 
				    "count" => 3449, 
				    "std" => 2.07598076900221 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HD3", 
				    "consistency" => 0.999684542586751, 
				    "count" => 3170, 
				    "std" => 0.506444947231313 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HE2", 
				    "consistency" => 0.99351606248158, 
				    "count" => 3393, 
				    "std" => 0.506820642510007 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HA", 
				    "shift2" => "HE3", 
				    "consistency" => 0.993548387096774, 
				    "count" => 3100, 
				    "std" => 0.506296724138893 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HA", 
				    "consistency" => 0.994029850746269, 
				    "count" => 335, 
				    "std" => 0.567431496558179 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.964400494437577, 
				    "count" => 4045, 
				    "std" => 0.259137190384886 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.959870724481551, 
				    "count" => 3713, 
				    "std" => 0.292738862806332 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB2", 
				    "shift2" => "HD2", 
				    "consistency" => 0.841107871720117, 
				    "count" => 3430, 
				    "std" => 2.03733014160821 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB2", 
				    "shift2" => "HD3", 
				    "consistency" => 0.833975594091201, 
				    "count" => 3114, 
				    "std" => 0.293864621229457 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.997029997029997, 
				    "count" => 3367, 
				    "std" => 0.278315687451957 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.99703557312253, 
				    "count" => 3036, 
				    "std" => 0.287398153497569 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 331, 
				    "std" => 0.523037238601536 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.946451780608266, 
				    "count" => 3847, 
				    "std" => 0.276375600257449 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.9589450788472, 
				    "count" => 3678, 
				    "std" => 0.273976201664985 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB3", 
				    "shift2" => "HD2", 
				    "consistency" => 0.8258615431534, 
				    "count" => 3279, 
				    "std" => 2.08309547427564 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HB3", 
				    "shift2" => "HD3", 
				    "consistency" => 0.8384, 
				    "count" => 3125, 
				    "std" => 0.279780333382369 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.995656220912194, 
				    "count" => 3223, 
				    "std" => 0.286269840058826 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE3", 
				    "shift2" => "HB3", 
				    "consistency" => 0.997380484610347, 
				    "count" => 3054, 
				    "std" => 0.279088948276257 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 331, 
				    "std" => 0.527417860735958 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HD2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.903282532239156, 
				    "count" => 3412, 
				    "std" => 0.29072988508549 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HD3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.90217039196631, 
				    "count" => 3087, 
				    "std" => 0.279007137471933 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.998788612961841, 
				    "count" => 3302, 
				    "std" => 0.250009285150165 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.999326372515999, 
				    "count" => 2969, 
				    "std" => 0.260354829098087 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 329, 
				    "std" => 0.531113413661971 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HD2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.912053147738058, 
				    "count" => 3161, 
				    "std" => 2.12066043428996 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HD3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.911659629749919, 
				    "count" => 3079, 
				    "std" => 0.281181186182438 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.998688524590164, 
				    "count" => 3050, 
				    "std" => 0.26940008444895 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.999328182734296, 
				    "count" => 2977, 
				    "std" => 0.260252074010115 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 319, 
				    "std" => 0.466157879604841 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE2", 
				    "shift2" => "HD2", 
				    "consistency" => 0.998085513720485, 
				    "count" => 3134, 
				    "std" => 2.12323152209481 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE3", 
				    "shift2" => "HD2", 
				    "consistency" => 0.998931243320271, 
				    "count" => 2807, 
				    "std" => 2.23939491940407 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 329, 
				    "std" => 0.499473652889152 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE2", 
				    "shift2" => "HD3", 
				    "consistency" => 0.99894142554693, 
				    "count" => 2834, 
				    "std" => 0.22052107947236 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HE3", 
				    "shift2" => "HD3", 
				    "consistency" => 0.998948106591865, 
				    "count" => 2852, 
				    "std" => 0.206880793934599 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 311, 
				    "std" => 0.420844828660246 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HE2", 
				    "consistency" => 1, 
				    "count" => 336, 
				    "std" => 0.417230520420552 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "HZ", 
				    "shift2" => "HE3", 
				    "consistency" => 1, 
				    "count" => 314, 
				    "std" => 0.420594526699998 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 2407, 
				    "std" => 1.79884550372074 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 2179, 
				    "std" => 3.06198848564872 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 1302, 
				    "std" => 2.49949782777481 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "C", 
				    "shift2" => "CD", 
				    "consistency" => 1, 
				    "count" => 1216, 
				    "std" => 2.41936549449107 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "C", 
				    "shift2" => "CE", 
				    "consistency" => 1, 
				    "count" => 1143, 
				    "std" => 2.16811832755131 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 3508, 
				    "std" => 3.27454228832946 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 2175, 
				    "std" => 2.75086576549611 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CA", 
				    "shift2" => "CD", 
				    "consistency" => 0.999509563511525, 
				    "count" => 2039, 
				    "std" => 2.52138258974845 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CA", 
				    "shift2" => "CE", 
				    "consistency" => 0.999493414387031, 
				    "count" => 1974, 
				    "std" => 2.43606615533153 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CB", 
				    "shift2" => "CG", 
				    "consistency" => 0.996318453750575, 
				    "count" => 2173, 
				    "std" => 2.45999488465548 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CB", 
				    "shift2" => "CD", 
				    "consistency" => 0.980891719745223, 
				    "count" => 2041, 
				    "std" => 2.03611675722159 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CE", 
				    "shift2" => "CB", 
				    "consistency" => 0.998982706002035, 
				    "count" => 1966, 
				    "std" => 1.77872560082655 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CD", 
				    "shift2" => "CG", 
				    "consistency" => 0.966067864271457, 
				    "count" => 2004, 
				    "std" => 2.39906527660276 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CE", 
				    "shift2" => "CG", 
				    "consistency" => 0.996856993190152, 
				    "count" => 1909, 
				    "std" => 2.14531454069688 };
  
  push @{$$shift_order_rules{K}}, { "shift1" => "CE", 
				    "shift2" => "CD", 
				    "consistency" => 0.998389694041868, 
				    "count" => 1863, 
				    "std" => 1.65512698633601 };
  
  
#
# Rules for L
#
  $$shift_order_rules{L} = [];
  push @{$$shift_order_rules{L}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.999833914632121, 
				    "count" => 6021, 
				    "std" => 0.698930330385903 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 5198, 
				    "std" => 0.733474859773715 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 5013, 
				    "std" => 0.742672803967285 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "H", 
				    "shift2" => "HG", 
				    "consistency" => 1, 
				    "count" => 4510, 
				    "std" => 0.724445228118439 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "H", 
				    "shift2" => "HD1", 
				    "consistency" => 1, 
				    "count" => 4772, 
				    "std" => 0.725164001878284 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "H", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 4642, 
				    "std" => 0.737331889751697 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999623352165725, 
				    "count" => 5310, 
				    "std" => 0.581951348763225 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.9998046875, 
				    "count" => 5120, 
				    "std" => 0.593383583366785 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HA", 
				    "shift2" => "HG", 
				    "consistency" => 1, 
				    "count" => 4607, 
				    "std" => 0.572891737348684 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HA", 
				    "shift2" => "HD1", 
				    "consistency" => 0.999172699069286, 
				    "count" => 4835, 
				    "std" => 0.549086546872021 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HA", 
				    "shift2" => "HD2", 
				    "consistency" => 0.999363192528126, 
				    "count" => 4711, 
				    "std" => 0.559415055344701 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HB2", 
				    "shift2" => "HG", 
				    "consistency" => 0.595495694413778, 
				    "count" => 4529, 
				    "std" => 0.37408535132222 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HB2", 
				    "shift2" => "HD1", 
				    "consistency" => 0.987928843710292, 
				    "count" => 4722, 
				    "std" => 0.382593909300048 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HB2", 
				    "shift2" => "HD2", 
				    "consistency" => 0.988309157826369, 
				    "count" => 4619, 
				    "std" => 0.410518610290053 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HB3", 
				    "shift2" => "HG", 
				    "consistency" => 0.519601178336732, 
				    "count" => 4413, 
				    "std" => 0.393921500951474 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HB3", 
				    "shift2" => "HD1", 
				    "consistency" => 0.97950730324831, 
				    "count" => 4587, 
				    "std" => 0.405852700285938 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HB3", 
				    "shift2" => "HD2", 
				    "consistency" => 0.981785872945358, 
				    "count" => 4502, 
				    "std" => 0.393533842324241 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HG", 
				    "shift2" => "HD1", 
				    "consistency" => 0.983058210251955, 
				    "count" => 4604, 
				    "std" => 0.339694996886416 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "HG", 
				    "shift2" => "HD2", 
				    "consistency" => 0.981705973109985, 
				    "count" => 4537, 
				    "std" => 0.360115058436975 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 2649, 
				    "std" => 1.79600726788614 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 2403, 
				    "std" => 3.15489744081343 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 1512, 
				    "std" => 2.60601057364527 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "C", 
				    "shift2" => "CD1", 
				    "consistency" => 1, 
				    "count" => 1674, 
				    "std" => 2.67027402888796 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "C", 
				    "shift2" => "CD2", 
				    "consistency" => 1, 
				    "count" => 1614, 
				    "std" => 2.99629417273385 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.999742135121196, 
				    "count" => 3878, 
				    "std" => 3.36660566831512 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 0.99959595959596, 
				    "count" => 2475, 
				    "std" => 2.58501060116174 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CA", 
				    "shift2" => "CD1", 
				    "consistency" => 0.999638074556641, 
				    "count" => 2763, 
				    "std" => 2.77720455673749 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CA", 
				    "shift2" => "CD2", 
				    "consistency" => 0.999623210248681, 
				    "count" => 2654, 
				    "std" => 2.83232967783062 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CB", 
				    "shift2" => "CG", 
				    "consistency" => 0.997556008146639, 
				    "count" => 2455, 
				    "std" => 2.38574553322618 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CB", 
				    "shift2" => "CD1", 
				    "consistency" => 0.999257884972171, 
				    "count" => 2695, 
				    "std" => 2.45376205186771 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CB", 
				    "shift2" => "CD2", 
				    "consistency" => 0.999613750482812, 
				    "count" => 2589, 
				    "std" => 2.32386767277296 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CG", 
				    "shift2" => "CD1", 
				    "consistency" => 0.877677100494234, 
				    "count" => 2428, 
				    "std" => 1.91283159300792 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CG", 
				    "shift2" => "CD2", 
				    "consistency" => 0.919045590115041, 
				    "count" => 2347, 
				    "std" => 2.04317074347821 };
  
  push @{$$shift_order_rules{L}}, { "shift1" => "CD1", 
				    "shift2" => "CD2", 
				    "consistency" => 0.583271375464684, 
				    "count" => 2690, 
				    "std" => 2.53050002256713 };
  
  
#
# Rules for M
#
  $$shift_order_rules{M} = [];
  push @{$$shift_order_rules{M}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 1451, 
				    "std" => 0.675756430150988 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 0.995819397993311, 
				    "count" => 1196, 
				    "std" => 0.904884025986793 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 0.99649430324277, 
				    "count" => 1141, 
				    "std" => 0.878410558496087 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 1022, 
				    "std" => 2.18429535171382 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "H", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 984, 
				    "std" => 1.96898988167294 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "H", 
				    "shift2" => "HE", 
				    "consistency" => 1, 
				    "count" => 725, 
				    "std" => 2.33303906791528 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.996937212863706, 
				    "count" => 1306, 
				    "std" => 0.904207769922165 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.997596153846154, 
				    "count" => 1248, 
				    "std" => 0.8332778206097 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 0.998212689901698, 
				    "count" => 1119, 
				    "std" => 1.90186783756304 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HA", 
				    "shift2" => "HG3", 
				    "consistency" => 0.999074074074074, 
				    "count" => 1080, 
				    "std" => 1.70858087391686 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HA", 
				    "shift2" => "HE", 
				    "consistency" => 1, 
				    "count" => 776, 
				    "std" => 1.87355657406904 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HG2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.879496402877698, 
				    "count" => 1112, 
				    "std" => 2.88106467776008 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HG3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.85941893158388, 
				    "count" => 1067, 
				    "std" => 2.64564944300602 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HB2", 
				    "shift2" => "HE", 
				    "consistency" => 0.60625814863103, 
				    "count" => 767, 
				    "std" => 3.25938299608104 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HG2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.878163074039363, 
				    "count" => 1067, 
				    "std" => 2.62821580748667 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HG3", 
				    "shift2" => "HB3", 
				    "consistency" => 0.876893939393939, 
				    "count" => 1056, 
				    "std" => 2.64245345112425 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HB3", 
				    "shift2" => "HE", 
				    "consistency" => 0.612732095490716, 
				    "count" => 754, 
				    "std" => 3.01932595466668 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HG2", 
				    "shift2" => "HE", 
				    "consistency" => 0.920765027322404, 
				    "count" => 732, 
				    "std" => 3.74865934586646 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "HG3", 
				    "shift2" => "HE", 
				    "consistency" => 0.892351274787535, 
				    "count" => 706, 
				    "std" => 3.89872310278639 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 685, 
				    "std" => 2.13416436931906 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 608, 
				    "std" => 3.74605163486089 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 366, 
				    "std" => 2.81528165254199 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "C", 
				    "shift2" => "CE", 
				    "consistency" => 1, 
				    "count" => 261, 
				    "std" => 3.68887905633596 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1028, 
				    "std" => 3.50486781160474 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 653, 
				    "std" => 2.81665307768114 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "CA", 
				    "shift2" => "CE", 
				    "consistency" => 1, 
				    "count" => 472, 
				    "std" => 4.42582421948285 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "CB", 
				    "shift2" => "CG", 
				    "consistency" => 0.618604651162791, 
				    "count" => 645, 
				    "std" => 2.85794743145334 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "CB", 
				    "shift2" => "CE", 
				    "consistency" => 0.98471615720524, 
				    "count" => 458, 
				    "std" => 4.2936881724606 };
  
  push @{$$shift_order_rules{M}}, { "shift1" => "CG", 
				    "shift2" => "CE", 
				    "consistency" => 0.976525821596244, 
				    "count" => 426, 
				    "std" => 4.2465189770482 };
  
  
#
# Rules for N
#
  $$shift_order_rules{N} = [];
  push @{$$shift_order_rules{N}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 3264, 
				    "std" => 0.751612273850133 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2917, 
				    "std" => 0.739133290118328 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 2846, 
				    "std" => 0.742313858800344 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "H", 
				    "shift2" => "HD21", 
				    "consistency" => 0.90547263681592, 
				    "count" => 2010, 
				    "std" => 0.860518346307855 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "H", 
				    "shift2" => "HD22", 
				    "consistency" => 0.936658354114713, 
				    "count" => 2005, 
				    "std" => 0.81808777802874 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 3011, 
				    "std" => 0.493451202924912 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 2936, 
				    "std" => 0.497559844587794 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HD21", 
				    "shift2" => "HA", 
				    "consistency" => 0.996566944580677, 
				    "count" => 2039, 
				    "std" => 0.658632158316743 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HD22", 
				    "shift2" => "HA", 
				    "consistency" => 0.996558505408063, 
				    "count" => 2034, 
				    "std" => 0.62342928279414 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HD21", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2040, 
				    "std" => 0.577869218435665 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HD22", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2035, 
				    "std" => 0.621078692488698 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HD21", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1996, 
				    "std" => 0.638356925071516 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "HD22", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1993, 
				    "std" => 0.548285242720604 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1353, 
				    "std" => 1.8443606822454 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1186, 
				    "std" => 2.68477582148664 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "CG", 
				    "shift2" => "C", 
				    "consistency" => 0.747619047619048, 
				    "count" => 210, 
				    "std" => 2.16902441422431 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.999500748876685, 
				    "count" => 2003, 
				    "std" => 2.66635882932153 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "CG", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 208, 
				    "std" => 2.16939166184538 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "CG", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 213, 
				    "std" => 2.20424397946201 };
  
  push @{$$shift_order_rules{N}}, { "shift1" => "N", 
				    "shift2" => "ND2", 
				    "consistency" => 0.895087427144047, 
				    "count" => 1201, 
				    "std" => 5.94938531835627 };
  
  
#
# Rules for P
#
  $$shift_order_rules{P} = [];
  push @{$$shift_order_rules{P}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2705, 
				    "std" => 0.432317636566943 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.99961788307222, 
				    "count" => 2617, 
				    "std" => 0.42899869044683 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 2332, 
				    "std" => 0.44104747925117 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HA", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 2187, 
				    "std" => 0.450800027815802 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HA", 
				    "shift2" => "HD2", 
				    "consistency" => 0.957236842105263, 
				    "count" => 2432, 
				    "std" => 0.517144161689974 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HA", 
				    "shift2" => "HD3", 
				    "consistency" => 0.96988973706531, 
				    "count" => 2358, 
				    "std" => 0.489022650473252 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HB2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.651670951156812, 
				    "count" => 2334, 
				    "std" => 0.38844039227333 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HB2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.640931932389219, 
				    "count" => 2189, 
				    "std" => 0.443350321313263 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.987468671679198, 
				    "count" => 2394, 
				    "std" => 0.512477847072715 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.984058595433003, 
				    "count" => 2321, 
				    "std" => 0.558363103776545 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HB3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.5844327176781, 
				    "count" => 2274, 
				    "std" => 0.437530834207451 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HB3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.622693726937269, 
				    "count" => 2168, 
				    "std" => 0.413814587545332 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.98932536293766, 
				    "count" => 2342, 
				    "std" => 0.576245061042144 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD3", 
				    "shift2" => "HB3", 
				    "consistency" => 0.989492119089317, 
				    "count" => 2284, 
				    "std" => 0.490558193909302 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.993449781659389, 
				    "count" => 2290, 
				    "std" => 0.431639024631681 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.992802519118309, 
				    "count" => 2223, 
				    "std" => 0.451520305892276 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.994893221912721, 
				    "count" => 2154, 
				    "std" => 0.480049478523152 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "HD3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.995296331138288, 
				    "count" => 2126, 
				    "std" => 0.416382461735028 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1194, 
				    "std" => 2.04610282841533 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1051, 
				    "std" => 2.39733101528977 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 636, 
				    "std" => 1.69355178472887 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "C", 
				    "shift2" => "CD", 
				    "consistency" => 1, 
				    "count" => 659, 
				    "std" => 2.15491604574802 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.998920669185105, 
				    "count" => 1853, 
				    "std" => 2.68882129273261 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 1181, 
				    "std" => 2.17633538903075 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "CA", 
				    "shift2" => "CD", 
				    "consistency" => 0.997572815533981, 
				    "count" => 1236, 
				    "std" => 2.36558791195851 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "CB", 
				    "shift2" => "CG", 
				    "consistency" => 0.993121238177128, 
				    "count" => 1163, 
				    "std" => 1.80384712356453 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "CD", 
				    "shift2" => "CB", 
				    "consistency" => 0.999167360532889, 
				    "count" => 1201, 
				    "std" => 1.62248722422982 };
  
  push @{$$shift_order_rules{P}}, { "shift1" => "CD", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 1139, 
				    "std" => 1.41986651171752 };
  
  
#
# Rules for Q
#
  $$shift_order_rules{Q} = [];
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 3007, 
				    "std" => 0.698603418311786 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2573, 
				    "std" => 0.686784336754559 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 0.999593330622204, 
				    "count" => 2459, 
				    "std" => 0.79054113703079 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 2291, 
				    "std" => 0.690285251920318 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 2147, 
				    "std" => 0.698986569577901 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HE21", 
				    "consistency" => 0.927218934911243, 
				    "count" => 1690, 
				    "std" => 0.769356480209242 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "H", 
				    "shift2" => "HE22", 
				    "consistency" => 0.952550415183867, 
				    "count" => 1686, 
				    "std" => 0.771805425416666 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.999621785173979, 
				    "count" => 2644, 
				    "std" => 0.534693411716358 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.999209798498617, 
				    "count" => 2531, 
				    "std" => 0.658001180004944 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 2355, 
				    "std" => 0.525147539535889 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HA", 
				    "shift2" => "HG3", 
				    "consistency" => 0.999546896239239, 
				    "count" => 2207, 
				    "std" => 0.535298461646545 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE21", 
				    "shift2" => "HA", 
				    "consistency" => 0.998812351543943, 
				    "count" => 1684, 
				    "std" => 0.648362316008149 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE22", 
				    "shift2" => "HA", 
				    "consistency" => 0.997619047619048, 
				    "count" => 1680, 
				    "std" => 0.642873789017022 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HG2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.89943892965041, 
				    "count" => 2317, 
				    "std" => 0.291577100254782 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HG3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.88294930875576, 
				    "count" => 2170, 
				    "std" => 0.340507915029536 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE21", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1658, 
				    "std" => 0.51506636583975 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE22", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1656, 
				    "std" => 0.528823760984784 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HG2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.900089605734767, 
				    "count" => 2232, 
				    "std" => 0.518299040234022 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HG3", 
				    "shift2" => "HB3", 
				    "consistency" => 0.89747191011236, 
				    "count" => 2136, 
				    "std" => 0.317052455014399 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE21", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1608, 
				    "std" => 0.565718772250498 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE22", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1606, 
				    "std" => 0.511053860074915 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE21", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 1620, 
				    "std" => 0.50680445613393 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE22", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 1618, 
				    "std" => 0.510598097990045 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE21", 
				    "shift2" => "HG3", 
				    "consistency" => 0.999354422207876, 
				    "count" => 1549, 
				    "std" => 0.579008242944612 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "HE22", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 1547, 
				    "std" => 0.488667933956263 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1310, 
				    "std" => 1.62093943417529 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1174, 
				    "std" => 3.21630950686512 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 776, 
				    "std" => 2.0279288921978 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CD", 
				    "shift2" => "C", 
				    "consistency" => 0.961325966850829, 
				    "count" => 181, 
				    "std" => 2.24884521347646 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1961, 
				    "std" => 3.43869849620684 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 1340, 
				    "std" => 2.17518438042426 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CD", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 188, 
				    "std" => 5.51998508643448 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CG", 
				    "shift2" => "CB", 
				    "consistency" => 0.984210526315789, 
				    "count" => 1330, 
				    "std" => 1.87222718887397 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CD", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 192, 
				    "std" => 5.46066398080865 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "CD", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 184, 
				    "std" => 5.26728082401487 };
  
  push @{$$shift_order_rules{Q}}, { "shift1" => "N", 
				    "shift2" => "NE2", 
				    "consistency" => 0.978279756733275, 
				    "count" => 1151, 
				    "std" => 5.04103013194974 };
  
  
#
# Rules for R
#
  $$shift_order_rules{R} = [];
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.999440246291632, 
				    "count" => 3573, 
				    "std" => 0.678416715372098 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 3085, 
				    "std" => 0.644453787950207 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 2910, 
				    "std" => 0.633355112637706 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 2607, 
				    "std" => 0.634483697562588 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 2442, 
				    "std" => 0.622054690358787 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 2547, 
				    "std" => 0.608213721810381 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 2375, 
				    "std" => 0.606421541949427 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HE", 
				    "consistency" => 0.916047548291233, 
				    "count" => 1346, 
				    "std" => 0.815138037966301 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HH11", 
				    "consistency" => 0.982352941176471, 
				    "count" => 170, 
				    "std" => 0.575815723959043 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HH12", 
				    "consistency" => 0.979591836734694, 
				    "count" => 147, 
				    "std" => 0.561775994947485 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HH21", 
				    "consistency" => 0.973684210526316, 
				    "count" => 152, 
				    "std" => 0.533162369441398 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "H", 
				    "shift2" => "HH22", 
				    "consistency" => 0.971428571428571, 
				    "count" => 140, 
				    "std" => 0.565989259651468 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.99936768890294, 
				    "count" => 3163, 
				    "std" => 0.568555726603457 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 2984, 
				    "std" => 0.559702055132492 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 2669, 
				    "std" => 0.505074268545476 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HA", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 2497, 
				    "std" => 0.520250018132896 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HA", 
				    "shift2" => "HD2", 
				    "consistency" => 0.991153846153846, 
				    "count" => 2600, 
				    "std" => 0.507197202096849 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HA", 
				    "shift2" => "HD3", 
				    "consistency" => 0.989673688558447, 
				    "count" => 2421, 
				    "std" => 0.50906463036282 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HA", 
				    "consistency" => 0.991111111111111, 
				    "count" => 1350, 
				    "std" => 0.766518304375081 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 168, 
				    "std" => 0.557495224061328 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 145, 
				    "std" => 0.539370155603962 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 150, 
				    "std" => 0.502232442024828 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 138, 
				    "std" => 0.523645324836843 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HB2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.881158330199323, 
				    "count" => 2659, 
				    "std" => 0.28486537812992 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HB2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.87233185662505, 
				    "count" => 2483, 
				    "std" => 0.324941273304702 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD2", 
				    "shift2" => "HB2", 
				    "consistency" => 0.994969040247678, 
				    "count" => 2584, 
				    "std" => 0.294409785068796 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.994991652754591, 
				    "count" => 2396, 
				    "std" => 0.317543095186045 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1338, 
				    "std" => 0.691012885210347 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 168, 
				    "std" => 0.470951423958715 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 145, 
				    "std" => 0.494151708256573 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 150, 
				    "std" => 0.507415147192119 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 138, 
				    "std" => 0.515559905564409 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HB3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.85996835443038, 
				    "count" => 2528, 
				    "std" => 0.293332827858943 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HB3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.880327868852459, 
				    "count" => 2440, 
				    "std" => 0.300856263043003 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD2", 
				    "shift2" => "HB3", 
				    "consistency" => 0.995112016293279, 
				    "count" => 2455, 
				    "std" => 0.30698167083552 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD3", 
				    "shift2" => "HB3", 
				    "consistency" => 0.995794785534062, 
				    "count" => 2378, 
				    "std" => 0.284961086324883 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1290, 
				    "std" => 0.682735356388041 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 164, 
				    "std" => 0.421335745037261 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 145, 
				    "std" => 0.431885494469237 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 150, 
				    "std" => 0.468663404445735 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 138, 
				    "std" => 0.489105247445972 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD2", 
				    "shift2" => "HG2", 
				    "consistency" => 0.997606701236538, 
				    "count" => 2507, 
				    "std" => 0.25753243968998 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD3", 
				    "shift2" => "HG2", 
				    "consistency" => 0.997402597402597, 
				    "count" => 2310, 
				    "std" => 0.275537539357286 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 1296, 
				    "std" => 0.654869175702432 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 164, 
				    "std" => 0.464023195529054 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 141, 
				    "std" => 0.484358234627778 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 145, 
				    "std" => 0.46870596062644 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 133, 
				    "std" => 0.485419899847384 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD2", 
				    "shift2" => "HG3", 
				    "consistency" => 0.998289867464728, 
				    "count" => 2339, 
				    "std" => 0.283509690077233 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HD3", 
				    "shift2" => "HG3", 
				    "consistency" => 0.998244844229925, 
				    "count" => 2279, 
				    "std" => 0.267820044560974 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 1241, 
				    "std" => 0.608365684820019 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 157, 
				    "std" => 0.51553135614778 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 136, 
				    "std" => 0.501846243148779 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 144, 
				    "std" => 0.525338065711127 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HG3", 
				    "consistency" => 1, 
				    "count" => 133, 
				    "std" => 0.542136803854437 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HD2", 
				    "consistency" => 0.999241849886278, 
				    "count" => 1319, 
				    "std" => 0.56022867395693 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 168, 
				    "std" => 0.449326905901869 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 145, 
				    "std" => 0.48055485004328 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 150, 
				    "std" => 0.472733281624592 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HD2", 
				    "consistency" => 1, 
				    "count" => 138, 
				    "std" => 0.50015013666923 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HD3", 
				    "consistency" => 0.999210110584518, 
				    "count" => 1266, 
				    "std" => 0.553353041385172 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH11", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 163, 
				    "std" => 0.444133614009601 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH12", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 144, 
				    "std" => 0.459265582207071 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH21", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 149, 
				    "std" => 0.452083102305846 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HH22", 
				    "shift2" => "HD3", 
				    "consistency" => 1, 
				    "count" => 137, 
				    "std" => 0.477167516751825 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HH11", 
				    "consistency" => 0.954838709677419, 
				    "count" => 155, 
				    "std" => 0.706313933144466 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HH12", 
				    "consistency" => 0.948529411764706, 
				    "count" => 136, 
				    "std" => 0.741242495272057 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HH21", 
				    "consistency" => 0.957142857142857, 
				    "count" => 140, 
				    "std" => 0.641671320435461 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "HE", 
				    "shift2" => "HH22", 
				    "consistency" => 0.953125, 
				    "count" => 128, 
				    "std" => 0.673084370146817 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1448, 
				    "std" => 1.81067133301315 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1290, 
				    "std" => 3.15410820635075 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "C", 
				    "shift2" => "CG", 
				    "consistency" => 1, 
				    "count" => 781, 
				    "std" => 2.78447150738655 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "C", 
				    "shift2" => "CD", 
				    "consistency" => 1, 
				    "count" => 805, 
				    "std" => 2.38954186262406 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.99954954954955, 
				    "count" => 2220, 
				    "std" => 3.51221949233255 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "CA", 
				    "shift2" => "CG", 
				    "consistency" => 0.999257609502598, 
				    "count" => 1347, 
				    "std" => 2.62196697730017 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "CA", 
				    "shift2" => "CD", 
				    "consistency" => 1, 
				    "count" => 1405, 
				    "std" => 2.41328414920012 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "CB", 
				    "shift2" => "CG", 
				    "consistency" => 0.953194650817236, 
				    "count" => 1346, 
				    "std" => 2.74725057284614 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "CD", 
				    "shift2" => "CB", 
				    "consistency" => 0.997838616714697, 
				    "count" => 1388, 
				    "std" => 1.84919009930556 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "CD", 
				    "shift2" => "CG", 
				    "consistency" => 0.998466257668712, 
				    "count" => 1304, 
				    "std" => 1.89367248601622 };
  
  push @{$$shift_order_rules{R}}, { "shift1" => "N", 
				    "shift2" => "NE", 
				    "consistency" => 0.952471482889734, 
				    "count" => 526, 
				    "std" => 14.6816681719479 };
  
  
#
# Rules for S
#
  $$shift_order_rules{S} = [];
  push @{$$shift_order_rules{S}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.99955859633635, 
				    "count" => 4531, 
				    "std" => 0.711217389922311 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 3947, 
				    "std" => 0.665460390783519 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 3744, 
				    "std" => 0.674272998732922 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.953204971971728, 
				    "count" => 4103, 
				    "std" => 0.507775529972216 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.95606372045221, 
				    "count" => 3892, 
				    "std" => 0.526314287123519 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1927, 
				    "std" => 2.03948886190289 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1681, 
				    "std" => 3.20707056057245 };
  
  push @{$$shift_order_rules{S}}, { "shift1" => "CB", 
				    "shift2" => "CA", 
				    "consistency" => 0.97432239657632, 
				    "count" => 2804, 
				    "std" => 3.42920444404991 };
  
  
#
# Rules for T
#
  $$shift_order_rules{T} = [];
  push @{$$shift_order_rules{T}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 4260, 
				    "std" => 0.709525179760056 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "H", 
				    "shift2" => "HB", 
				    "consistency" => 0.9994617868676, 
				    "count" => 3716, 
				    "std" => 1.64310304656737 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "H", 
				    "shift2" => "HG1", 
				    "consistency" => 0.963730569948187, 
				    "count" => 193, 
				    "std" => 1.88304152346607 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 3597, 
				    "std" => 0.663272021951951 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "HA", 
				    "shift2" => "HB", 
				    "consistency" => 0.660431280852169, 
				    "count" => 3849, 
				    "std" => 1.60683503720885 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "HG1", 
				    "shift2" => "HA", 
				    "consistency" => 0.794871794871795, 
				    "count" => 195, 
				    "std" => 1.96559619182649 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 3727, 
				    "std" => 0.547815804396593 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "HG1", 
				    "shift2" => "HB", 
				    "consistency" => 0.81025641025641, 
				    "count" => 195, 
				    "std" => 1.90799778861015 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "HB", 
				    "shift2" => "HG2", 
				    "consistency" => 0.999457406402604, 
				    "count" => 3686, 
				    "std" => 1.54019425292216 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "HG1", 
				    "shift2" => "HG2", 
				    "consistency" => 0.917127071823204, 
				    "count" => 181, 
				    "std" => 1.67179590354663 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 1759, 
				    "std" => 2.40750217837479 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1508, 
				    "std" => 3.7267703331952 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "C", 
				    "shift2" => "CG2", 
				    "consistency" => 1, 
				    "count" => 1041, 
				    "std" => 2.43727622680169 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "CB", 
				    "shift2" => "CA", 
				    "consistency" => 0.974576271186441, 
				    "count" => 2596, 
				    "std" => 4.53947489214787 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "CA", 
				    "shift2" => "CG2", 
				    "consistency" => 0.999449642267474, 
				    "count" => 1817, 
				    "std" => 3.05095095983498 };
  
  push @{$$shift_order_rules{T}}, { "shift1" => "CB", 
				    "shift2" => "CG2", 
				    "consistency" => 1, 
				    "count" => 1807, 
				    "std" => 2.64987505951304 };
  
  
#
# Rules for V
#
  $$shift_order_rules{V} = [];
  push @{$$shift_order_rules{V}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 0.99979512395001, 
				    "count" => 4881, 
				    "std" => 0.761808568246514 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "H", 
				    "shift2" => "HB", 
				    "consistency" => 0.999540546749368, 
				    "count" => 4353, 
				    "std" => 0.877942983055892 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "H", 
				    "shift2" => "HG1", 
				    "consistency" => 1, 
				    "count" => 4133, 
				    "std" => 0.74082338109585 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "H", 
				    "shift2" => "HG2", 
				    "consistency" => 1, 
				    "count" => 4000, 
				    "std" => 0.756275175471404 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "HA", 
				    "shift2" => "HB", 
				    "consistency" => 0.999553969669938, 
				    "count" => 4484, 
				    "std" => 0.809563762330052 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "HA", 
				    "shift2" => "HG1", 
				    "consistency" => 0.999527967901817, 
				    "count" => 4237, 
				    "std" => 0.646576071915057 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "HA", 
				    "shift2" => "HG2", 
				    "consistency" => 0.999512551791372, 
				    "count" => 4103, 
				    "std" => 0.66920980028766 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "HB", 
				    "shift2" => "HG1", 
				    "consistency" => 0.991770514930637, 
				    "count" => 4253, 
				    "std" => 0.319362877008499 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "HB", 
				    "shift2" => "HG2", 
				    "consistency" => 0.992725509214355, 
				    "count" => 4124, 
				    "std" => 0.327117516899001 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 2112, 
				    "std" => 2.16620640530046 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 1867, 
				    "std" => 3.14334921884835 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "C", 
				    "shift2" => "CG1", 
				    "consistency" => 1, 
				    "count" => 1363, 
				    "std" => 2.15844052834828 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "C", 
				    "shift2" => "CG2", 
				    "consistency" => 1, 
				    "count" => 1278, 
				    "std" => 2.04068689890821 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.999680511182109, 
				    "count" => 3130, 
				    "std" => 4.26582937192897 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "CA", 
				    "shift2" => "CG1", 
				    "consistency" => 0.999566348655681, 
				    "count" => 2306, 
				    "std" => 3.578287324245 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "CA", 
				    "shift2" => "CG2", 
				    "consistency" => 1, 
				    "count" => 2165, 
				    "std" => 2.58983428573091 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "CB", 
				    "shift2" => "CG1", 
				    "consistency" => 0.998683055311677, 
				    "count" => 2278, 
				    "std" => 3.20863270743525 };
  
  push @{$$shift_order_rules{V}}, { "shift1" => "CB", 
				    "shift2" => "CG2", 
				    "consistency" => 0.999532710280374, 
				    "count" => 2140, 
				    "std" => 2.71731044009031 };
  
  
#
# Rules for W
#
  $$shift_order_rules{W} = [];
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 924, 
				    "std" => 0.815632669984783 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 836, 
				    "std" => 0.832039781612005 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 811, 
				    "std" => 0.845353774743643 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HD1", 
				    "consistency" => 0.909352517985612, 
				    "count" => 695, 
				    "std" => 0.863893860868061 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "H", 
				    "consistency" => 0.948644793152639, 
				    "count" => 701, 
				    "std" => 1.02616247820953 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HE3", 
				    "consistency" => 0.868300153139357, 
				    "count" => 653, 
				    "std" => 0.928505843299441 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HZ2", 
				    "consistency" => 0.883755588673621, 
				    "count" => 671, 
				    "std" => 0.891876282261803 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HZ3", 
				    "consistency" => 0.936808846761453, 
				    "count" => 633, 
				    "std" => 0.947591290941819 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "H", 
				    "shift2" => "HH2", 
				    "consistency" => 0.9140625, 
				    "count" => 640, 
				    "std" => 0.948216787593956 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.994219653179191, 
				    "count" => 865, 
				    "std" => 0.656650534705795 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.996420047732697, 
				    "count" => 838, 
				    "std" => 0.659612393426908 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HD1", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 714, 
				    "std" => 0.64285020488167 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 697, 
				    "std" => 0.920574468837783 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 681, 
				    "std" => 0.720832766196173 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ2", 
				    "shift2" => "HA", 
				    "consistency" => 0.998550724637681, 
				    "count" => 690, 
				    "std" => 0.676430982034753 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ3", 
				    "shift2" => "HA", 
				    "consistency" => 0.978755690440061, 
				    "count" => 659, 
				    "std" => 0.734055790391749 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HH2", 
				    "shift2" => "HA", 
				    "consistency" => 0.981954887218045, 
				    "count" => 665, 
				    "std" => 0.750372499636305 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HB3", 
				    "shift2" => "HB2", 
				    "consistency" => 0.501762632197415, 
				    "count" => 851, 
				    "std" => 0.38133133361511 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HD1", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 708, 
				    "std" => 0.419569005645651 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 685, 
				    "std" => 0.745163849836733 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 677, 
				    "std" => 0.52954488600396 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ2", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 687, 
				    "std" => 0.497159622386909 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ3", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 655, 
				    "std" => 0.551972769669604 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HH2", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 664, 
				    "std" => 0.563109600397457 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HD1", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 695, 
				    "std" => 0.408264606253976 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 671, 
				    "std" => 0.761116768943566 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 666, 
				    "std" => 0.50392963352073 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ2", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 677, 
				    "std" => 0.487964769151475 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ3", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 645, 
				    "std" => 0.557546641594125 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HH2", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 655, 
				    "std" => 0.582564653068293 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HD1", 
				    "consistency" => 0.993006993006993, 
				    "count" => 715, 
				    "std" => 0.683991910752278 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HD1", 
				    "consistency" => 0.73582295988935, 
				    "count" => 723, 
				    "std" => 0.488236449669713 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ2", 
				    "shift2" => "HD1", 
				    "consistency" => 0.767160161507402, 
				    "count" => 743, 
				    "std" => 0.433539153423953 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HD1", 
				    "shift2" => "HZ3", 
				    "consistency" => 0.757790368271955, 
				    "count" => 706, 
				    "std" => 0.530608880246586 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HD1", 
				    "shift2" => "HH2", 
				    "consistency" => 0.629943502824859, 
				    "count" => 708, 
				    "std" => 0.541823105828012 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HE3", 
				    "consistency" => 0.986526946107784, 
				    "count" => 668, 
				    "std" => 0.807492016137263 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HZ2", 
				    "consistency" => 0.989766081871345, 
				    "count" => 684, 
				    "std" => 0.658146560198166 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HZ3", 
				    "consistency" => 0.992378048780488, 
				    "count" => 656, 
				    "std" => 0.740841064340894 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE1", 
				    "shift2" => "HH2", 
				    "consistency" => 0.987730061349693, 
				    "count" => 652, 
				    "std" => 0.806427497062016 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HZ2", 
				    "consistency" => 0.589115646258503, 
				    "count" => 735, 
				    "std" => 0.511645350858064 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HZ3", 
				    "consistency" => 0.887978142076503, 
				    "count" => 732, 
				    "std" => 0.479914667350643 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HE3", 
				    "shift2" => "HH2", 
				    "consistency" => 0.814305364511692, 
				    "count" => 727, 
				    "std" => 0.535969569081703 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ2", 
				    "shift2" => "HZ3", 
				    "consistency" => 0.89437585733882, 
				    "count" => 729, 
				    "std" => 0.455956312526858 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HZ2", 
				    "shift2" => "HH2", 
				    "consistency" => 0.859673024523161, 
				    "count" => 734, 
				    "std" => 0.424480544922576 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "HH2", 
				    "shift2" => "HZ3", 
				    "consistency" => 0.735172413793103, 
				    "count" => 725, 
				    "std" => 0.431610591233567 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 360, 
				    "std" => 2.3830103694514 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 329, 
				    "std" => 3.18453187199025 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "C", 
				    "shift2" => "CD1", 
				    "consistency" => 1, 
				    "count" => 107, 
				    "std" => 2.69263155323132 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "C", 
				    "shift2" => "CZ2", 
				    "consistency" => 1, 
				    "count" => 112, 
				    "std" => 2.43323323051483 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "C", 
				    "shift2" => "CZ3", 
				    "consistency" => 1, 
				    "count" => 105, 
				    "std" => 2.89786263852275 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "C", 
				    "shift2" => "CH2", 
				    "consistency" => 1, 
				    "count" => 111, 
				    "std" => 2.12165497982612 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 557, 
				    "std" => 3.74719506252053 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CD1", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 203, 
				    "std" => 3.25735172241673 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CE3", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 189, 
				    "std" => 3.22298903340472 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CZ2", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 205, 
				    "std" => 4.37918156949385 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CZ3", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 192, 
				    "std" => 3.40712196438302 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CH2", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 202, 
				    "std" => 5.47038931890117 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CD1", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 202, 
				    "std" => 3.24711732774822 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CE3", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 189, 
				    "std" => 3.31140309052402 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CZ2", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 203, 
				    "std" => 3.82544879804756 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CZ3", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 191, 
				    "std" => 2.93733418510826 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CH2", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 201, 
				    "std" => 5.00798686851849 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CD1", 
				    "shift2" => "CE3", 
				    "consistency" => 0.98314606741573, 
				    "count" => 178, 
				    "std" => 2.34819879392932 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CD1", 
				    "shift2" => "CZ2", 
				    "consistency" => 1, 
				    "count" => 189, 
				    "std" => 2.71514218550034 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CD1", 
				    "shift2" => "CZ3", 
				    "consistency" => 0.965909090909091, 
				    "count" => 176, 
				    "std" => 2.6959095151055 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CD1", 
				    "shift2" => "CH2", 
				    "consistency" => 0.902173913043478, 
				    "count" => 184, 
				    "std" => 4.69556273055099 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CE3", 
				    "shift2" => "CZ2", 
				    "consistency" => 0.977653631284916, 
				    "count" => 179, 
				    "std" => 2.73809642739102 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CZ3", 
				    "shift2" => "CE3", 
				    "consistency" => 0.780898876404494, 
				    "count" => 178, 
				    "std" => 2.38284013497679 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CH2", 
				    "shift2" => "CE3", 
				    "consistency" => 0.972067039106145, 
				    "count" => 179, 
				    "std" => 4.03264567563531 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CZ3", 
				    "shift2" => "CZ2", 
				    "consistency" => 0.984375, 
				    "count" => 192, 
				    "std" => 2.4028716735427 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CH2", 
				    "shift2" => "CZ2", 
				    "consistency" => 0.990049751243781, 
				    "count" => 201, 
				    "std" => 4.42725002502005 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "CH2", 
				    "shift2" => "CZ3", 
				    "consistency" => 0.895287958115183, 
				    "count" => 191, 
				    "std" => 4.28083127602624 };
  
  push @{$$shift_order_rules{W}}, { "shift1" => "NE1", 
				    "shift2" => "N", 
				    "consistency" => 0.943488943488944, 
				    "count" => 407, 
				    "std" => 8.5410865633142 };
  
  
#
# Rules for Y
#
  $$shift_order_rules{Y} = [];
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 2494, 
				    "std" => 0.823329815492924 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2233, 
				    "std" => 0.861522807346024 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 2184, 
				    "std" => 0.8621824907789 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HD1", 
				    "consistency" => 0.967112024665981, 
				    "count" => 1946, 
				    "std" => 0.807717143925297 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HD2", 
				    "consistency" => 0.968408262454435, 
				    "count" => 1646, 
				    "std" => 0.805838831698019 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HE1", 
				    "consistency" => 0.984416980118216, 
				    "count" => 1861, 
				    "std" => 0.789998130381086 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "H", 
				    "shift2" => "HE2", 
				    "consistency" => 0.985443037974684, 
				    "count" => 1580, 
				    "std" => 0.786891465414383 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HA", 
				    "shift2" => "HB2", 
				    "consistency" => 0.992304403591278, 
				    "count" => 2339, 
				    "std" => 0.70231466289098 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HA", 
				    "shift2" => "HB3", 
				    "consistency" => 0.996503496503496, 
				    "count" => 2288, 
				    "std" => 0.704921635967105 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD1", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 2038, 
				    "std" => 0.624846141826812 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD2", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 1729, 
				    "std" => 0.625775772643308 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HE1", 
				    "shift2" => "HA", 
				    "consistency" => 1, 
				    "count" => 1956, 
				    "std" => 0.619558120328315 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HE2", 
				    "shift2" => "HA", 
				    "consistency" => 0.999400119976005, 
				    "count" => 1667, 
				    "std" => 0.616541330304208 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD1", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 2028, 
				    "std" => 0.392636180940925 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD2", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1733, 
				    "std" => 0.400700741268971 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HE1", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1947, 
				    "std" => 0.424197150510497 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HE2", 
				    "shift2" => "HB2", 
				    "consistency" => 1, 
				    "count" => 1669, 
				    "std" => 0.423137429221377 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD1", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1995, 
				    "std" => 0.387679631060011 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD2", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1719, 
				    "std" => 0.398505875040552 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HE1", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1914, 
				    "std" => 0.427487491063715 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HE2", 
				    "shift2" => "HB3", 
				    "consistency" => 1, 
				    "count" => 1655, 
				    "std" => 0.42831522650017 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD1", 
				    "shift2" => "HE1", 
				    "consistency" => 0.833486660533579, 
				    "count" => 2174, 
				    "std" => 0.293779031189437 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD1", 
				    "shift2" => "HE2", 
				    "consistency" => 0.835987261146497, 
				    "count" => 1884, 
				    "std" => 0.297826951857453 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD2", 
				    "shift2" => "HE1", 
				    "consistency" => 0.841185812599259, 
				    "count" => 1889, 
				    "std" => 0.32768797027251 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "HD2", 
				    "shift2" => "HE2", 
				    "consistency" => 0.841547429782724, 
				    "count" => 1887, 
				    "std" => 0.314191482180043 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "C", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 921, 
				    "std" => 2.20320401168969 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "C", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 820, 
				    "std" => 3.22667858739508 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "C", 
				    "shift2" => "CD1", 
				    "consistency" => 1, 
				    "count" => 314, 
				    "std" => 4.60116097570977 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "C", 
				    "shift2" => "CD2", 
				    "consistency" => 1, 
				    "count" => 193, 
				    "std" => 3.10642639970399 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "C", 
				    "shift2" => "CE1", 
				    "consistency" => 1, 
				    "count" => 311, 
				    "std" => 4.28977918535971 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "C", 
				    "shift2" => "CE2", 
				    "consistency" => 1, 
				    "count" => 195, 
				    "std" => 3.13189670550263 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CA", 
				    "shift2" => "CB", 
				    "consistency" => 0.998620689655172, 
				    "count" => 1450, 
				    "std" => 3.85399101687744 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD1", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 634, 
				    "std" => 4.07737019808384 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD2", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 351, 
				    "std" => 3.54680299723643 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CE1", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 638, 
				    "std" => 4.17522133927409 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CE2", 
				    "shift2" => "CA", 
				    "consistency" => 1, 
				    "count" => 360, 
				    "std" => 3.65865837896224 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD1", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 615, 
				    "std" => 3.69275150883156 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD2", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 341, 
				    "std" => 3.15854224273055 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CE1", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 619, 
				    "std" => 3.8724755107338 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CE2", 
				    "shift2" => "CB", 
				    "consistency" => 1, 
				    "count" => 348, 
				    "std" => 3.47031538961358 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD1", 
				    "shift2" => "CE1", 
				    "consistency" => 0.988691437802908, 
				    "count" => 619, 
				    "std" => 2.9751603469097 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD1", 
				    "shift2" => "CE2", 
				    "consistency" => 0.982507288629738, 
				    "count" => 343, 
				    "std" => 3.5321929606557 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD2", 
				    "shift2" => "CE1", 
				    "consistency" => 0.988338192419825, 
				    "count" => 343, 
				    "std" => 3.37337138504252 };
  
  push @{$$shift_order_rules{Y}}, { "shift1" => "CD2", 
				    "shift2" => "CE2", 
				    "consistency" => 0.988338192419825, 
				    "count" => 343, 
				    "std" => 3.35812011562962 };
  

  return $shift_order_rules;
  }
