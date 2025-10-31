#!/usr/bin/env python

"""Fetch domains from various sources and add missing ones to the blocklist"""

import re
import sys
from typing import Set

from bs4 import BeautifulSoup
from requests import get
from publicsuffixlist import PublicSuffixList


def extract_domains_from_text(text: str) -> Set[str]:
    """Extract domains from text content (handles @domain format)"""
    domains = set()
    
    # Extract domains that follow an @ symbol
    domain_pattern = r'@([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,})'
    matches = re.findall(domain_pattern, text)
    domains.update(m.lower() for m in matches)
    
    # Also check for standalone domains in lines with @ symbols
    for line in text.split('\n'):
        if '@' in line and '.' in line:
            parts = line.split('@')
            for part in parts:
                part = part.strip()
                if part and '.' in part:
                    domain_match = re.match(r'^([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,})', part)
                    if domain_match:
                        domain = domain_match.group(1).lower()
                        domains.add(domain)
    
    return domains


class DomainFetcher:
    """Base class for domain fetchers"""
    
    def __init__(self, name: str):
        self.name = name
    
    def fetch(self) -> Set[str]:
        """Fetch domains from the source. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement fetch()")
    
    def get_name(self) -> str:
        """Get the name of this fetcher"""
        return self.name


class YopmailFetcher(DomainFetcher):
    """Fetcher for Yopmail disposable email domains"""
    
    def __init__(self):
        super().__init__("Yopmail")
        self.url = "https://yopmail.com/en/domain?d=list"
    
    def fetch(self) -> Set[str]:
        """Fetch domains from Yopmail endpoint"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()
        
        # Extract domains from the text content
        domains = extract_domains_from_text(text)
        
        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)
        
        return domains


def load_existing_domains(filename: str) -> Set[str]:
    """Load existing domains from blocklist file"""
    try:
        with open(filename, 'r') as f:
            return set(line.strip().lower() for line in f if line.strip())
    except FileNotFoundError:
        print(f"Warning: {filename} not found, starting with empty list", file=sys.stderr)
        return set()


def add_domains_to_blocklist(new_domains: Set[str], filename: str, source_name: str = "") -> int:
    """Add new domains to the blocklist file (appends at the end)"""
    existing = load_existing_domains(filename)
    missing = new_domains - existing
    
    if not missing:
        if source_name:
            print(f"No new domains to add from {source_name}.")
        else:
            print("No new domains to add.")
        return 0
    
    print(f"Found {len(missing)} new domains to add from {source_name}:")
    for domain in sorted(missing):
        print(f"  + {domain}")
    
    # Merge with existing and write back sorted alphabetically (case-insensitive)
    merged = existing | set(d for d in missing if d)
    with open(filename, 'w') as f:
        for domain in sorted(merged, key=lambda s: s.lower()):
            f.write(f"{domain}\n")
    
    return len(missing)


# Registry of all domain fetchers
FETCHERS = [
    YopmailFetcher(),
    # Add more fetchers here in the future
    # Example: AnotherFetcher(),
]


def main():
    """Main function to run all registered domain fetchers"""
    blocklist_file = "disposable_email_blocklist.conf"
    psl = None
    # Load the public suffix list once, to filter out subdomains
    try:
        resp = get("https://publicsuffix.org/list/public_suffix_list.dat", timeout=30)
        resp.raise_for_status()
        psl = PublicSuffixList(resp.text.splitlines())
    except Exception as e:
        print(f"Error loading Public Suffix List: {e}", file=sys.stderr)
        sys.exit(1)
    
    total_added = 0
    sources_processed = 0
    
    for fetcher in FETCHERS:
        print(f"\n=== Fetching domains from {fetcher.get_name()} ===")
        try:
            raw_domains = fetcher.fetch()
            # Keep only second-level domains (no third-or-lower level subdomains)
            filtered_domains: Set[str] = set()
            for d in raw_domains:
                dd = d.strip().lower()
                if not dd:
                    continue
                privateparts = psl.privateparts(dd)
                # Include only domains that are not subdomains (exactly one private part)
                if privateparts is not None and len(privateparts) == 1:
                    # Also exclude pure public suffixes
                    if psl.publicsuffix(dd) != dd:
                        filtered_domains.add(dd)
            domains = filtered_domains
            print(f"Found {len(domains)} domains from {fetcher.get_name()}")
            
            if domains:
                added = add_domains_to_blocklist(domains, blocklist_file, fetcher.get_name())
                total_added += added
                sources_processed += 1
            else:
                print(f"No domains found from {fetcher.get_name()}")
        except Exception as e:
            print(f"Error processing {fetcher.get_name()}: {e}", file=sys.stderr)
            continue
    
    print(f"\n=== Summary ===")
    print(f"Processed {sources_processed} source(s)")
    print(f"Total new domains added: {total_added}")
    
    if total_added > 0:
        print(f"\nSuccessfully added {total_added} new domains.")
        sys.exit(0)
    else:
        print("\nNo new domains to add.")
        sys.exit(0)


if __name__ == "__main__":
    main()

