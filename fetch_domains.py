#!/usr/bin/env python

"""Fetch domains from various sources and add missing ones to the blocklist"""

import json
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


class NoopmailFetcher(DomainFetcher):
    """
    Fetcher for 'noopmail org' disposable email domains.

    Blocks github IP range - run locally via vpn/proxy.
    """

    def __init__(self):
        super().__init__("Noopmail")
        self.url = "https://noopmail.org/api/rd"

    def fetch(self) -> Set[str]:
        """Fetch domains from Noopmail by polling the random domain endpoint"""
        import time
        domains = set()
        try:
            # Poll the /api/rd endpoint to collect domains
            # Each call returns a single random domain with expiration info
            # The site has a small pool of ~17 domains, so 50 requests is enough
            for i in range(50):
                try:
                    response = get(self.url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict) and "dm" in data:
                        domain = data["dm"].lower().strip()
                        if domain:
                            domains.add(domain)
                    # Small delay to avoid rate limiting
                    time.sleep(0.05)
                except Exception:
                    # Continue on individual request failures
                    continue
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)

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
        # Public endpoint used by the site UI; /api/all-domains/ requires a token now
        self.url = "https://tinyhost.shop/api/random-domains/"

    def fetch(self) -> Set[str]:
        """Fetch domains from the Tinyhost public random domains API (paginated)"""
        domains = set()
        duplicate_pages = 0
        try:
            # Each page returns a random selection from the pool, so sample
            # several pages per run; coverage accumulates across daily runs.
            for page in range(1, 11):
                response = get(self.url, params={"page": page, "limit": 50}, timeout=30)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("domains"), list):
                    print(f"Error: Malformed response from {self.name} while fetching domains.", file=sys.stderr)
                    return domains
                items = data["domains"]
                new_domains = 0
                for domain in items:
                    if isinstance(domain, str) and domain:
                        domain = domain.lower().strip()
                        if domain not in domains:
                            domains.add(domain)
                            new_domains += 1
                if not items:
                    break
                # Pages are random samples, so stop only after several
                # consecutive pages add nothing new
                if new_domains == 0:
                    duplicate_pages += 1
                else:
                    duplicate_pages = 0
                if duplicate_pages >= 4:
                    break
        except Exception as e:
            print(f"Error fetching {self.name} domains (keeping {len(domains)} domain(s) collected so far): {e}", file=sys.stderr)
            return domains

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)
        return domains


class OpenInboxFetcher(DomainFetcher):
    """Fetcher for `openinbox io` disposable email domains"""

    def __init__(self):
        super().__init__("OpenInbox")
        self.url = "https://api.openinbox.io/api/inbox/platform-domains"

    def fetch(self) -> Set[str]:
        """Fetch platform (disposable inbox) domains from the OpenInbox API"""
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


class CleanTempMailFetcher(DomainFetcher):
    """Fetcher for `cleantempmail com` disposable email domains"""

    def __init__(self):
        super().__init__("CleanTempMail")
        self.url = "https://cleantempmail.com/api/domains"
        self.limit = 2000

    def fetch(self) -> Set[str]:
        """Fetch all domains from the paginated CleanTempMail API.
        """
        domains = set()
        offset = 0

        max_pages = 1000

        for _ in range(max_pages):
            try:
                response = get(
                    self.url,
                    params={"limit": self.limit, "offset": offset},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
                return set()

            if not isinstance(data, dict):
                print(f"Error parsing data from {self.name}: malformed response", file=sys.stderr)
                return set()

            if data.get("success") is False:
                print(f"Error from {self.name}: API reported failure", file=sys.stderr)
                return set()

            page = data.get("data")
            if not isinstance(page, dict) or not isinstance(page.get("domains"), list):
                print(f"Error parsing data from {self.name}: malformed response", file=sys.stderr)
                return set()
            page_domains = page["domains"]

            total = page.get("total")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                total = None

            before = len(domains)
            for domain in page_domains:
                if isinstance(domain, str):
                    normalized = domain.lower().strip()
                    if normalized:
                        domains.add(normalized)

            # Stop when the API has nothing more for us, or when we either
            # reached the advertised total or made no forward progress.
            if not page_domains:
                break
            offset += len(page_domains)
            if total is not None and offset >= total:
                break
            if len(domains) == before:
                break

        if not domains:
            print(f"Warning: No domains found from {self.name}. The API may have changed.", file=sys.stderr)

        return domains


class GeneratorEmailFetcher(DomainFetcher):
    """Fetcher for 'generator.email' disposable email domains"""

    def __init__(self):
        super().__init__("GeneratorEmail")
        self.url = "https://generator.email/"

    def _fetch_once(self, attempt: int, domain_pattern: "re.Pattern") -> Set[str]:
        """Fetch and parse the randomly selected domain from a single page load"""
        domains = set()
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains (attempt {attempt + 1}): {e}", file=sys.stderr)
            return domains

        # Each page load selects a random domain from the pool and embeds it
        # in the page's JS config as cur_domain:"..."
        match = re.search(r'cur_domain\s*:\s*["\']([^"\']+)["\']', response.text)
        if match:
            domain = match.group(1).lower().strip()
            if domain_pattern.match(domain):
                domains.add(domain)

        return domains

    def fetch(self) -> Set[str]:
        """Fetch domains by sampling page loads concurrently (domain rotates per load)"""
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


class TempMailFetcher(DomainFetcher):
    """Fetcher for 'temp-mail org' disposable email domains.

    temp-mail.org does not expose its domain list publicly (the /domains
    endpoint requires an auth secret). The active pool is only observable
    by requesting new mailboxes via its mailbox API, which returns a
    randomly picked domain per call. Domains rotate over time, so sampling
    a few times per run is enough to gradually cover the pool.

    Rate limits (~5-10 mailbox creations per IP, then a short block) are
    handled by stopping early and returning the domains collected so far.
    """

    def __init__(self):
        super().__init__("TempMail")
        self.url = "https://web2.temp-mail.org/mailbox"

    def fetch(self) -> Set[str]:
        """Fetch domains from temp-mail.org by polling its mailbox endpoint"""
        import time
        domains = set()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://temp-mail.org",
            "Referer": "https://temp-mail.org/",
        }
        payload = {"method": "getMailBox", "params": {"lang": "en"}, "id": 1}
        try:
            for _ in range(30):
                try:
                    response = post(self.url, json=payload, headers=headers, timeout=15)
                    # Stop early on hard blocks (Cloudflare 403, auth 401)
                    if response.status_code in (401, 403):
                        break
                    # Stop on rate limit: {"errorMessage":"Too Many Request","errorName":"TooManyRequestsException"}
                    if response.status_code == 429 or "TooManyRequests" in response.text:
                        break
                    response.raise_for_status()
                    data = response.json()
                    mailbox = data.get("mailbox", "")
                    if isinstance(mailbox, str) and "@" in mailbox:
                        domain = mailbox.rsplit("@", 1)[1].lower().strip()
                        if domain:
                            domains.add(domain)
                except Exception:
                    # Continue on individual request failures
                    pass
                finally:
                    # Always wait between attempts, also after failures
                    time.sleep(2)
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)

        if not domains:
            print(
                f"Warning: No domains found from {self.name}. "
                "This may be caused by rate limiting or IP/Cloudflare blocking, "
                "or the endpoint may have changed.",
                file=sys.stderr,
            )

        return domains


class TempMailIOFetcher(DomainFetcher):
    """Fetcher for 'temp-mail.io' disposable email domains.

    temp-mail.io (a separate service from temp-mail.org) exposes its
    active domain pool through a public JSON endpoint, so the domains can
    be fetched directly.
    """

    def __init__(self):
        super().__init__("TempMail.io")
        self.url = "https://api.internal.temp-mail.io/api/v2/domains"

    def fetch(self) -> Set[str]:
        """Fetch domains from the temp-mail.io public domains API"""
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
        if isinstance(data, dict) and isinstance(data.get("domains"), list):
            for entry in data["domains"]:
                if isinstance(entry, str) and entry:
                    domains.add(entry.lower().strip())
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, str) and entry:
                    domains.add(entry.lower().strip())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class ThrowawayFetcher(DomainFetcher):
    """Fetcher for 'throwaway io' disposable email domains.

    throwaway.io lists its whole domain pool at a public JSON endpoint:
    {"status": true, "data": {"domains": ["example.xyz", ...]}}
    """

    def __init__(self):
        super().__init__("Throwaway")
        self.url = "https://throwaway.io/api/ai/v1/domains"

    def fetch(self) -> Set[str]:
        """Fetch domains from the throwaway.io domains API"""
        try:
            # The server answers 403 to requests' default User-Agent
            # (python-requests/x.y), so send one that names this project.
            response = get(self.url, headers={"User-Agent": "disposable-email-domains fetcher"}, timeout=30)
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
        entries = data.get("data", {}).get("domains") if isinstance(data, dict) else None
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, str) and entry.strip():
                    domains.add(entry.lower().strip())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The API response may have changed.", file=sys.stderr)

        return domains


class TempMailCloudFetcher(DomainFetcher):
    """Fetcher for 'tempmail cloud' disposable email domains.

    tempmail.cloud publishes its domain pool in its public app config:
    {"domains": [{"domain": "example.store", "active": true, "privateOwnerId": null, ...}, ...]}
    """

    def __init__(self):
        super().__init__("TempMail.cloud")
        self.url = "https://tempmail.cloud/api/config"

    def fetch(self) -> Set[str]:
        """Fetch active public domains from the tempmail.cloud config API"""
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
        entries = data.get("domains") if isinstance(data, dict) else None
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("active") is not True:
                    continue
                # Skip domains a user has claimed privately; only the shared pool is disposable for sure
                if entry.get("privateOwnerId"):
                    continue
                domain = entry.get("domain")
                if isinstance(domain, str) and domain.strip():
                    domains.add(domain.lower().strip())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The API response may have changed.", file=sys.stderr)

        return domains


class Mail123Fetcher(DomainFetcher):
    """Fetcher for 'mail123 fr' disposable email domains.

    mail123.fr lists its domain pool at a public JSON endpoint:
    {"success": true, "domains": ["mail123.fr", ...], "primary": "mail123.fr", ...}
    """

    def __init__(self):
        super().__init__("Mail123")
        self.url = "https://mail123.fr/api/v1/domains"

    def fetch(self) -> Set[str]:
        """Fetch domains from the mail123.fr domains API"""
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
        entries = data.get("domains") if isinstance(data, dict) else None
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, str) and entry.strip():
                    domains.add(entry.lower().strip())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The API response may have changed.", file=sys.stderr)

        return domains


class CatchMailFetcher(DomainFetcher):
    """Fetcher for 'catchmail io' disposable email domains.

    catchmail.io has no public domains endpoint; the homepage renders the
    domain picker server-side as <select><option value="example.com">...,
    and also embeds the same list in the Next.js payload as
    {"domains":[{"domain":"example.com"},...]}.
    """

    def __init__(self):
        super().__init__("CatchMail")
        self.url = "https://catchmail.io/"

    def fetch(self) -> Set[str]:
        """Fetch domains from the catchmail.io homepage domain picker"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        domains = set()
        soup = BeautifulSoup(response.text, "html.parser")
        for select in soup.find_all("select"):
            for option in select.find_all("option"):
                value = (option.get("value") or option.get_text() or "").strip().lower()
                if "." in value:
                    domains.add(value)

        # Fallback: the Next.js flight payload (quotes may be backslash-escaped)
        if not domains:
            for match in re.findall(r'\\?"domain\\?":\\?"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\\?"', response.text):
                domains.add(match.lower())

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class TempFastMailFetcher(DomainFetcher):
    """Fetcher for 'tempfastmail com' disposable email domains.

    tempfastmail.com has no domain list; each POST to /api/email-box creates a
    mailbox on a random domain from its pool:
    {"email": "name@example.com", "uuid": "..."}
    so the pool is collected by sampling several mailboxes.
    """

    def __init__(self, attempts: int = 20):
        super().__init__("TempFastMail")
        self.url = "https://tempfastmail.com/api/email-box"
        self.attempts = attempts

    def fetch(self) -> Set[str]:
        """Collect domains by creating a number of mailboxes"""
        domains = set()
        failures = 0
        for _ in range(self.attempts):
            try:
                response = post(self.url, json={}, timeout=15)
                response.raise_for_status()
                email = response.json().get("email")
            except Exception as e:
                failures += 1
                print(f"Error fetching {self.name} mailbox: {e}", file=sys.stderr)
                # Give up early if the service is down or blocking us
                if failures >= 3 and not domains:
                    break
                continue

            if isinstance(email, str) and "@" in email:
                domain = email.rsplit("@", 1)[1].strip().lower()
                if domain:
                    domains.add(domain)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The API response may have changed.", file=sys.stderr)

        return domains


class TenMinuteMailNetFetcher(DomainFetcher):
    """Fetcher for '10minutemail net' disposable email domains.

    The homepage pre-generates an address into <input id="fe_text" value="name@example.com">.
    """

    def __init__(self):
        super().__init__("10MinuteMail.net")
        self.url = "https://10minutemail.net/"

    def fetch(self) -> Set[str]:
        """Fetch the domain of the address generated on the 10minutemail.net homepage"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        domains = set()
        soup = BeautifulSoup(response.text, "html.parser")
        field = soup.find("input", id="fe_text")
        value = (field.get("value") or "") if field else ""
        if "@" in value:
            domain = value.rsplit("@", 1)[1].strip().lower()
            if domain:
                domains.add(domain)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class DisposableMailFetcher(DomainFetcher):
    """Fetcher for 'disposablemail com' disposable email domains.

    The homepage shows the mailbox domain in a read-only <input value="@example.com">.
    """

    def __init__(self):
        super().__init__("DisposableMail")
        self.url = "https://www.disposablemail.com/"

    def fetch(self) -> Set[str]:
        """Fetch the domain shown on the disposablemail.com homepage"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        domains = set()
        soup = BeautifulSoup(response.text, "html.parser")
        for field in soup.find_all("input"):
            value = (field.get("value") or "").strip().lower()
            if value.startswith("@") and "." in value:
                domains.add(value[1:])

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class FakeMailGeneratorFetcher(DomainFetcher):
    """Fetcher for 'fakemailgenerator com' disposable email domains.

    The homepage lists all domains in the dropdown next to #domain-select:
    <ul class="dropdown-menu"><a href="#">@example.com</a>...</ul>
    """

    def __init__(self):
        super().__init__("FakeMailGenerator")
        self.url = "https://www.fakemailgenerator.com/"

    def fetch(self) -> Set[str]:
        """Fetch domains from the fakemailgenerator.com domain dropdown"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        domains = set()
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.select("ul.dropdown-menu a"):
            text = link.get_text(strip=True).lower()
            if text.startswith("@") and "." in text:
                domains.add(text[1:])

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class AnonymMailFetcher(DomainFetcher):
    """Fetcher for 'anonymmail net' disposable email domains.

    Each homepage load generates an address on a random domain from the pool,
    shown as <b class="email">name@example.com</b>, so the pool is sampled.
    """

    def __init__(self, attempts: int = 25):
        super().__init__("AnonymMail")
        self.url = "https://anonymmail.net/"
        self.attempts = attempts

    def fetch(self) -> Set[str]:
        """Collect domains by loading the anonymmail.net homepage several times"""
        domains = set()
        failures = 0
        for _ in range(self.attempts):
            try:
                response = get(self.url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                failures += 1
                print(f"Error fetching {self.name} page: {e}", file=sys.stderr)
                # Give up early if the site is down or blocking us
                if failures >= 3 and not domains:
                    break
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup.find_all(class_="email"):
                text = tag.get_text(strip=True)
                if "@" in text:
                    domain = text.rsplit("@", 1)[1].strip().lower()
                    if domain:
                        domains.add(domain)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class MailBlinkerFetcher(DomainFetcher):
    """Fetcher for 'mailblinker com' disposable email domains.

    Each page load generates an address on a random domain from the pool,
    shown as <span id="mail_address">name@example.com</span>, so the pool is sampled.
    """

    def __init__(self, attempts: int = 10):
        super().__init__("MailBlinker")
        # The bare domain answers with a meta-refresh to /en
        self.url = "https://mailblinker.com/en"
        self.attempts = attempts

    def fetch(self) -> Set[str]:
        """Collect domains by loading the mailblinker.com page several times"""
        domains = set()
        failures = 0
        for _ in range(self.attempts):
            try:
                response = get(self.url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                failures += 1
                print(f"Error fetching {self.name} page: {e}", file=sys.stderr)
                # Give up early if the site is down or blocking us
                if failures >= 3 and not domains:
                    break
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            tag = soup.find(id="mail_address")
            text = tag.get_text(strip=True) if tag else ""
            if "@" in text:
                domain = text.rsplit("@", 1)[1].strip().lower()
                if domain:
                    domains.add(domain)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class USMailFetcher(DomainFetcher):
    """Fetcher for 'usmail one' disposable email domains.

    usmail.one (redirects to 1mail.lt) renders its domain picker server-side:
    <select id="name_domain"><optgroup label="Free Domains"><option value="example.com">...
    """

    def __init__(self):
        super().__init__("USMail")
        self.url = "https://usmail.one/"

    def fetch(self) -> Set[str]:
        """Fetch domains from the usmail.one domain picker"""
        try:
            response = get(self.url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)
            return set()

        domains = set()
        soup = BeautifulSoup(response.text, "html.parser")
        select = soup.find("select", id="name_domain")
        if select:
            for option in select.find_all("option"):
                # Only the free groups; premium/paid domains are not handed out for free
                group = option.find_parent("optgroup")
                if group and "free" not in (group.get("label") or "").lower():
                    continue
                value = (option.get("value") or "").strip().lower()
                if "." in value:
                    domains.add(value)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class EmailFakeFetcher(DomainFetcher):
    """Fetcher for 'email-fake com' disposable email domains."""

    def __init__(self):
        super().__init__("Email-Fake")
        self.url = "https://email-fake.com"

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

        # Domains appear as <p id="domain.tld"> inside the .fem.tt-suggestions div
        suggestions_div = soup.find("div", class_=lambda c: c and "tt-suggestions" in c.split())
        if suggestions_div:
            for p_tag in suggestions_div.find_all("p", id=True):
                candidate = p_tag["id"].strip().lower()
                if candidate and domain_pattern.match(candidate):
                    domains.add(candidate)

        # Fallback: scan all <p id="..."> on the page
        if not domains:
            for p_tag in soup.find_all("p", id=True):
                candidate = p_tag["id"].strip().lower()
                if candidate and domain_pattern.match(candidate):
                    domains.add(candidate)

        return domains

    def fetch(self) -> Set[str]:
        """Fetch domains by sampling page loads concurrently (pool may rotate per load)"""
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

class MailTmApiFetcher(DomainFetcher):
    """Base fetcher for services that serve the mail.tm domains API"""

    def __init__(self, name: str, url: str, status_key: str):
        super().__init__(name)
        self.url = url
        # The field that marks a domain usable: mail.tm sends `isActive`, other
        # services running its API may send a different flag (DuckMail: `isVerified`)
        self.status_key = status_key

    def fetch(self) -> Set[str]:
        """Fetch active domains from a mail.tm-style public domains API (paginated)"""
        domains = set()
        page_size = None
        try:
            for page in range(1, 6):
                response = get(f"{self.url}?page={page}", timeout=30)
                response.raise_for_status()
                data = response.json()
                member = data.get("hydra:member")
                if not isinstance(member, list) or not member:
                    break
                # Derive the API page size from the first page instead of assuming one
                if page_size is None:
                    page_size = len(member)
                for entry in member:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get(self.status_key) is not True:
                        continue
                    domain = entry.get("domain")
                    if isinstance(domain, str) and domain:
                        domains.add(domain.lower().strip())
                # Stop when a page returns fewer items than the first page did
                if len(member) < page_size:
                    break
        except Exception as e:
            print(f"Error fetching {self.name} domains: {e}", file=sys.stderr)

        if not domains:
            print(f"Warning: No domains found from {self.name}. The page structure may have changed.", file=sys.stderr)

        return domains


class MailTmFetcher(MailTmApiFetcher):
    """Fetcher for 'mail.tm' disposable email domains"""

    def __init__(self):
        super().__init__("Mail.tm", "https://api.mail.tm/domains", "isActive")


class DuckMailFetcher(MailTmApiFetcher):
    """Fetcher for 'duckmail sbs' disposable email domains

    DuckMail serves the domains offered under "Add mailbox" -> "Custom create" ->
    "Select Domain" through a mail.tm-compatible API, with `isVerified` in place
    of `isActive`.
    """

    def __init__(self):
        super().__init__("DuckMail", "https://api.duckmail.sbs/domains", "isVerified")


# Registry of all domain fetchers
FETCHERS = [
    YopmailFetcher(),
    NoopmailFetcher(),
    GPTMailFetcher(),
    TinyhostFetcher(),
    OpenInboxFetcher(),
    CleanTempMailFetcher(),
    GeneratorEmailFetcher(),
    CyberTempFetcher(),
    TempMailFetcher(),
    MailTmFetcher(),
    DuckMailFetcher(),
    TempMailIOFetcher(),
    ThrowawayFetcher(),
    TempMailCloudFetcher(),
    Mail123Fetcher(),
    CatchMailFetcher(),
    TempFastMailFetcher(),
    TenMinuteMailNetFetcher(),
    DisposableMailFetcher(),
    FakeMailGeneratorFetcher(),
    AnonymMailFetcher(),
    MailBlinkerFetcher(),
    USMailFetcher(),
    EmailFakeFetcher(),
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
    stats = {}  # Track statistics per fetcher

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
            raw_count = len(raw_domains)
            filtered_count = len(domains)
            print(f"Found {filtered_count} domains from {fetcher.get_name()} (raw: {raw_count})")

            added = 0
            if domains:
                added = add_domains_to_blocklist(domains, blocklist_file, fetcher.get_name())
                total_added += added
                sources_processed += 1
            else:
                print(f"No domains found from {fetcher.get_name()}")

            # Record statistics for this fetcher
            stats[fetcher.get_name()] = {
                "found": filtered_count,
                "added": added,
                "raw": raw_count
            }
        except Exception as e:
            print(f"Error processing {fetcher.get_name()}: {e}", file=sys.stderr)
            # Record failed fetcher with zero counts
            stats[fetcher.get_name()] = {
                "found": 0,
                "added": 0,
                "raw": 0,
                "error": str(e)
            }
            continue

    # Write statistics to JSON file for workflow to consume
    with open("fetch_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

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
