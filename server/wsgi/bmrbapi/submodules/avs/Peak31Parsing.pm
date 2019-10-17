package Peak30Parsing;

#
#   Author:     Gurmukh Sahota 07/15/2000
#   Copyright:  Gurmukh Sahota, 2000. All rights reserved.
#
#   Updated:  Gurmukh Sahota 04/15/2001
#             Added PAL, PRL and notes as well as the assignment parsing.
#
#
#  Hunter Moseley: Modified at various times over 2002-2005
#

# Returns a reference to a Array     of  a Hash      of an Array
#                          Residue  :::  AtomTypes  :::  possible chemical shifts

require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw();
@EXPORT_OK = qw( parsePeakfile outputPeakfile outputSparkyPeakfile parseSparkyPeakfile translate_sparky_name );
%EXPORT_TAGS = ( ALL => [@EXPORT_OK] );                                                   

# allows perl to fine local modules.
use FindBin;
use lib $FindBin::Bin;

use strict;


########################################## parsePeakfile #########################################################
# Input   : filename and tokens ie. dimensions used. Explained below                                             #
# Output  : A reference to a peakfile hash                                                                       #
#                $peakfile_hlist - reference to a hash                                                           #
#               $$peakfile_hlist{"filename"}    - peaklist's filename                                            #
#               $$peakfile_hlist{"dimlist"}      - the tokens of the peaklist or the dimension                   #
#                                                 names (HN, N15, CX)                                            #
#               $$peakfile_hlist{"internal_comments"}    - the comments in the peaklist, lines                   #
#                                                 starting with a #                                              #
#               $$peakfile_hlist{"end_comments"} - The filehistory created by some of the                        #
#                                                 AutoAssign Scripts                                             #
#               $$peakfile_hlist{"plist"}       - Hash list of index to the shifts and                           #
#                                                 intensity and workbooks                                        #
#               $peakfile_row = $$peakfile_hlist{"plist"}{indexnumber}                                           #
#                                                                                                                #
#                               $$peakfile_row{"shifts"}{token}               - shift value of the token         #
#                               $$peakfile_row{"intensity"}                   - intensity of the peak            #
#                               $$peakfile_row{"workbookname"}                - workbook name of the peak        #
#                               $$peakfile_row{"assign"}{"residue"}           - residue assignment of peak       #
#                               $$peakfile_row{"assign"}{"atomtype"}{"list"}  - atomType list for the assignment #
#                               $$peakfile_row{"PRL"}{"list"}                 - Possible Residue List(array)     #
#                               $$peakfile_row{"PAL"}{"list"}                 - Possible AtomType List(array)    #
#                                                                                                                #
# Purpose : To parse the input peakfile and return the described data structure                                  #
##################################################################################################################

sub parsePeakfile

  { #===== begin parsePeakfile =====#
    my $infile = shift @_;
    my @tokens = @_;

    my @input = ();
    my $count = 0;
    my $line;

    my $peakfile_hlist = {};
    $$peakfile_hlist{"internal_comments"}    = '';
    $$peakfile_hlist{"end_comments"} = '';

    # open the file for input
     local *IN;
     if ($infile =~ /^\-$/)
     {
	 *IN = *STDIN;
     }
     else
     {
	 open(IN, "<$infile");
     }
    # save the input parameters in the hash for future reference
    $$peakfile_hlist{"filename"} = $infile;
    $$peakfile_hlist{"dimlist"} = \@tokens;
    
    # while you do not hit the eof or catch a * do the following
    while ($line = <IN>)
      { 
	# save the comments and push the other lines on to an input array.
	if ($line =~ /^\*/)     {last;}
	elsif ($line =~ /^\#/)  {$$peakfile_hlist{"internal_comments"} .= $line;} 
	else                    {push (@input, $line);} 
      }
    
    # while there are extra lines, we will assume that they are file history lines
    while ($line = <IN>)
      {   
	$$peakfile_hlist{"end_comments"} .= $line; 
      } 

    # close the file
    close(IN);
    
    # while there are elements left in the input array
    while (@input > 0)
      {
	# pull off the next line
	$line = shift @input;

	# as long as the line is not empty or just spaces do
	if ($line !~ /^\s*$/)
	  {
	    # split the line on the spaces
	    my @chemical_shifts = split(/\s+/, $line);

	    # we assume that the first column is the index 
	    my $index = shift @chemical_shifts;

	    # the token columns are stored
	    for ($count=0; $count < @tokens; $count++)
	      {
		$$peakfile_hlist{"plist"}{$index}{"shifts"}{$tokens[$count]} = $chemical_shifts[$count];
	      }

	    # we assume that the next two columns will be intensity and the workbook name
	    $$peakfile_hlist{"plist"}{$index}{"intensity"} = $chemical_shifts[$count++];
	    $$peakfile_hlist{"plist"}{$index}{"workbookname"} = $chemical_shifts[$count++];
	    if ($$peakfile_hlist{"plist"}{$index}{"workbookname"} =~ /^(.*?)\.(\w\d+)\.?(.*?)\.(.*?)$/)
	    {
		$$peakfile_hlist{"plist"}{$index}{"assign"}{"residue"} = $2;
		@ {$$peakfile_hlist{"plist"}{$index}{"assign"}{"atomtype"}{"list"}} = (split /\_/, $3);
#		print "$index >> ", $$peakfile_hlist{"plist"}{$index}{"assign"}{"residue"}, "  :: (", join(", ", @ {$$peakfile_hlist{"plist"}{$index}{"assign"}{"atomtype"}{"list"}}), ")\n";
	    }
	    # We will assume that the note corresponds to a Possible Residue List
		while ( $$peakfile_hlist{"plist"}{$index}{"workbookname"} =~ /\{(\-?\d+),(.*?)\}/g)
		{
		    my $list_type = $1;
		    # PRL is a CSV list
		    @{$$peakfile_hlist{"plist"}{$index}{"PRL"}{$list_type}{"list"}} = split(/\,/, $2);
		    foreach my $elem (@{$$peakfile_hlist{"plist"}{$index}{"PRL"}{$list_type}{"list"}})
		    {
			$elem = uc($elem);
		    }
		    # Make sure something was in there ...
		    delete $$peakfile_hlist{"plist"}{$index}{"PRL"}{$list_type}{"list"} if (!(@{$$peakfile_hlist{"plist"}{$index}{"PRL"}{$list_type}{"list"}}));
#		    print $1, "\t", @{$$peakfile_hlist{"plist"}{$index}{"PRL"}{$list_type}{"list"}}, "\n";
		}

		if ($$peakfile_hlist{"plist"}{$index}{"workbookname"}  =~ /\[(.*?)\]/)
		{
		    # PAL is a CSV list
		    @{$$peakfile_hlist{"plist"}{$index}{"PAL"}{"list"}} = split(/\,/, $1);

		    foreach my $elem (@{$$peakfile_hlist{"plist"}{$index}{"PAL"}{"list"}})
		    {
			$elem = uc($elem);
		    }
		    # Make sure something was in there ...
		    delete $$peakfile_hlist{"plist"}{$index}{"PAL"}{"list"} if (!(@{$$peakfile_hlist{"plist"}{$index}{"PAL"}{"list"}}));
		}
	}
    }
    
    # returned the datastructure
    return $peakfile_hlist;

  } #===== end   parsePeakfile =====#			       


######################################### outputPeakfile #########################################################
# Input   : A reference to a peakfile hash                                                                       #
#                $peakfile_hlist - reference to a hash                                                           #
#               $$peakfile_hlist{"filename"}    - peaklist's filename                                            #
#               $$peakfile_hlist{"dimlist"}      - the tokens of the peaklist or the dimension                   #
#                                                 names (HN, N15, CX)                                            #
#               $$peakfile_hlist{"internal_comments"}    - the comments in the peaklist, lines                   #
#                                                 starting with a #                                              #
#               $$peakfile_hlist{"end_comments"} - The filehistory created by some of the                        #
#                                                 AutoAssign Scripts                                             #
#               $$peakfile_hlist{"plist"}       - Hash list of index to the shifts and                           #
#                                                 intensity and workbooks                                        #
#               $peakfile_row = $$peakfile_hlist{"plist"}{indexnumber}                                           #
#                                                                                                                #
#                               $$peakfile_row{"shifts"}{token}               - shift value of the token         #
#                               $$peakfile_row{"intensity"}                   - intensity of the peak            #
#                               $$peakfile_row{"workbookname"}                - workbook name of the peak        #
#                               $$peakfile_row{"assign"}{"residue"}           - residue assignment of peak       #
#                               $$peakfile_row{"assign"}{"atomtype"}{"list"}  - atomType list for the assignment #
#                               $$peakfile_row{"PRL"}{"list"}                 - Possible Residue List(array)     #
#                               $$peakfile_row{"PAL"}{"list"}                 - Possible AtomType List(array)    #
#                               $$peakfile_row{"notes"}                       - notes about a specific peak      #
#                                                                                                                #
# Output  : A peakfile                                                                                           # 
# Purpose : To output the described data structure                                                               #
##################################################################################################################

sub outputPeakfile

  { #===== begin outputPeakfile =====#
      my $peakfile_hlist = shift @_;
      my $filename = shift @_;
      
      $filename = $$peakfile_hlist{"filename"}      if ($filename eq '');
      local *OUTFILE;
      if (($filename eq "-") || ($filename eq ''))
	 { *OUTFILE = *STDOUT; }
      else
	 { open (OUTFILE, ">$filename") || die "unable to open $filename"; }
      

      print OUTFILE "#Index\t";
      for (my $x = 0; $x < @{$$peakfile_hlist{"dimlist"}}; $x++)
	  {
	      print OUTFILE $x+1 , "Dim\t";
	  }
      print OUTFILE "Intensity\tWorkbook\n";

      foreach my $index (sort { $a <=> $b } (keys %{$$peakfile_hlist{"plist"}}))
	  {
	      print OUTFILE "$index\t";
	      foreach my $token (@{$$peakfile_hlist{"dimlist"}})
		  {
		      print OUTFILE $$peakfile_hlist{"plist"}{$index}{"shifts"}{$token}, "\t";
		  }
	      print OUTFILE $$peakfile_hlist{"plist"}{$index}{"intensity"}, "\t", $$peakfile_hlist{"plist"}{$index}{"workbookname"};
	      if (exists $$peakfile_hlist{"plist"}{$index}{"PRL"})
	      {
		  print OUTFILE "!!{", join(",", $$peakfile_hlist{"plist"}{$index}{"PRL"}{"list"}), "\}!!";
	      }
	      
	      if (exists $$peakfile_hlist{"plist"}{$index}{"PAL"})
	      {
		  print OUTFILE "!![", join(",", $$peakfile_hlist{"plist"}{$index}{"PAL"}{"list"}), "\]!!";
	      }

	      print OUTFILE "\n";

	  }
      print OUTFILE "*\n";
      print OUTFILE $$peakfile_hlist{"internal_comments"}, "\n";
      print OUTFILE $$peakfile_hlist{"end_comments"}, "\n";

      return;
  }

sub outputSparkyPeakfile
  { 
  my $peakfile_hlist = shift @_;
  my $filename = shift @_;
  my $print_intensity = 0;
  if (@_)
    { $print_intensity = shift @_; }
  
  $filename = $$peakfile_hlist{"filename"}      if ($filename eq '');
  local *OUTFILE;
  if (($filename eq "-") || ($filename eq ''))
    { *OUTFILE = *STDOUT; }
  else
    { open (OUTFILE, ">$filename") || die "unable to open $filename"; }
  
  foreach my $index (sort { $a <=> $b } (keys %{$$peakfile_hlist{"plist"}}))
    {
    my $sparky_name = "";
    if (exists $$peakfile_hlist{"plist"}{$index}{"sparky_name"})
      { $sparky_name = $$peakfile_hlist{"plist"}{$index}{"sparky_name"}; }
    else
      {
      for(my $x=0; $x+1 < @{$$peakfile_hlist{"dimlist"}}; $x++)
	{ $sparky_name .= "?-"; }
      
      $sparky_name .= "?";
      }
    
    printf OUTFILE "%15s \t", $sparky_name;
    foreach my $token (@{$$peakfile_hlist{"dimlist"}})
      { print OUTFILE $$peakfile_hlist{"plist"}{$index}{"shifts"}{$token}, " \t"; }
    
    if ($print_intensity)
      { print OUTFILE $$peakfile_hlist{"plist"}{$index}{"intensity"}, " \t"; }

    if (exists $$peakfile_hlist{"plist"}{$index}{"sparky_note"})
      { print OUTFILE $$peakfile_hlist{"plist"}{$index}{"sparky_note"}; }
    
    print OUTFILE "\n";
    
    }
  
  return;
  }


sub parseSparkyPeakfile

  { #===== begin parsePeakfile =====#
    my $infile = shift @_;
    my $missing_intensity = 0;
    if (@_)
      { $missing_intensity = shift @_; }

    my $count = 0;
    my $line;

    my $sparky_peakfile_hlist = {};

    # open the file for input
     local *IN;
     if ($infile =~ /^\-$/)
     {
	 *IN = *STDIN;
     }
     else
     {
	 open(IN, "<$infile");
     }
    # save the input parameters in the hash for future reference
    $$sparky_peakfile_hlist{"filename"} = $infile;

    my @input = <IN>;
    close(IN);
    @input = grep { $_ !~ /^\s*$/; } (@input);

    my @tokens;
    if ($input[0] =~ /Assignment/)
      {
      my $header_line = shift @input;
      $header_line =~ s/^\s+//;
      $header_line =~ s/\s+$//;
      @tokens = split /\s+/, $header_line;
      shift @tokens; # Assignment
      pop @tokens;   # Height
      if (! $missing_intensity)
	{ pop @tokens; }  # Data
      }
    else
      {
      my $test = $input[0];
      $test =~ s/^\s+//;
      $test =~ s/\s+$//;
      my $count = 1;
      foreach my $item (split(/\s+/, $test))
	{ 
	if ($item != 0.0) 
	  { push @tokens, "D" . $count++; }
	}
      if (! $missing_intensity)
	{ pop @tokens; } # last numeric item is intensity.
      }

    $$sparky_peakfile_hlist{"dimlist"} = [ @tokens ];

    
    my $index=1;
    while (@input)
      {	# pull off the next line
      $line = shift @input;
      $line =~ s/^\s+//;
      $line =~ s/\s+$//;
      
      my @chemical_shifts = split(/\s+/, $line);
      
      if (($chemical_shifts[0] == 0.0) && ($chemical_shifts[0] =~ /[-]/))
	{ $$sparky_peakfile_hlist{"plist"}{$index}{"sparky_name"} = shift @chemical_shifts; }
      
      my $count=0;
      while (@chemical_shifts)
	{
	last if ($count > $#tokens);
	$$sparky_peakfile_hlist{"plist"}{$index}{"shifts"}{$tokens[$count]} = shift @chemical_shifts;
	$count++;
	}
      
      if (! $missing_intensity)
	{ $$sparky_peakfile_hlist{"plist"}{$index}{"intensity"} = shift @chemical_shifts; }
      
      # we assume that the remaining columns will be the workbook name
      if (@chemical_shifts)
	{ $$sparky_peakfile_hlist{"plist"}{$index}{"sparky_note"} = shift @chemical_shifts; }
      
      $index++;
      }
    
    # returned the datastructure
    return $sparky_peakfile_hlist;

  } #===== end   parsePeakfile =====#			       



sub translate_sparky_name
  {
  my $string = shift @_;

  if ($string =~ /[?]-[?]/)
    { return ""; }

  my $assignments = [];
  my $last_res_type;
  my $last_res_num;
  my @test_dims = split("-",$string);
  for(my $x=0; $x < @test_dims; $x++)
    {
    if ($test_dims[$x] =~ /^(\w)([-]?\d+)(\w+)$/)
      { 
      push @$assignments, { "res_type" => $1, "res_num" => $2, "atom_type" => $3, "res_name" => $1 . $2 }; 
      $last_res_type = $1;
      $last_res_num = $2;
      }
    elsif ($test_dims[$x] =~ /^(\w+)$/)
      { push @$assignments, { "res_type" => $last_res_type, "res_num" => $last_res_num, "atom_type" => $1, "res_name" => $last_res_type . $last_res_num }; }
    else
      { push @$assignments, {}; }
    }

  return $assignments;
  }
