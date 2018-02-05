#!/usr/bin/env python

"""Verify the integrity of the domain blacklist
"""

import io
import sys

from publicsuffixlist import PublicSuffixList

def main(arguments):
    psl = PublicSuffixList()
    suffix_detected = False

    with io.open('disposable_email_blacklist.conf', 'r') as deb:
        for i, line in enumerate(deb):
            current_line = line.strip()
            public_suffix = psl.publicsuffix(current_line)
            if public_suffix == current_line:
                print(f'The line number {i+1} contains just a public suffix: {current_line}')
                suffix_detected = True
    if suffix_detected:
        print ('At least one valid public suffix found in the blacklist, please remove it. See https://publicsuffix.org for details on why this shouldn\'t be blacklisted.')
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
