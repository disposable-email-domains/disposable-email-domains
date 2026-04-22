#!/usr/bin/env bash

# Unify locale settings temporarily to make sort produce the same order
export LC_ALL=C

TMPFILE=$(mktemp)

# Converts uppercase to lowercase, sorts, removes duplicates
cat disposable_email_blocklist.conf | tr '[:upper:]' '[:lower:]' | sort -f | uniq -i > $TMPFILE

mv $TMPFILE disposable_email_blocklist.conf

echo "Done!"
