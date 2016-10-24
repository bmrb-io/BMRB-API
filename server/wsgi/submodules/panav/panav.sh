#!/bin/sh
if [ -z "$1" ] ; then
    echo "usage $0 <input file>"
    exit 1
fi

java -cp "panav.jar" CLI -f star -i "$1"
