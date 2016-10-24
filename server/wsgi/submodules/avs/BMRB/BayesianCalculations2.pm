#
#  BayesianCalculation2 - subroutines for calculating the bayesian likehood function for a 
#                         group of chemical shifts being a particular amino acid type.
#                         This differs from BayesionCalculations1 in that it uses the full
#                         covariance matrices in the calculations.
#
package BMRB::BayesianCalculations2;
require Exporter;
use BMRB::ChemicalShift;
use Statistics::Distributions;
@ISA = qw(Exporter);
@EXPORT = qw();
@EXPORT_OK = qw(bayesianProbabilityByCovarianceMatrix bayesianProbabilityByChiSquare bayesianProbabilityByMultivariateIntegral simplePrior frequencyPrior deltaPrior);
%EXPORT_TAGS = ( ALL => [@EXPORT_OK] );

# Enforces variable declaration, hard reference use, and no bareword use.
use strict;


#  bayesianProbability
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
#		                                       determinant value.
#		{"prior_sub"} - ref to prior subroutine that calculates a prior. 
sub bayesianProbabilityByCovarianceMatrix
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my $super_type = &findProperSuperType($aa_type, $res_shift_hlist, $BP_props);
  if ($super_type eq "")
    { return 0.0; }
  
  my @type_list = split /\s+/, $super_type;

  my $type1;
  my $type2;  
  my %vector1 = ();
  my %vector2 = ();
  foreach $type1 (@type_list)
    { $vector1{$type1} = ($$res_shift_hlist{$type1}->Value - $$BP_props{"mean"}{$aa_type}{$type1}); }

  foreach $type1 (@type_list)
    {
    foreach $type2 (@type_list)
      { $vector2{$type1} += $vector1{$type2} * $$BP_props{"inverted_covariance_matrices"}{$aa_type}{$super_type}->element($type2, $type1) }
    }

  my $exponent = 0.0;
  foreach $type1 (@type_list)
    { $exponent += $vector1{$type1} * $vector2{$type1};}

  if ($exponent < 0.0) 
    { return 0.0; }

  my $const = 0.398942;
  my $prior = &{$$BP_props{"prior_sub"}}($aa_type, $res_shift_hlist, $BP_props);
  return $const * exp(-0.5 * $exponent) * $prior / sqrt(abs($$BP_props{"covariance_matrices_determinant"}{$aa_type}{$super_type}));
  }


sub bayesianProbabilityByMultivariateIntegral
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my $super_type = &findProperSuperType($aa_type, $res_shift_hlist, $BP_props);
  if ($super_type eq "")
    { return 0.0; }
  
  my @type_alist = split /\s+/, $super_type;


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

sub bayesianProbabilityByChiSquare
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


#  findProperSuperType - internal subroutine only
#    Returns an appropriate SuperType that is compatible with the given ResType and $res_shift_hlist.
#
#  Parameters:
#	$aa_type - ResType.
#	$res_shift_hlist - ref to hash of AtomType to ChemicalShift ref.
#	$BP_props - properties for calculating the bayesian probability.
#		{"covariance_matrices_determinant"} - ref to hash of ResType to hash of SuperType to scalar
#		                                       determinant value.
sub findProperSuperType
  {
  my $aa_type = shift @_;
  my $res_shift_hlist = shift @_;
  my $BP_props = shift @_;

  my @type_list = sort keys %$res_shift_hlist;
  my $super_type;
  my ($x,$y,$z);
  my $count;
  my @type_list2;

  for($x= $#type_list; $x >= 0; $x--)
    {
    $y = 0;
    while((($y + $x) < @type_list) && ($x || !$y)) # ($x || !$y) allows only single pass for matrix sizes of 1.
      {
      $z = $y;
      $count = 0;
      @type_list2 = ();
      while($count < $x)
	{
	push @type_list2, $type_list[$z];
        $count++;
	$z++;	
	}

      while($z < @type_list)
	{
	push @type_list2, $type_list[$z];
        $super_type = join(' ', @type_list2);
        if ($$BP_props{"covariance_matrices_determinant"}{$aa_type}{$super_type})
	  { return $super_type; }
        pop @type_list2;
	$z++;
	}
      
      $y++;
      }
    }

  return "";
  }


