#!/usr/bin/env python3

"""Verify or fix the integrity of the domain blocklist

Usage:
    python verify.py           # Check validity (exit 1 if issues found)
    python verify.py --fix     # Auto-fix issues and write corrected file
"""

import argparse
import sys
from collections import Counter

from publicsuffixlist import PublicSuffixList
from requests import get


blocklist = "disposable_email_blocklist.conf"

files = {
    filename: open(filename).read().splitlines() for filename in [blocklist]
}


def download_suffixes():
    with open("public_suffix_list.dat", "wb") as file:
        response = get("https://publicsuffix.org/list/public_suffix_list.dat")
        file.write(response.content)


def is_public_suffix(domain, psl, psl_local):
    """Check if domain is a public suffix from either source."""
    if psl.publicsuffix(domain) == domain:
        return True
    return domain in psl_local


def is_valid_level_domain(domain, psl, psl_local):
    """Check if domain has valid level (second-level or valid third-level)."""
    parts = domain.split('.')
    private_parts = psl.privateparts(domain)
    if private_parts and len(private_parts) == 1:
        return True
    for i in range(len(parts)):
        suffix = '.'.join(parts[i:])
        if suffix in psl_local:
            private_parts = parts[:i]
            if len(private_parts) == 1:
                return True
    return False


def check_for_public_suffixes(filename, psl, psl_local):
    """
    Check if any line in the given file is just a public suffix.
    Returns set of problematic lines.
    """
    lines = files[filename]
    problematic = set()
    for line in lines:
        current_line = line.strip()
        if is_public_suffix(current_line, psl, psl_local):
            problematic.add(line)
    return problematic


def check_for_invalid_level_domains(filename, psl, psl_local):
    """
    Check for invalid third-or-lower level domains.
    Returns set of problematic lines.
    """
    invalid = set()
    for line in files[filename]:
        domain = line.strip()
        if not is_valid_level_domain(domain, psl, psl_local):
            invalid.add(line)
    return invalid


def check_for_non_lowercase(filename):
    """Check for non-lowercase entries. Returns dict mapping bad->correct."""
    lines = files[filename]
    corrections = {}
    for line in lines:
        lower = line.lower()
        if line != lower:
            corrections[line] = lower
    return corrections


def check_for_duplicates(filename):
    """Check for duplicates. Returns list of duplicate lines."""
    lines = files[filename]
    seen = set()
    duplicates = []
    for line in lines:
        if line in seen:
            duplicates.append(line)
        else:
            seen.add(line)
    return duplicates


def check_sort_order(filename):
    """Check sort order. Returns True if unsorted."""
    lines = files[filename]
    sorted_lines = sorted(lines, key=str.lower)
    return lines != sorted_lines


def fix_invalid_level(domain, psl, psl_local):
    """Try to fix an invalid level domain by removing leftmost parts until valid."""
    parts = domain.split('.')
    for i in range(1, len(parts) - 1):  # Keep at least 2 parts
        candidate = '.'.join(parts[i:])
        if is_valid_level_domain(candidate, psl, psl_local):
            return candidate
    return None


def fix_blocklist(psl, psl_local):
    """Apply fixes to the blocklist file."""
    lines = files[blocklist][:]  # Copy original
    lines = [line.lower() for line in lines] # Lowercase
    lines = [line for line in lines if line.strip()] # Remove empty

    public_suffixes_found = set()
    invalid_levels_fixed = {}
    invalid_levels_removed = set()

    result_lines = []
    for line in lines:
        if is_public_suffix(line, psl, psl_local):
            public_suffixes_found.add(line)
            continue

        if not is_valid_level_domain(line, psl, psl_local):
            fixed = fix_invalid_level(line, psl, psl_local)
            if fixed:
                invalid_levels_fixed[line] = fixed
                result_lines.append(fixed)
            else:
                invalid_levels_removed.add(line)
            continue

        result_lines.append(line)

    if public_suffixes_found:
        print(f"Removed {len(public_suffixes_found)} public suffix(es):")
        for ps in sorted(public_suffixes_found):
            print(f"  - {ps}")

    if invalid_levels_fixed:
        print(f"Fixed {len(invalid_levels_fixed)} invalid level domain(s) by trimming:")
        for bad, good in sorted(invalid_levels_fixed.items()):
            print(f"  - {bad} -> {good}")

    if invalid_levels_removed:
        print(f"Removed {len(invalid_levels_removed)} unfixable invalid level domain(s):")
        for il in sorted(invalid_levels_removed):
            print(f"  - {il}")

    lines = result_lines

    # Remove dups
    seen = set()
    unique_lines = []
    duplicates_found = 0
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)
        else:
            duplicates_found += 1

    if duplicates_found:
        print(f"Removed {duplicates_found} duplicate(s)")

    # Sort
    unique_lines.sort(key=str.lower)

    # Write back
    with open(blocklist, 'w') as f:
        for line in unique_lines:
            f.write(line + '\n')

    total_fixed = len(public_suffixes_found) + len(invalid_levels_fixed) + len(invalid_levels_removed) + duplicates_found
    print(f"\nFixed {total_fixed} issue(s), wrote {len(unique_lines)} valid domain(s) to {blocklist}")


def main():
    parser = argparse.ArgumentParser(description='Verify the integrity of the domain blocklist')
    parser.add_argument('--fix', action='store_true', help='Auto-fix issues and write corrected file')
    args = parser.parse_args()

    download_suffixes()

    with open("publicsuffixlist.local", "r") as psl_local_file:
        psl_local = set(line.strip() for line in psl_local_file if line.strip())

    with open("public_suffix_list.dat", "r") as latest:
        psl = PublicSuffixList(latest)

    public_suffixes = check_for_public_suffixes(blocklist, psl, psl_local)
    invalid_levels = check_for_invalid_level_domains(blocklist, psl, psl_local)
    non_lowercase = check_for_non_lowercase(blocklist)
    duplicates = check_for_duplicates(blocklist)
    unsorted = check_sort_order(blocklist)

    has_issues = (public_suffixes or invalid_levels or non_lowercase or duplicates or unsorted)

    if not has_issues:
        print("All domain entries seem valid.")
        return 0

    # Report issues
    if public_suffixes:
        print(f"The following {len(public_suffixes)} entries are public suffixes:")
        for line in sorted(public_suffixes):
            print(f"  * {line}")

    if invalid_levels:
        print(f"The following {len(invalid_levels)} entries have invalid domain levels:")
        for line in sorted(invalid_levels):
            print(f"  * {line}")

    if non_lowercase:
        print(f"The following {len(non_lowercase)} entries should be lowercased:")
        for bad, good in sorted(non_lowercase.items()):
            print(f"  * {bad} -> {good}")

    if duplicates:
        print(f"The following {len(duplicates)} entries appear multiple times:")
        for line in sorted(set(duplicates)):
            count = duplicates.count(line)
            print(f"  * {line} ({count} times)")

    if unsorted:
        print("The list is not sorted alphabetically.")

    # Fix issues
    if args.fix:
        print("\nApplying fixes...")
        fix_blocklist(psl, psl_local)
        return 0
    else:
        print("\nUse --fix to automatically correct these issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
