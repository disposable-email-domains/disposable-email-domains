#!/usr/bin/env python 

"""Verify the online DNS records of the domain blocklist
"""

import sys

import dns.resolver

blocklist = "disposable_email_blocklist.conf"
allowlist = "allowlist.conf"

dns_timeout_sec = 1

files = {
    filename: open(filename).read().splitlines() for filename in [allowlist, blocklist]
}

def check_dns(filename):
    invalid_dns = []
    lines = files[filename]
    for i, line in enumerate(lines):
        sys.stdout.flush()
        current_line = line.strip()
        try:
            records = dns.resolver.resolve(current_line, 'MX', raise_on_no_answer=False, lifetime=dns_timeout_sec)
        except dns.resolver.NXDOMAIN:
            # No MX found for domain
            sys.stdout.write("X")
            invalid_dns += [current_line]
            continue
        except dns.exception.Timeout:
            # Timeout querying domain
            sys.stdout.write("T")
            invalid_dns += [current_line]
            continue
        if len(records) == 0:
            # No MX record
            sys.stdout.write("M")
            invalid_dns += [current_line] 
            continue
        sys.stdout.write(".")
    print()
    if len(invalid_dns):
        print("Found invalid domains in DNS:")
        print("\n".join(invalid_dns))
        sys.exit(1)


if __name__ == "__main__":
    print("checking allowlist")
    check_dns(allowlist)
    print("checking denylist")
    check_dns(blocklist)


