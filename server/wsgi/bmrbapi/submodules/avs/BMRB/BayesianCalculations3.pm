#
#  BayesianCalculation3 - subroutines for calculating the bayesian likehood function for a 
#                         group of chemical shifts being a particular amino acid type.
#                         This differs from BayesionCalculations2 it tries all possible 
#                         combinations of AtomsTypes with the given chemical shifts.
#
package BMRB::BayesianCalculations3;
require Exporter;
use BMRB::ChemicalShift;
use Statistics::Distributions;
use FindBin;

@ISA = qw(Exporter);
@EXPORT = qw();
@EXPORT_OK = qw(allBayesianProbCombinations singleBProbByCovarianceMatrix singleBProbByMeanVariance singleBProbByMeanVarianceChiSquare singleBProbByMultivariateIntegral
		simplePrior frequencyPrior deltaPrior shiftCountWeightPrior shiftCountWeightExpPrior);
%EXPORT_TAGS = ( ALL => [@EXPORT_OK] );

# Enforces variable declaration, hard reference use, and no bareword use.
use strict;


#  allBayesianProbCombinations
#    Returns the probability for a given set of chemical shifts being a particular amino acid type.
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
#		{"covariance_type_lists"} - ref to hash of ResType to array of possible AtomTypes for a particular
#		                            ResType.
#		{"single_bp_sub"} - ref to subroutine that calculates a single bayesian probability.
sub allBayesianProbCombinations
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my $max_prob = 0.0;
  my $max_size = scalar (keys %$res_shift_hlist);
  # need to redo this algorithm because it is not correct! Use "ordered_gly_match_vecs" in Protein.cc as a guideline.
  if ($max_size > @{$$BP_props{"covariance_type_lists"}{$aa_type}})
    { $max_size = @{$$BP_props{"covariance_type_lists"}{$aa_type}}; }
  
  
  for(my $x = 1; $x < 2 ** @{$$BP_props{"covariance_type_lists"}{$aa_type}}; $x++)
    {
    my @type_alist2 = ();
    my $count = 0;
    for(my $y=0; $y < @{$$BP_props{"covariance_type_lists"}{$aa_type}}; $y++)
      {
      if ((2 ** $y) & $x) # test for inclusion in the sub list
	{
	$count++;
	push @type_alist2, $$BP_props{"covariance_type_lists"}{$aa_type}[$y];
	}
      }

    if ($count == $max_size) # calculate for all permutations if the type list is the appropriate size
      {
      my $prob = &calculateBayesianPermutation($aa_type, $res_shift_hlist, \@type_alist2, $BP_props);
      if ($prob > $max_prob)
	{ $max_prob = $prob; }
      }
    }

  return $max_prob;  
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
      { $vector2{$type1} += $vector1{$type2} * $$BP_props{"inverted_covariance_matrices"}{$aa_type}{$super_type}->element($type2, $type1) }
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



#  calculateBayesianPermutation - for internal use only.
#   Calculate probability for a given amino acid type using all permutations of res_shift_hlist assigned
#    to the AtomTypes in the $type_alist
#
#  Parameters:
#	$aa_type - amino acid type
#	$res_shift_hlist - reference to a hash of AtomType to ChemicalShift refs.
#	$type_alist - reference to array of AtomTypes to use.
#	$BP_props - properties for calculating the bayesian probability.
sub calculateBayesianPermutation
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $type_alist = shift @_;
  my $BP_props = shift @_;

  my @type_alist2 = keys %$res_shift_hlist;

  if (@type_alist2 == 1)
    {
    my %new_res_shift_hlist = ();
    $new_res_shift_hlist{$$type_alist[0]} = $$res_shift_hlist{$type_alist2[0]};
    return &{$$BP_props{"single_bp_sub"}}($aa_type, \%new_res_shift_hlist, $BP_props);
    }


  my $max_prob = 0.0;
  my $num_permutations = &factorial(scalar @type_alist2);
  for (my $x=0; $x < $num_permutations; $x++)
    {
    my %new_res_shift_hlist = ();
    my @type_map = &n2perm($x, $#type_alist2);
    for(my $y=0; $y < @$type_alist; $y++)
      { $new_res_shift_hlist{$$type_alist[$y]} = $$res_shift_hlist{$type_alist2[$type_map[$y]]}; }
    
    my $prob = &{$$BP_props{"single_bp_sub"}}($aa_type, \%new_res_shift_hlist, $BP_props);
    if ($prob > $max_prob)
      { $max_prob = $prob; }
    } 

  return $max_prob;
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


# End Module with a return true.
return 1;
