#	Copyright Hunter Moseley, 2000. All rights reserved.
#	Written by Hunter Moseley 5/1/2000
#       Revised by Gurmukh Sahota 7/15/2000
#	Revised by Hunter Moseley 3/19/2001

#
#  BayesianCalculation4 - subroutines for calculating the bayesian likehood function for a 
#                         group of chemical shifts being a particular amino acid type.
#                         This differs from BayesianCalculations3 it only tries all possible 
#                         combinations of AtomsTypes starting with CX for the given chemical shifts.
#
package BMRB::BayesianCalculations4;
require Exporter;
use BMRB::ChemicalShift;
use Statistics::Distributions;
use FindBin;

@ISA = qw(Exporter);
@EXPORT = qw();
@EXPORT_OK = qw(allBayesianProbCombinationsCXrecomb allBayesianProbCombinationsCXrecomb2 singleBProbByCovarianceMatrix singleBProbByMeanVariance singleBProbByMeanVarianceChiSquare singleBProbByMultivariateIntegral
		simplePrior frequencyPrior deltaPrior shiftCountWeightPrior shiftCountWeightExpPrior);
%EXPORT_TAGS = ( ALL => [@EXPORT_OK] );

# Enforces variable declaration, hard reference use, and no bareword use.
use strict;


#  allBayesianProbCombinationsCXrecomb
#    Returns the chemical shift assignments which yields the highest typing probability.
#
#  Parameters:
#	$aa_type - amino acid type
#	$res_shift_hlist - reference to a hash of AtomType to ChemicalShift refs.
#	$BP_props - properties for calculating the bayesian probability.
#		{"mean"} - ref to hash of ResType to hash of AtomType to scalar mean values.
#		{"variance"} - ref to hash of ResType to hash of AtomType to scalar variance values.
#		{"mean_count"} - ref to hash of ResType to hash of AtomType to scalar count of values used 
#		                 to calculate the means.
#		{"inverted_covariance_matrices"} - ref to hash of ResType to hash of SuperType to inverted 
#		                                   covariance TypedMatrix ref.
#		{"covariance_matrices_determinant"} - ref to hash of ResType to hash of SuperType to scalar
#		                                      determinant value.
#		{"prior_sub"} - ref to prior subroutine that calculates a prior. 
#		{"CX_prior_sub"} - ref to prior subroutine that calculates a prior for selecting between possible CX's. 
#		{"restricted_type_lists"} - ref to hash of ResType to array of possible AtomTypes for a particular
#		                            ResType.
#		{"single_bp_sub"} - ref to subroutine that calculates a single bayesian probability.
sub allBayesianProbCombinationsCXrecomb
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;
  my $verbose = shift @_;
  my $min_size = 0;
  if (@_)
    { $min_size = shift @_; }
  
  my ($x, $y, $z);
  my @type_alist2;
  my $prob;
  my $max_prob = 0.0;
  my $true_prob = 0.0;
  my $max_true_prob = 0.0;
  my $max_res_shift_hlist = {};
  my $temp_res_shift_hlist = {};
  my $max_size = scalar (grep /^CX/, keys %$res_shift_hlist);
  my $count;
  # need to redo this algorithm because it is not correct! Use "ordered_gly_match_vecs" in Protein.cc as a guideline.
  
  my @fulltypelist = @{$$BP_props{"restricted_type_lists"}{$aa_type}};

  if ($min_size > $max_size)
    { $min_size = $max_size; }
  
  if ($min_size > scalar(@fulltypelist))
    { $min_size = scalar(@fulltypelist); }
  
  
  my @other_keys = grep !/^CX/, keys %$res_shift_hlist;
  my @recombinable_typelist;
  foreach my $elem (@fulltypelist)
    {     
    my @temp = grep /$elem/, @other_keys;
    push (@recombinable_typelist, $elem) unless ($temp[0] eq $elem);
    }    
  
  
  my %properatoms_res_shift_hlist;
  foreach my $key (keys %$res_shift_hlist)
    {
    my @matched_key = grep /^$key$/, @{$$BP_props{"restricted_type_lists"}{$aa_type}};
    if ($matched_key[0] eq $key)
      { $properatoms_res_shift_hlist{$key} = $$res_shift_hlist{$key}; }
    }
  
  
# Previous check before funky joinings. 
#  elsif ((!(($#other_keys == 0) && ($other_keys[0] eq "CA"))) || (($#fulltypelist == 0) && ($fulltypelist[0] eq "CA")))
  
  if (($max_size == 0) || ($#recombinable_typelist == -1))
    { 
#      print "NO RECOMBINATION >>> \n";      
    if (wantarray)
      { return (&{$$BP_props{"single_bp_sub"}}($aa_type, \%properatoms_res_shift_hlist, $BP_props), \%properatoms_res_shift_hlist); }
    else
      { return \%properatoms_res_shift_hlist; }
    }
  elsif ((join('', keys %properatoms_res_shift_hlist )) ne '')
    {
#      print "SINGLE RECOMBINATION >>> \n";
    $max_res_shift_hlist = \%properatoms_res_shift_hlist;
    $max_true_prob = &{$$BP_props{"single_bp_sub"}}($aa_type, $max_res_shift_hlist, $BP_props);
    $max_prob = $max_true_prob * &{$$BP_props{"CX_prior_sub"}}($aa_type, $max_res_shift_hlist, $BP_props);
    if ($verbose && scalar(%$max_res_shift_hlist))
      {
      print "\n\t-------------------------------------------------";
      print "\n\tPROB>> $max_true_prob ($max_prob)\n\tSHIFT_LIST>>\t";
      foreach my $SHAT (keys %$max_res_shift_hlist)
	{ print $SHAT, " :: ", $$max_res_shift_hlist{$SHAT}->Value, "\t"; }

      print "\n";
      }    
    }
      
  
#  print "RECOMBINABLE TYPELIST >> @recombinable_typelist", "\n";
  if ( $max_size > @recombinable_typelist )
    { $max_size =  @recombinable_typelist; }
  
  
  for(my $x=1; $x < (2 ** @recombinable_typelist); $x++)
    {
    # create new sub list of types and generate a new inverse covariance matrix.xsxc
    my @type_alist2 = ();
    my $count = 0;
    for(my $y=0; $y < @recombinable_typelist; $y++)
      {
      if ((2 ** $y) & $x) # test for inclusion in the sub list
	{ push @type_alist2, $recombinable_typelist[$y]; $count++;}
      }
    if (($count<=$max_size) && ($count >= $min_size))
      {    
      ($true_prob, $temp_res_shift_hlist) = &calculateBayesianPermutationCXrecomb($aa_type, $res_shift_hlist, \@type_alist2, $BP_props);
      $prob = $true_prob * &{$$BP_props{"CX_prior_sub"}}($aa_type, $temp_res_shift_hlist, $BP_props);
      if ($prob > $max_prob)
	{ 
	$max_prob = $prob;
	$max_true_prob = $true_prob;
	%$max_res_shift_hlist = %$temp_res_shift_hlist;
	}
      if ($verbose && scalar(%$temp_res_shift_hlist))
	{
	print "\n\tPROB>> $true_prob ($prob)\n\tSHIFT_LIST>>\t";
	foreach my $SHAT (keys %$temp_res_shift_hlist)
	  { print $SHAT, " :: ", $$temp_res_shift_hlist{$SHAT}->Value, "\t"; }

	print "\n";
	}      
      }
    }
  
  if ($verbose)
    { print "\t-------------------------------------------------\n\n"; }

  if (wantarray)
    { return ($max_true_prob, $max_res_shift_hlist); }
  
  return $max_res_shift_hlist;  
  }


#  allBayesianProbCombinationsCXrecomb2
#    Returns the chemical shift assignments which yields the highest typing probability.
#	Acts like allBayesianProbCombinationsCXrecomb except that res_shift_hlist can point to
#       array of ChemicalShifts for certain AtomTypes.
#
#  Parameters:
#	$aa_type - amino acid type
#	$res_shift_hlist - reference to a hash of AtomType to ChemicalShift refs.
#	$BP_props - properties for calculating the bayesian probability.
#		{"mean"} - ref to hash of ResType to hash of AtomType to scalar mean values.
#		{"variance"} - ref to hash of ResType to hash of AtomType to scalar variance values.
#		{"mean_count"} - ref to hash of ResType to hash of AtomType to scalar count of values used 
#		                 to calculate the means.
#		{"inverted_covariance_matrices"} - ref to hash of ResType to hash of SuperType to inverted 
#		                                   covariance TypedMatrix ref.
#		{"covariance_matrices_determinant"} - ref to hash of ResType to hash of SuperType to scalar
#		                                      determinant value.
#		{"prior_sub"} - ref to prior subroutine that calculates a prior. 
#		{"CX_prior_sub"} - ref to prior subroutine that calculates a prior for selecting between possible CX's. 
#		{"restricted_type_lists"} - ref to hash of ResType to array of possible AtomTypes for a particular
#		                            ResType.
#		{"single_bp_sub"} - ref to subroutine that calculates a single bayesian probability.
sub allBayesianProbCombinationsCXrecomb2
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;
  my $verbose = shift @_;
  my $min_size = 0;
  if (@_)
    { $min_size = shift @_; }
  
  my ($x, $y, $z);
  my @type_alist2;
  my $prob;
  my $max_prob = 0.0;
  my $true_prob = 0.0;
  my $max_true_prob = 0.0;
  my $max_res_shift_hlist = {};
  my $temp_res_shift_hlist = {};
  my $max_size = scalar (grep /^CX/, keys %$res_shift_hlist);
  my $count;
  # need to redo this algorithm because it is not correct! Use "ordered_gly_match_vecs" in Protein.cc as a guideline.
  
  my @fulltypelist = @{$$BP_props{"restricted_type_lists"}{$aa_type}};

  if ($min_size > $max_size)
    { $min_size = $max_size; }
  
  if ($min_size > scalar(@fulltypelist))
    { $min_size = scalar(@fulltypelist); }
  
  
  my @other_keys = grep !/^CX/, keys %$res_shift_hlist;
  my @recombinable_typelist;
  foreach my $elem (@fulltypelist)
    {     
    my @temp = grep /$elem/, @other_keys;
    push (@recombinable_typelist, $elem) unless ($temp[0] eq $elem);
    }    
  
  my %properatoms_res_shift_hlist;
  my @properatoms_arrays;
  my $res_shift_hlist2 = {};
  foreach my $key (keys %$res_shift_hlist)
    {
    $$res_shift_hlist2{$key} = $$res_shift_hlist{$key}; 
    my @matched_key = grep /^$key$/, @{$$BP_props{"restricted_type_lists"}{$aa_type}};
    if ($matched_key[0] eq $key)
      { 
      $properatoms_res_shift_hlist{$key} = $$res_shift_hlist{$key}; 
      if (ref($$res_shift_hlist{$key}) eq "ARRAY")
	{ push @properatoms_arrays, [$key, $$res_shift_hlist{$key} ]; }
      }
    }

  my @indeces;
  while(! @properatoms_arrays || ($indeces[$#properatoms_arrays] < @{$properatoms_arrays[$#properatoms_arrays][1]}))
    {

    $temp_res_shift_hlist = \%properatoms_res_shift_hlist;
    if (@properatoms_arrays)
      {
      for($x=0; $x < @properatoms_arrays; $x++)
	{ 
	$$temp_res_shift_hlist{$properatoms_arrays[$x][0]} = $properatoms_arrays[$x][1][$indeces[$x]]; 
	$$res_shift_hlist2{$properatoms_arrays[$x][0]} = $properatoms_arrays[$x][1][$indeces[$x]]; 
	}
      }


    # adjust indeces
    $indeces[0]++;
    if (@properatoms_arrays > 1)
      {
      for(my $x=0; $x < @properatoms_arrays-1; $x++)
	{
	if ($indeces[$x] >= @{$properatoms_arrays[$x][1]})
	  {
	  $indeces[$x] = 0; 
	  $indeces[$x+1]++;
	  }
	}
      }

# Previous check before funky joinings. 
#  elsif ((!(($#other_keys == 0) && ($other_keys[0] eq "CA"))) || (($#fulltypelist == 0) && ($fulltypelist[0] eq "CA")))
  
    if ((join('', keys %properatoms_res_shift_hlist )) ne '')
      {
#      print "SINGLE RECOMBINATION >>> \n";
      $true_prob = &{$$BP_props{"single_bp_sub"}}($aa_type, $temp_res_shift_hlist, $BP_props);
      $prob = $true_prob * &{$$BP_props{"CX_prior_sub"}}($aa_type, $temp_res_shift_hlist, $BP_props);
      if ($verbose && scalar(%$temp_res_shift_hlist))
	{
	print "\n\t-------------------------------------------------";
	print "\n\tPROB>> $max_true_prob ($max_prob)\n\tSHIFT_LIST>>\t";
	foreach my $SHAT (keys %$temp_res_shift_hlist)
	  { print $SHAT, " :: ", $$temp_res_shift_hlist{$SHAT}->Value, "\t"; }
	
	print "\n";
	}    
      
      if ($prob > $max_prob)
	{ 
	$max_prob = $prob;
	$max_true_prob = $true_prob;
	%$max_res_shift_hlist = %$temp_res_shift_hlist;
	}
      }      
    
    last if (! @properatoms_arrays &&(($max_size == 0) || ($#recombinable_typelist == -1)));
    next if (($max_size == 0) || ($#recombinable_typelist == -1));

#  print "RECOMBINABLE TYPELIST >> @recombinable_typelist", "\n";
    if ( $max_size > @recombinable_typelist )
      { $max_size =  @recombinable_typelist; }
        
    for(my $x=1; $x < (2 ** @recombinable_typelist); $x++)
      {
      # create new sub list of types and generate a new inverse covariance matrix.xsxc
      my @type_alist2 = ();
      my $count = 0;
      for(my $y=0; $y < @recombinable_typelist; $y++)
	{
	if ((2 ** $y) & $x) # test for inclusion in the sub list
	  { push @type_alist2, $recombinable_typelist[$y]; $count++;}
	}
      if (($count<=$max_size) && ($count >= $min_size))
	{    
	($true_prob, $temp_res_shift_hlist) = &calculateBayesianPermutationCXrecomb($aa_type, $res_shift_hlist2, \@type_alist2, $BP_props);
	$prob = $true_prob * &{$$BP_props{"CX_prior_sub"}}($aa_type, $temp_res_shift_hlist, $BP_props);
	if ($prob > $max_prob)
	  { 
	  $max_prob = $prob;
	  $max_true_prob = $true_prob;
	  %$max_res_shift_hlist = %$temp_res_shift_hlist;
	  }
	if ($verbose && scalar(%$temp_res_shift_hlist))
	  {
	  print "\n\tPROB>> $true_prob ($prob)\n\tSHIFT_LIST>>\t";
	  foreach my $SHAT (keys %$temp_res_shift_hlist)
	    { print $SHAT, " :: ", $$temp_res_shift_hlist{$SHAT}->Value, "\t"; }
	  
	  print "\n";
	  }      
	}
      }

  
    last if (! @properatoms_arrays)
    }
  
  if ($verbose)
    { print "\t-------------------------------------------------\n\n"; }
  
  if (wantarray)
    { return ($max_true_prob, $max_res_shift_hlist); }
  
  return $max_res_shift_hlist;  
  }


#  Single Bayesian Probability subroutines
#   Returns single bayesian probability for a given AtomType permutation.
#
#  Parameters:
#	$aa_type - amino acid type
#	$res_shift_hlist - reference to a hash of AtomType to ChemicalShift refs.
#	$BP_props - properties for calculating the bayesian probability.
sub singleBProbByCovarianceMatrix
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my @type_alist = sort keys %$res_shift_hlist;
  my $super_type = join(' ', @type_alist); 


# GSS 07/02/00 reinstated to fix problem of supertypes where there were none.  Talk to Hunter about this. eg. Y:: CA CD CG
# GSS 07/17/00 unreinstated.  Problem with permutations in Statistics.pm fixed.

#  if (! $$BP_props{"covariance_matrices_determinant"}{$aa_type}{$super_type})
#    { return 0.0; }

  my $type1;
  my $type2;  
  my %vector1 = ();
  my %vector2 = ();
  foreach $type1 (@type_alist)
    { $vector1{$type1} = ($$res_shift_hlist{$type1}->Value - $$BP_props{"mean"}{$aa_type}{$type1}); }

  foreach $type1 (@type_alist)
    {
    foreach $type2 (@type_alist)
      { 
#          print "SUPERTYPE :: $super_type ;; AATYPE :: $aa_type\n";
	      $vector2{$type1} += $vector1{$type2} * $$BP_props{"inverted_covariance_matrices"}{$aa_type}{$super_type}->element($type2, $type1) }
    }

  my $exponent = 0.0;
  foreach $type1 (@type_alist)
    { $exponent += $vector1{$type1} * $vector2{$type1};}

  if ($exponent < 0.0) 
    { return 0.0; }

  my $const = 0.398942;
  my $prior = &{$$BP_props{"prior_sub"}}($aa_type, $res_shift_hlist, $BP_props);

  return $const * exp(-0.5 * $exponent) * $prior / sqrt(abs($$BP_props{"covariance_matrices_determinant"}{$aa_type}{$super_type}));
  }

sub singleBProbByMultivariateIntegral
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my @type_alist = sort keys %$res_shift_hlist;
  my $super_type = join(' ', @type_alist); 


  my $type1;
  my $type2;  

  my $toms_input = scalar(@type_alist) . "\n";

  foreach $type1 (@type_alist)
     { $toms_input .= (-1 * abs(($$res_shift_hlist{$type1}->Value - $$BP_props{"mean"}{$aa_type}{$type1}) / sqrt($$BP_props{"variance"}{$aa_type}{$type1}) )) . "\n"; }

  foreach $type1 (@type_alist)
    {
    foreach $type2 (@type_alist)
      { $toms_input .= $$BP_props{"covariance_matrices"}{$aa_type}->element($type2, $type1) . "\n"; }
    }

  my $prior = &{$$BP_props{"prior_sub"}}($aa_type, $res_shift_hlist, $BP_props);
  my $toms_result = `echo \"$toms_input\" | $FindBin::Bin/toms_725_read`;
  return $toms_result * $prior;
  }

sub singleBProbByMeanVariance
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my $exponent = 0.0;
  my $found = 0;  
  my $type;
  foreach $type (keys %$res_shift_hlist)
    {
    if ($$BP_props{"mean_count"}{$aa_type}{$type})
      { 
      $found = 1.0; 
      $exponent += -0.5 * ($$res_shift_hlist{$type}->Value - 
			   $$BP_props{"mean"}{$aa_type}{$type}) ** 2.0 / 
			     $$BP_props{"variance"}{$aa_type}{$type} ; 
      }
    }

  if (! $found)
    { return 0.0; }

  my $const = 0.398942;
  my $prior = &{$$BP_props{"prior_sub"}}($aa_type, $res_shift_hlist, $BP_props);
  return $const * exp($exponent) * $prior;
  }

sub singleBProbByMeanVarianceChiSquare
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my $test = 0.0;
  my $freedom = 0;
  foreach my $type (keys %$res_shift_hlist)
    {
    if ($$BP_props{"mean_count"}{$aa_type}{$type})
      { 
      $freedom++; 
      $test += ($$res_shift_hlist{$type}->Value - 
		$$BP_props{"mean"}{$aa_type}{$type}) ** 2.0 / 
		  $$BP_props{"variance"}{$aa_type}{$type} ; 
      }
    }

  if (! $freedom)
    { return 0.0; }

  my $prior = &{$$BP_props{"prior_sub"}}($aa_type, $res_shift_hlist, $BP_props);
  return Statistics::Distributions::chisqrprob($freedom,$test) * $prior;
  }


#  Prior subroutines
#   Return prior value for bayesianProbability subroutine.
#
#  Parameters:
#	$aa_type - amino acid type
#	$res_shift_hlist - reference to hash of AtomType to ChemicalShift ref.
#	$BP_props - properties for calculating the bayesian probability.
#		{"File_ResType_frequencies"} - ref to hash of File to hash of ResType to scalar 
#		                                  frequency value.
sub simplePrior
  { return 1.0; }

sub frequencyPrior
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;
  my ($junk, $shift) = (each %$res_shift_hlist); 

  return $$BP_props{"File_ResType_frequencies"}{$shift->File}{$aa_type};
  }

sub deltaPrior
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;
  if (! scalar(%$res_shift_hlist))
    { return 0; }
  my ($junk, $shift) = (each %$res_shift_hlist);

  return ($$BP_props{"File_ResType_frequencies"}{$shift->File}{$aa_type} != 0);
  }

sub shiftCountWeightPrior
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;
  my $shift_count = (keys %$res_shift_hlist); 

  return $$BP_props{"Shift_Count_Prior_Weight"} * $shift_count;
  }

sub shiftCountWeightExpPrior
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;
  my $shift_count = (keys %$res_shift_hlist); 

  return $$BP_props{"Shift_Count_Prior_Weight"} ** $shift_count;
  }



#  calculateBayesianPermutationCXrecomb - for internal use only.
#   Calculate probability for a given amino acid type using all permutations of res_shift_hlist assigned
#    to the AtomTypes in the $type_alist
#
#  Parameters:
#	$aa_type - amino acid type
#	$res_shift_hlist - reference to a hash of AtomType to ChemicalShift refs.
#	$type_alist - reference to array of AtomTypes to use.
#	$BP_props - properties for calculating the bayesian probability.
sub calculateBayesianPermutationCXrecomb
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $type_alist_initial = shift @_;
  my $BP_props = shift @_;


  my $max_res_shift_hlist = {};


  my @non_CX_keys = grep !/^CX/, keys %$res_shift_hlist;
  my %std_res_shift_hlist;

#  print "INITIAL TYPE LIST: ", join(" : ", @$type_alist_initial), "\n";
  foreach my $key (@non_CX_keys)
	     {$std_res_shift_hlist{$key} = $$res_shift_hlist{$key};}

  my $type_alist;

  my %seen = map { $_, 1 } @non_CX_keys;
  foreach my $elem (@$type_alist_initial)
     { push (@$type_alist, $elem) unless exists $seen{$elem}; }
 

  my @type_alist2 = grep /^CX/, keys %$res_shift_hlist;


#  print "TYPE_ALIST>> \t ", "@$type_alist", "\n";
#  print "TYPE_ALIST2>> \t ", "@type_alist2", "\n";


  my $max_prob = 0.0;
  my $num_permutations = &factorial(scalar @type_alist2);
  for (my $x=0; $x < $num_permutations; $x++)
    {
    my %new_res_shift_hlist = %std_res_shift_hlist;
    my @type_map = &n2perm($x, $#type_alist2);
    for(my $y=0; $y < @$type_alist; $y++)
      { $new_res_shift_hlist{$$type_alist[$y]} = $$res_shift_hlist{$type_alist2[$type_map[$y]]}; }

    # Do not allow Bayesian Typing on only CA's.
    # if keys new_res_shift_hlist != only CA then proceed else next
    # Extensive discussion: greater number shifts = greater probability thus no need
#      next if ( (join('', keys %$new_res_shift_hlist)) eq 'CA');

    # incorrect algorithm
    # next if (((scalar(@$type_alist)) == 1) && ($$type_alist[0] eq "CA"));

    my $prob = &{$$BP_props{"single_bp_sub"}}($aa_type, \%new_res_shift_hlist, $BP_props);

#    $prob *= 6 ** (scalar (keys %new_res_shift_hlist) - 1);

    if ($prob > $max_prob)
      { 
	  $max_prob = $prob; 
	  %$max_res_shift_hlist = %new_res_shift_hlist;
      }

#	    print "PERMUTE>>\n";
#	      foreach my $SHAT (keys %new_res_shift_hlist)
#	           {print $SHAT, " :: ", $new_res_shift_hlist{$SHAT}->Value, "\t";}
#	     print "\n";

    } 

  return $max_prob, $max_res_shift_hlist;
  }

#
# Code for calculating permutations from the Perl Cookbook.
#

# Utility function: factorial with memorizing
BEGIN {
  my @fact = (1);
  sub factorial($) {
      my $n = shift;
      return $fact[$n] if defined $fact[$n];
      $fact[$n] = $n * factorial($n - 1);
  }
}

# n2pat($N, $len - 1) : produce the $N-th pattern of length $len
sub n2pat {
    my $i   = 1;
    my $N   = shift;
    my $len = shift;
    my @pat;
    while ($i <= $len + 1) {   # Should really be just while ($N) { ...
        push @pat, $N % $i;
        $N = int($N/$i);
        $i++;
    }
    return @pat;
}

# pat2perm(@pat) : turn pattern returned by n2pat() into
# permutation of integers.  XXX: splice is already O(N)
sub pat2perm {
    my @pat    = @_; # This is a list of offsets to use when splicing elements off the source list.
    my @source = (0 .. $#pat);
    my @perm;
    push @perm, splice(@source, (pop @pat), 1) while @pat;
    return @perm;
}

# n2perm($N, $len - 1) : generate the Nth permutation of $len objects
sub n2perm {
    return &pat2perm(n2pat(@_));
}

return 1;
