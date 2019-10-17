#
#  BMRB::TypedMatrix - class that designates matrix row/columns by non numeric indices.
#

#
#  This differs from TypedMatrix in that the invert routine calls a c program to calculate the
#  inverse.
#
package BMRB::TypedMatrix2;
require Exporter;
use Math::MatrixReal;
@ISA = qw(Exporter);
@EXPORT = qw();

use strict;
use Carp;

sub AUTOLOAD
  {
  my $this = shift @_;
  my $type = ref($this) || croak "$this in not an object";
  my $name = $BMRB::TypedMatrix2::AUTOLOAD;
  $name =~ s/.*://; # strip fully-qualified portion
  if (! exists $this->{$name})
    { croak "Can't access `$name' field in object of class $type"; }
  
  if (@_)
    { return $this->{$name} = shift @_; }
  
  return $this->{$name};
  }

sub new
  {
  my $that = shift @_;
  my $class = ref($that) || $that || 'BMRB::TypedMatrix2';
  my $this = {};
  $this->{matrix} = Math::MatrixReal->new(scalar @_, scalar @_);

  $this->{type_hash} = {};
  my $x;
  for($x = 0; $x < @_; $x++)
    { $this->{type_hash}{@_[$x]} = $x+1; }
    
  bless $this, $class;
  return $this;
  }

sub copy 
  {
  if (@_ != 2)
    { croak "Usage: \$typed_matrix->copy(\$typed_matrix);"; }

  my $this = shift @_;
  my $other = shift @_;

  $this->{matrix}->copy($other->{matrix});
  $this->{type_hash} = { %{$other->{type_hash}} };
  }

sub clone
  {
  if (@_ != 1)
    { croak "Usage: \$typed_matrix->clone()"; }

  my $this = shift @_;
  my $temp = $this->new();
  $temp->copy($this);

  return $temp;
  }

sub exists
  {
  if (@_ < 2)
    { croak "Usage: \$typed_matrix->exists(type || \@types)"; }

  my $this = shift @_;
  my $type;

  foreach $type (@_)
    {
    if (! exists $this->{type_hash}{$type})
      { return 0; }
    }

  return 1;
  }


sub add
  {
  if (@_ < 2)
    { croak "Usage: \$typed_matrix->add(type || \@types);"; }

  my $this = shift @_;
  my $type;

  foreach $type (@_)
    {
    if (! exists $this->{type_hash}{$type})
      { $this->{type_hash}{$type} = ++($this->{matrix}->[1]); $this->{matrix}->[2]++; }		 
    }
  }


sub element
  {
  if (@_ < 3)
    { croak "Usage: \$typed_matrix->element(\$row_type, \$col_type, (optional) \$value)"; }

  my $this = shift @_;
  my $row_type = shift @_;
  my $col_type = shift @_;

  if (! exists $this->{type_hash}{$row_type})
    { $this->add($row_type); }

  if (! exists $this->{type_hash}{$col_type})
    { $this->add($col_type); }

  if (@_)
    { $this->{matrix}->assign($this->{type_hash}{$row_type}, $this->{type_hash}{$col_type}, shift @_); }

  return $this->{matrix}->element($this->{type_hash}{$row_type}, $this->{type_hash}{$col_type});
  }

sub assign
  {
  if (@_ < 4)
    { croak "Usage: \$typed_matrix->assign(\$row_type, \$col_type, \$value)"; }
  
  return &element(@_); 
  }

sub invert
  {
  if (@_ != 1)
    { croak "Usage: \$typed_matrix->invert()"; }

  my $this = shift @_;

  my $program_input = "\"";
  # print covariance matrix size
  my @type_list = sort keys %{$this->{type_hash}};
  $program_input .= (scalar @type_list) . " ";

  # print the covariance matrix
  my($type1, $type2);
  foreach $type1 (@type_list)
    {
    foreach $type2 (@type_list)
      { $program_input .= $this->element($type1, $type2) . " "; }
    }

  $program_input .= "\"";

  my @program_output = `echo $program_input | matrix_calc_inverse_determinant`;
  my $determinant = shift @program_output;
  chomp $determinant;

  my @row_tokens;
  foreach $type1 (@type_list)
    {
    @row_tokens = split /\s+/, shift @program_output;
    my $x = 0;
    foreach $type2 (@type_list)
      {
      $this->element($type1,$type2, $row_tokens[$x]);
      $x++;
      }
    }


  return wantarray ? ($this, $determinant) : $this;
  }


sub submatrix
  {
  if (@_ < 1)
    { croak "Usage: \$typed_matrix->submatrix(\@types)"; }
  
  my $this = shift @_;
  my $temp = $this->new(@_);
  my $type1; 
  my $type2;
  
  foreach $type1 (@_)
    {
    if (exists $this->{type_hash}{$type1})
      {
      foreach $type2 (@_)
	{ 
	if (exists $this->{type_hash}{$type2})
	  { $temp->assign($type1, $type2, $this->element($type1, $type2)); }
	}
      }
    }

  return $temp;
  }

# End the Module with a return true.
return 1;
