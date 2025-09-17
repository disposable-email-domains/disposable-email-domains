#!/usr/bin/env bash

# Unify locale settings temporarily to make sort produce the same order
export LC_ALL=C

# Converts uppercase to lowercase, sorts, removes duplicates and removes allowlisted domains
cat disposable_email_blocklist.conf | tr '[:upper:]' '[:lower:]' | sort -f | uniq -i  > temp.conf
comm -23 temp.conf allowlist.conf > disposable_email_blocklist.conf

rm temp.conf
echo "Done!"
