#!/usr/bin/env bash

# Unify locale settings temporarily to make sort produce the same order
export LC_ALL=C

# Create temporary file to work on
TMPFILE=`mktemp`

# Converts uppercase to lowercase, sorts, removes duplicates and removes allowlisted domains
cat disposable_email_blocklist.conf | tr '[:upper:]' '[:lower:]' | sort -f | uniq -i  > $TMPFILE
comm -23 $TMPFILE allowlist.conf > disposable_email_blocklist.conf

rm $TMPFILE
echo "Done!"
