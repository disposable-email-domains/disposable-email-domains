#!/usr/bin/env python

"""Verify the integrity of the domain blocklist"""

import io
import sys
import re
import logging
from collections import Counter
from publicsuffixlist import PublicSuffixList
from requests import get

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

blocklist = "disposable_email_blocklist.conf"
allowlist = "allowlist.conf"

files = {
    filename: open(filename).read().splitlines() for filename in [allowlist, blocklist]
}

def download_suffixes():
    with open("public_suffix_list.dat", "wb") as file:
        response = get("https://publicsuffix.org/list/public_suffix_list.dat")
        file.write(response.content)

def check_for_public_suffixes(filename):
    lines = files[filename]
    suffix_detected = False
    psl = None
    with open("public_suffix_list.dat", "r") as latest:
        psl = PublicSuffixList(latest)
    for i, line in enumerate(lines):
        current_line = line.split('#')[0].strip()  # Ignore comments
        if not current_line:
            continue
        public_suffix = psl.publicsuffix(current_line)
        if public_suffix == current_line:
            logging.error(f"The line number {i+1} contains just a public suffix: {current_line}")
            suffix_detected = True
    if suffix_detected:
        logging.error(
            "At least one valid public suffix found in {!r}, please "
            "remove it. See https://publicsuffix.org for details on why this "
            "shouldn't be blocklisted.".format(filename)
        )
        sys.exit(1)

def check_for_third_level_domains(filename):
    with open("public_suffix_list.dat", "r") as latest:
        psl = PublicSuffixList(latest)
    invalid = {
        line.split('#')[0].strip()
        for line in files[filename]
        if len(psl.privateparts(line.split('#')[0].strip())) > 1 and not line.startswith("#") and line.split('#')[0].strip()
    }
    if invalid:
        logging.error(f"The following domains contain a third or lower level domain in {!r}:")
        for line in sorted(invalid):
            logging.error(f"* {line}")
        sys.exit(1)

def check_for_non_lowercase(filename):
    lines = files[filename]
    invalid = {line.split('#')[0].strip() for line in lines if line.split('#')[0].strip() != line.split('#')[0].strip().lower() and not line.startswith("#") and line.split('#')[0].strip()}
    if invalid:
        logging.error(f"The following domains should be lowercased in {!r}:".format(filename))
        for line in sorted(invalid):
            logging.error(f"* {line}")
        sys.exit(1)

def check_for_duplicates(filename):
    lines = [line.split('#')[0].strip() for line in files[filename] if not line.startswith("#") and line.split('#')[0].strip()]
    count = Counter(lines) - Counter(set(lines))
    if count:
        logging.error(f"The following domains appear twice in {!r}:".format(filename))
        for line in sorted(count):
            logging.error(f"* {line}")
        sys.exit(1)

def check_sort_order(filename):
    lines = [line for line in files[filename] if not line.startswith("#") and line.split('#')[0].strip()]
    for a, b in zip(lines, sorted(lines)):
        if a != b:
            logging.error(f"The list is not sorted in {!r}:".format(filename))
            logging.error(f"* {b!r} should come before {a!r}")
            sys.exit(1)

def check_for_intersection(filename_a, filename_b):
    a = [line.split('#')[0].strip() for line in files[filename_a] if not line.startswith("#") and line.split('#')[0].strip()]
    b = [line.split('#')[0].strip() for line in files[filename_b] if not line.startswith("#") and line.split('#')[0].strip()]
    intersection = set(a) & set(b)
    if intersection:
        logging.error("The following domains appear in both lists:")
        for line in sorted(intersection):
            logging.error(f"* {line}")
        sys.exit(1)

def check_for_valid_domain_format(filename):
    domain_regex = re.compile(
        r"^(?:[a-zA-Z0-9]"  # First character of the domain
        r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)"  # Sub domain + hostname
        r"+[a-zA-Z]{2,6}$"  # First level TLD
    )
    lines = files[filename]
    invalid = {line.split('#')[0].strip() for line in lines if not domain_regex.match(line.split('#')[0].strip()) and not line.startswith("#") and line.split('#')[0].strip()}
    if invalid:
        logging.error(f"The following domains are invalid in {!r}:".format(filename))
        for line in sorted(invalid):
            logging.error(f"* {line}")
        sys.exit(1)

if __name__ == "__main__":
    # Download the list of public suffixes
    download_suffixes()

    # Check if any domains have a public suffix
    check_for_public_suffixes(blocklist)

    # Check if any domains are a third or lower level domain
    check_for_third_level_domains(blocklist)

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

    # Check if any domains are in an invalid format
    check_for_valid_domain_format(allowlist)
    check_for_valid_domain_format(blocklist)

    logging.info("All domain entries seem valid.")
