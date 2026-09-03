#!/usr/bin/env bash

# Unify locale settings temporarily to make sort produce the same order
export LC_ALL=C

TMPFILE=$(mktemp)

#Remove empty lines,  Convert uppercase to lowercase, sorts, removes duplicates
grep -v '^[[:space:]]*$' disposable_email_blocklist.conf \
| tr '[:upper:]' '[:lower:]' \
| sort -f \
| uniq -i > $TMPFILE

mv $TMPFILE disposable_email_blocklist.conf

echo "Done!"
