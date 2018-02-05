#!/usr/bin/env python

"""Verify the integrity of the domain blacklist
"""

import sys

from publicsuffixlist import PublicSuffixList

def main(arguments):
    psl = PublicSuffixList()
    with open("disposable_email_blacklist", "r") as deb:
        for line in deb:
            if psl.publicsuffix(line) != line:
                print(f'The following line is a public suffix: {line} - please remove it from the blacklist file. See https://publicsuffix.org for details.')


if __name__ == "__main__":
    main(sys.argv)
