#!/bin/bash
#
#  avs.sh is a shell script wrapper
# that runs the AutoPeak script validate_assignments.pl.
#
# INPUTS:
#
#	BMRB_FILE:  The NMR-STAR file to be validated.
#	STAR_FORMAT:  The format to be used for parsing
#	the input file.  Valid values are 2.1 and 3.0.
#
#
# OUTPUTS:
#
# This script will generate three output files:
#   1.  A file named AVS_full_<input_file>.txt.  This file will
#       contain the full output of validate_assignments.
#   2.  A file named AVS_anomalous_<input_file>.  This
#       file will contain only those chemical shifts
#       that have an overall status of Anomolous.
#
#   3.  A file named AVS_anomalous_<input_file>.ltr.  This
#       file will contain only those chemical shifts
#       that have an overall status of Anomolous and 
#	puts the format in the form of a letter to the
#	author. 

#  Set the AVS PATH to point to where AVS is installed.
AVS_PATH="."

if [ $# -ne 1 ]
then
  printf "\n\n USAGE:  $0 <bmrb star file name> [2.1 or 3.0 or 3.1]\n\n"
  exit 1
fi

BMRB_FILE=$1
BASE_BMRB_FILE=`echo $BMRB_FILE | cut -d. -f1`
STAR_FORMAT=$2
FULL_REPORT_FILE=AVS_full_$BASE_BMRB_FILE.txt
ANOMALOUS_FILE=AVS_anomalous_$BMRB_FILE
ANNO_LTR_FILE=AVS_anomalous_$BASE_BMRB_FILE.ltr

AVS_SCRIPT="${AVS_PATH}/validate_assignments_31.pl"

# echo "Using avs script:  " $AVS_SCRIPT

if [ -f $FULL_REPORT_FILE ]
then
   printf "File $FULL_REPORT_FILE already exists... overwrite it (y/n)? "
   read overwrite_val
   if [ $overwrite_val != "y" ]
   then
     printf "\n\nExiting.....\n\n"
     exit 1
   else
     printf "\n\n\tOverwriting file $FULL_REPORT_FILE\n\n" 
   fi
fi

echo "Starting the generation of $FULL_REPORT_FILE"
$AVS_SCRIPT  -nitrogen -fmean -aromatic -std $BMRB_FILE > $FULL_REPORT_FILE &

#
#  Generate anomalous report file.
#

if [ -f $ANOMALOUS_FILE ]
then
   printf "File $ANOMALOUS_FILE already exists... overwrite it (y/n)? "
   read overwrite_val
   if [ $overwrite_val != "y" ]
   then
     printf "\n\nExiting.....\n\n"
     exit 1
   else
     printf "\n\n\tOverwriting file $ANOMALOUS_FILE\n\n" 
   fi
fi
echo "Starting the generation of $ANOMALOUS_FILE"
$AVS_SCRIPT -nitrogen -fmean -aromatic -anomalous -std -star_output $BMRB_FILE > $ANOMALOUS_FILE &

#
#  Generate annotator letter for anomalous report file.
#

if [ -f $ANNO_LTR_FILE ]
then
   printf "File $ANNO_LTR_FILE already exists... overwrite it (y/n)? "
   read overwrite_val
   if [ $overwrite_val != "y" ]
   then
     printf "\n\nExiting.....\n\n"
     exit 1
   else
     printf "\n\n\tOverwriting file $ANNO_LTR_FILE\n\n" 
   fi
fi
echo "Starting the generation of $ANNO_LTR_FILE"
$AVS_SCRIPT -nitrogen -fmean -aromatic -std -anno_ltr $BMRB_FILE > $ANNO_LTR_FILE &

echo "All files are currently being generated.  This "
echo "may take several minutes.  Please wait."
echo

wait

# Check for Anomalous entries in anomalous report file.
ANOMALOUS_ENTRIES=`grep " Anomalous " $ANOMALOUS_FILE | head -1`

if [ -z "$ANOMALOUS_ENTRIES" ]
then
  printf "\n\nThere are no Anomalous entries in report file.\nNo anomalous report will be generated.\n\n"
  rm -f $ANOMALOUS_FILE
  # exit 0
else
  printf "\nFormating $ANOMALOUS_FILE...\n\t"
  java EDU.bmrb.starlibj.examples.passthru $ANOMALOUS_FILE
  if [ $? = 0 ]
  then
    mv $ANOMALOUS_FILE.1 $ANOMALOUS_FILE
  else
    printf "\nERROR!\n\n\tFormat error on file $BMRB_FILE.  Please check the file to ensure it is a valid NMR-STAR file.\n\n"
    rm -f $ANOMALOUS_FILE.1
  fi
fi

printf "\nProcessing complete.\n\n"

if [ -f $ANNO_LTR_FILE ]
then
   printf "\nAnnotator file generated as follows:\n\n"
   cat $ANNO_LTR_FILE
fi

exit 0
