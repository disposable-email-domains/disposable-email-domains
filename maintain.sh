#!/usr/bin/env bash

# Unify locale settings temporarily to make sort produce the same order
export LC_ALL=C

# Converts uppercase to lowercase, sorts, removes duplicates
cat disposable_email_blocklist.conf | tr '[:upper:]' '[:lower:]' | sort -f | uniq -i  > disposable_email_blocklist.conf

echo "Done!"
