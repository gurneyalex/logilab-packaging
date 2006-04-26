#!/bin/bash

if [ "$1" = "" -o "$1" = "--help" -o "$1" = "-h" ]; then
        echo "USAGE: update_gettext.sh <gettextid>"
        echo
        echo "move .mo files to their respective directory"
	echo "should be run in the directory where are located the .po file"
else
    for i in `ls *.po` ; do
	msgfmt.py $i
	base=`basename $i .po`
	mv $base.mo $base/LC_MESSAGES/$1.mo
    done
fi