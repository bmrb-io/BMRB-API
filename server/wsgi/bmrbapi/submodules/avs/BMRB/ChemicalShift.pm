#
#  BMRB::ChemicalShift - class that embodies the characteristics of a chemical shift.
#
package BMRB::ChemicalShift;
require Exporter;
use Carp;
@ISA = qw(Exporter);
@EXPORT = qw();
@EXPORT_FAIL = qw(%fields);

# Enforces variable declaration, hard reference use, and no bareword use.
use strict;

my %fields = 
  ( 
  File => undef,	# name of nmr star file
  ResNum => undef,	# residue number
  ResType => undef,	# residue type
  AtomType => undef,	# atom type
  Value => undef	# chemical shift value
  );

sub new 
  {
  my $that = shift @_;
  my $class = ref($that) || $that || 'BMRB::ChemicalShift';
  my $self = { %fields, };
  if (@_)
    {
    if (ref(@_[0]) eq "ARRAY")
      {
      my $list = shift @_;
      $self->{File} = $$list[0];
      $self->{ResNum} = $$list[1];
      $self->{ResType} = $$list[2];
      $self->{AtomType} = $$list[3];
      $self->{Value} = $$list[4];
      }
    else
      { 
      my %params;
      %params = @_; 
      $self->{File} = $params{File};
      $self->{ResNum} = $params{ResNum};
      $self->{ResType} = $params{ResType};
      $self->{AtomType} = $params{AtomType};
      $self->{Value} = $params{Value};
      }
    }

  bless $self, $class;
  return $self;
  }


sub copy 
  {
  if (@_ != 2)
    { croak "Usage: \$ChemicalShift->copy(\$ChemicalShift);"; }

  my $this = shift @_;
  my $other = shift @_;

      $this->{File} = $other->{File};
      $this->{ResNum} = $other->{ResNum};
      $this->{ResType} = $other->{ResType};
      $this->{AtomType} = $other->{AtomType};
      $this->{Value} = $other->{Value};

  }

sub clone
  {
  if (@_ != 1)
    { croak "Usage: \$ChemicalShift->clone()"; }

  my $this = shift @_;
  my $temp = $this->new(1, 2, 3, 4, 5);
  $temp->copy($this);

  return $temp;
  }


sub AUTOLOAD
  {
  my $self = shift @_;
  my $type = ref($self) || croak "$self in not an object";
  my $name = $BMRB::ChemicalShift::AUTOLOAD;
  $name =~ s/.*://; # strip fully-qualified portion
  unless (exists $self->{$name})
    { croak "Can't access `$name' field in object of class $type"; }
  
  if (@_)
    { return $self->{$name} = shift @_; }
  
  return $self->{$name};
  }

# End Module with a return true.
return 1;
