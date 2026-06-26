#!/usr/bin/env python

"""Fetch domains from various sources and add missing ones to the blocklist"""

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set

from bs4 import BeautifulSoup
from requests import get, post
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
    """Fetcher for 'yopmail com' disposable email domains """

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


class TmailFetcher(DomainFetcher):
    """Fetcher for 'tmail gg' disposable email domains """

    def __init__(self):
        super().__init__("Tmail")
        self.url = "http://45.207.211.187:1234/api/domains"

    def fetch(self) -> Set[str]:
        """Fetch domains from Tmail endpoint"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        # Parse JSON
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from {self.name}: {e}", file=sys.stderr)
            return set()

        domains = set()
        if "data" in data and "domains" in data["data"]:
            for domain in data["data"]["domains"]:
                if isinstance(domain, str) and domain:
                    domains.add(domain.lower())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class YoursToolsFetcher(DomainFetcher):
    """Fetcher for 'yours tools' disposable email domains"""

    def __init__(self):
        super().__init__("YoursTools")
        self.url = "https://apis.kyfudao.com/apis.php"

    def fetch(self) -> Set[str]:
        """Fetch domains from YoursTools endpoint"""
        try:
            response = post(self.url, timeout=30, data={"ajax": "get_domains"})
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        # Parse JSON
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from {self.name}: {e}", file=sys.stderr)
            return set()

        domains = set()
        if "domains" in data:
            for domain in data["domains"]:
                if isinstance(domain, str) and domain:
                    domains.add(domain.lower())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class NoopmailFetcher(DomainFetcher):
    """Fetcher for 'noopmail org' disposable email domains"""

    def __init__(self):
        super().__init__("Noopmail")
        self.url = "http://103.166.182.97:8080/api/d"

    def fetch(self) -> Set[str]:
        """Fetch domains from Noopmail endpoint"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        # Parse JSON
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from {self.name}: {e}", file=sys.stderr)
            return set()

        domains = set()
        if isinstance(data, list):
            for domain in data:
                if isinstance(domain, str) and domain:
                    domains.add(domain.lower())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class GPTMailFetcher(DomainFetcher):
    """Fetcher for `mail chatgpt org uk` disposable email domains"""

    def __init__(self):
        super().__init__("GPTMail")
        self.url = "https://mail.chatgpt.org.uk/api/domains/status"

    def fetch(self) -> Set[str]:
        """Fetch domains from GPTMail domains status API"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        # Parse JSON
        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from {self.name}: {e}", file=sys.stderr)
            return set()

        domains = set()
        if "success" in data and data["success"] and "data" in data:
            domain_data = data["data"]
            # Handle both list format and object with domains array
            if isinstance(domain_data, list):
                for entry in domain_data:
                    if isinstance(entry, dict) and "domain_name" in entry:
                        domain = entry["domain_name"].lower().strip()
                        if domain:
                            domains.add(domain)
            elif isinstance(domain_data, dict) and "domains" in domain_data:
                for entry in domain_data["domains"]:
                    if isinstance(entry, dict) and "domain_name" in entry:
                        domain = entry["domain_name"].lower().strip()
                        if domain:
                            domains.add(domain)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains

class TinyhostFetcher(DomainFetcher):
    """Fetcher for `tinyhost shop` disposable email domains"""

    def __init__(self):
        super().__init__("Tinyhost")
        self.url = "https://tinyhost.shop/api/all-domains/"

    def fetch(self) -> Set[str]:
        """Fetch all online domains from the Tinyhost API"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from {self.name}: {e}", file=sys.stderr)
            return set()

        domains = set()
        if isinstance(data, dict) and "domains" in data:
            for domain in data["domains"]:
                domain = domain.lower().strip()
                if domain:
                    domains.add(domain)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)
        return domains


class GeneratorEmailFetcher(DomainFetcher):
    """Fetcher for 'generator.email' disposable email domains"""

    def __init__(self):
        super().__init__("GeneratorEmail")
        self.url = "https://generator.email/"

    def _fetch_once(self, attempt: int, domain_pattern: "re.Pattern") -> Set[str]:
        """Fetch and parse domains from a single page load"""
        domains = set()
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains (attempt {attempt + 1}): {e}", file=sys.stderr)
            return domains

        soup = BeautifulSoup(response.text, "html.parser")

        # Domains appear as <li> items in the domain dropdown list
        for li in soup.find_all("li"):
            text = li.get_text(strip=True).lower()
            if domain_pattern.match(text):
                domains.add(text)

        # Fallback: domains also appear in <p onclick="change_dropdown_list(...)">
        for p in soup.find_all("p", onclick=re.compile("change_dropdown_list")):
            text = p.get_text(strip=True).lower()
            if domain_pattern.match(text):
                domains.add(text)

        return domains

    def fetch(self) -> Set[str]:
        """Fetch domains by checking the page concurrently (domain list rotates)"""
        domains = set()
        domain_pattern = re.compile(
            r'^([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+)$'
        )

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(self._fetch_once, i, domain_pattern) for i in range(50)]
            for future in as_completed(futures):
                domains.update(future.result())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class CyberTempFetcher(DomainFetcher):
    """Fetcher for 'cybertemp xyz' disposable email domains"""

    def __init__(self):
        super().__init__("CyberTemp")
        self.url = "https://api.cybertemp.xyz/getDomains"

    def fetch(self) -> Set[str]:
        """Fetch domains from CyberTemp API"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        try:
            data = response.json()
        except Exception as e:
            print(f"Error parsing JSON from {self.name}: {e}", file=sys.stderr)
            return set()

        domains = set()
        # Handle list response: ["domain1.com", "domain2.com", ...]
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, str) and entry:
                    domains.add(entry.lower().strip())
        # Handle object response: {"domains": [...]}
        elif isinstance(data, dict):
            for key in ("domains", "data"):
                if key in data and isinstance(data[key], list):
                    for entry in data[key]:
                        if isinstance(entry, str) and entry:
                            domains.add(entry.lower().strip())
                    break

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
    """Add new domains to the blocklist file"""
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


def is_valid_level_domain(domain: str, psl: PublicSuffixList, psl_local: Set) -> bool:
    """Check if the domain is a valid-level domain"""
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
    if public_valid or local_valid:
        return True
    else:
        return False


def is_public_suffix(domain: str, psl: PublicSuffixList, psl_local: Set) -> bool:
    """Check if the domain is a public suffix"""
    return (psl.publicsuffix(domain) == domain) or (domain in psl_local)

# Registry of all domain fetchers
FETCHERS = [
    YopmailFetcher(),
    TmailFetcher(),
    NoopmailFetcher(),
    YoursToolsFetcher(),
    GPTMailFetcher(),
    TinyhostFetcher(),
    GeneratorEmailFetcher(),
    CyberTempFetcher(),
    # Example: AnotherFetcher(),
]


def main():
    """Main function to run all registered domain fetchers"""
    blocklist_file = "disposable_email_blocklist.conf"
    with open("publicsuffixlist.local", "r") as psl_local_file:
        psl_local = set(line.strip() for line in psl_local_file if line.strip())

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
                if is_valid_level_domain(dd, psl, psl_local) and not is_public_suffix(dd, psl, psl_local):
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
