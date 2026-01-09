#!/usr/bin/env python

"""Verify the integrity of the domain blocklist
"""

import io
import sys
from collections import Counter

from publicsuffixlist import PublicSuffixList
from requests import get


blocklist = "disposable_email_blocklist.conf"
allowlist = "allowlist.conf"

files = {
    filename: open(filename).read().splitlines() for filename in [allowlist, blocklist]
}


def download_suffixes():
    with open("public_suffix_list.dat", "wb") as file:
        response = get("https://publicsuffix.org/list/public_suffix_list.dat")
        file.write(response.content)


def check_for_public_suffixes(filename, psl, psl_local):
    """
    Check if any line in the given file is just a public suffix.
    Public suffixes are supplied from two sources: online database and local list.

    Exit with code 1 if any public suffix is found.

    :param filename: The name of the file to check.
    """
    lines = files[filename]
    suffix_detected = False
    for i, line in enumerate(lines):
        current_line = line.strip()
        public_suffix = psl.publicsuffix(current_line)
        if public_suffix == current_line:
            print(
                f"The line number {i+1} contains just a public suffix: {current_line}"
            )
            suffix_detected = True
        else:
            for psl_entry in psl_local:
                if psl_entry == current_line:
                    print(
                        f"The line number {i+1} contains just a public suffix (from local public suffix database): {current_line}"
                    )
                    suffix_detected = True

    if suffix_detected:
        print(
            "At least one valid public suffix found in {!r}, please "
            "remove it. See https://publicsuffix.org for details on why this "
            "shouldn't be blocklisted.".format(filename)
        )
        sys.exit(1)


def check_for_invalid_level_domains(filename, psl, psl_local):
    """
    Allow third or lower level domains in the list only if the entry contains a known public suffix
    and the length of the private part is 1.

    Public suffixes are supplied from two sources: online database and local list.
    """
    invalid = set()
    for line in files[filename]:
        domain = line.strip()
        parts = domain.split('.')
        public_valid = local_valid = False
        if len(psl.privateparts(domain)) == 1:
            public_valid = True
        for i in range(len(parts)):
            suffix = '.'.join(parts[i:])
            if suffix in psl_local:
                private_parts = parts[:i]
                if len(private_parts) == 1:
                    local_valid = True
                    break
        if not (public_valid or local_valid):
            invalid.add(line)

    if invalid:
        print("The following entries contain invalid third or lower level domain in {!r}:".format(filename))
        for line in sorted(invalid):
            print("* {}".format(line))
        sys.exit(1)


def check_for_non_lowercase(filename):
    lines = files[filename]
    invalid = set(lines) - set(line.lower() for line in lines)
    if invalid:
        print("The following domains should be lowercased in {!r}:".format(filename))
        for line in sorted(invalid):
            print("* {}".format(line))
        sys.exit(1)


def check_for_duplicates(filename):
    lines = files[filename]
    count = Counter(lines) - Counter(set(lines))
    if count:
        print("The following domains appear twice in {!r}:".format(filename))
        for line in sorted(count):
            print("* {}".format(line))
        sys.exit(1)


def check_sort_order(filename):
    lines = files[filename]
    for a, b in zip(lines, sorted(lines)):
        if a != b:
            print("The list is not sorted in {!r}:".format(filename))
            print("* {!r} should come before {!r}".format(b, a))
            sys.exit(1)


def check_for_intersection(filename_a, filename_b):
    a = files[filename_a]
    b = files[filename_b]
    intersection = set(a) & set(b)
    if intersection:
        print("The following domains appear in both lists:")
        for line in sorted(intersection):
            print("* {}".format(line))
        sys.exit(1)


if __name__ == "__main__":
    # Download the list of public suffixes
    download_suffixes()

    with open("publicsuffixlist.local", "r") as psl_local_file:
        psl_local = set(line.strip() for line in psl_local_file if line.strip())

    with open("public_suffix_list.dat", "r") as latest:
        psl = PublicSuffixList(latest)

    # Check if any domain is just a public suffix
    check_for_public_suffixes(blocklist, psl, psl_local)

    # Check if any domains contain invalid level
    check_for_invalid_level_domains(blocklist, psl, psl_local)

    # Check if any domains are not lowercase
    check_for_non_lowercase(allowlist)
    check_for_non_lowercase(blocklist)

    # Check if any domains are duplicated in the same list
    check_for_duplicates(allowlist)
    check_for_duplicates(blocklist)

    # Check if any lists are not sorted
    check_sort_order(allowlist)
    check_sort_order(blocklist)

    # Check if any domains are in both the allowlist and blocklist
    check_for_intersection(allowlist, blocklist)

    print("All domain entries seem valid.")
