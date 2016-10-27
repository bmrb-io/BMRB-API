#!/bin/sh

BMRB_FILE=$1
AVS_SCRIPT="./validate_assignments_31.pl"

#echo "Starting the generation of $FULL_REPORT_FILE"
#$AVS_SCRIPT  -nitrogen -fmean -aromatic -std $BMRB_FILE | less

#
#  Generate anomalous report file.
#
#echo "Starting the generation of $ANOMALOUS_FILE"
$AVS_SCRIPT -nitrogen -fmean -aromatic -anomalous -std -star_output $BMRB_FILE | less

#
#  Generate annotator letter for anomalous report file.
#
#echo "Starting the generation of $ANNO_LTR_FILE"
$AVS_SCRIPT -nitrogen -fmean -aromatic -std -anno_ltr $BMRB_FILE | less

# Check for Anomalous entries in anomalous report file.
#ANOMALOUS_ENTRIES=`grep " Anomalous " $ANOMALOUS_FILE | head -1`
#echo $ANOMALOUS_ENTRIES

exit

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
