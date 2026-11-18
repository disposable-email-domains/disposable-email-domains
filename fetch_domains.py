#!/usr/bin/env python

"""Fetch domains from various sources and add missing ones to the blocklist"""

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import DefaultCookiePolicy
from typing import Any, Iterable, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from domain_rules import (
    download_public_suffix_list,
    is_public_suffix,
    is_valid_level_domain,
    load_local_suffixes,
)


# Some sites (generator.email, throwaway.io) reject requests' default
# python-requests User-Agent outright
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
# (connect, read) seconds: a host that doesn't accept the connection is given
# up on quickly, a slow response still gets time
DEFAULT_TIMEOUT = (10, 30)

# A plain ASCII hostname with at least one dot; anything else a source returns is noise
HOSTNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def make_session() -> requests.Session:
    """Session shared by all fetchers: keeps connections alive and retries transient errors.

    Cookies are never stored. Several sources pick a new random domain per
    visitor, and a remembered session cookie would pin them to one.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.headers["Accept-Language"] = "en-US,en;q=0.9"
    session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
    # Only idempotent methods are retried (urllib3's default), so a POST that
    # creates a mailbox is never sent twice by the retry logic
    retry = Retry(total=2, backoff_factor=1, status_forcelist=(500, 502, 503, 504), raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = make_session()


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


def domain_of(address: Any) -> Optional[str]:
    """Return the domain part of an email address, or None if it isn't one."""
    if isinstance(address, str) and "@" in address:
        return address.rsplit("@", 1)[1]
    return None


def describe_error(error: Optional[BaseException]) -> str:
    """A short, single-line description of a fetch error, for logs and the stats table.

    requests' own messages repeat the whole URL and connection pool details,
    which buries the actual cause.
    """
    if error is None:
        return "unknown error"
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return f"HTTP {error.response.status_code}"
    if isinstance(error, requests.exceptions.RetryError):
        return "server errors persisted after retries"
    if isinstance(error, requests.Timeout):
        return "timed out"
    if isinstance(error, requests.ConnectionError):
        return "connection failed"
    if isinstance(error, requests.exceptions.JSONDecodeError):
        return "invalid JSON response"
    message = " ".join(str(error).split())
    if not isinstance(error, FetchError):
        message = f"{type(error).__name__}: {message}"
    return message if len(message) <= 160 else message[:157] + "..."


def strings(items: Any) -> Iterable[str]:
    """Yield the string entries of a JSON list; anything else yields nothing."""
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                yield item


# --- Base classes ----------------------------------------------------------


class FetchError(Exception):
    """A source failed in a way worth reporting, rather than with a raw network/parse error."""


class DomainFetcher:
    """Base class for domain fetchers.

    Subclasses implement collect(), returning the raw domains a source offers.
    fetch() normalizes them and drops anything that isn't a hostname.

    Failures propagate: network, HTTP and parse errors, and a source that yields
    no domains at all, raise from fetch(), and main() records them per source.
    Problems that still left a usable result (some sampling attempts failed,
    pagination broke off part way) are recorded with warn() and end up in
    self.warnings.
    """

    # Added to the error when a source yields nothing; override to point at a likelier cause
    empty_hint = "The page structure may have changed."

    def __init__(self, name: str, url: str = ""):
        self.name = name
        self.url = url
        self.warnings: List[str] = []

    def get_name(self) -> str:
        """Get the name of this fetcher"""
        return self.name

    def collect(self) -> Iterable[str]:
        """Return the domains offered by the source. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement collect()")

    def warn(self, message: str) -> None:
        """Record a problem that didn't stop the source from producing domains."""
        self.warnings.append(message)
        print(f"Warning ({self.name}): {message}", file=sys.stderr)

    def fetch(self) -> Set[str]:
        """Fetch, normalize and sanity-check the source's domains; raises on failure"""
        self.warnings = []
        raw = self.collect()
        domains = {d.strip().lower() for d in raw if isinstance(d, str)}
        domains = {d for d in domains if HOSTNAME_RE.match(d)}
        if not domains:
            raise FetchError(f"No domains found. {self.empty_hint}")
        return domains

    # HTTP helpers: all raise on network and HTTP errors

    def request(self, method: str, url: Optional[str] = None, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        response = SESSION.request(method, url or self.url, **kwargs)
        response.raise_for_status()
        return response

    def get(self, url: Optional[str] = None, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: Optional[str] = None, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def get_json(self, url: Optional[str] = None, **kwargs) -> Any:
        return self.get(url, **kwargs).json()

    def get_soup(self, url: Optional[str] = None, **kwargs) -> BeautifulSoup:
        return BeautifulSoup(self.get(url, **kwargs).text, "html.parser")


class JsonApiFetcher(DomainFetcher):
    """A source whose domain list comes from one JSON endpoint.

    Subclasses implement extract(), picking the domains out of the decoded JSON.
    """

    empty_hint = "The API response may have changed."

    def collect(self) -> Iterable[str]:
        return self.extract(self.get_json())

    def extract(self, data: Any) -> Iterable[str]:
        raise NotImplementedError("Subclasses must implement extract()")


class HtmlFetcher(DomainFetcher):
    """A source whose domains can be read off one HTML page.

    Subclasses implement parse(), given the parsed page and its raw HTML.
    """

    def collect(self) -> Iterable[str]:
        html = self.get().text
        return self.parse(BeautifulSoup(html, "html.parser"), html)

    def parse(self, soup: BeautifulSoup, html: str) -> Iterable[str]:
        raise NotImplementedError("Subclasses must implement parse()")


class StopSampling(Exception):
    """Raised by sample_once() when the source is blocking us and further attempts are pointless."""


class SamplingFetcher(DomainFetcher):
    """A source that only reveals a random part of its pool per request.

    Subclasses implement sample_once(), which makes one request and returns the
    domains it revealed. collect() calls it `attempts` times, sequentially with
    `delay` seconds between calls, or concurrently when `workers` > 1.

    `max_failures`: after this many failed attempts without a single domain,
    the sequential loop gives up (the site is down or blocking us). None keeps
    trying for all attempts.

    Failed attempts become a warning when other attempts still found domains,
    and an error when none did.
    """

    attempts = 10
    workers = 1
    delay = 0.0
    max_failures: Optional[int] = 3

    def sample_once(self) -> Iterable[str]:
        raise NotImplementedError("Subclasses must implement sample_once()")

    def _try_once(self, attempt: int) -> Tuple[Optional[Set[str]], Optional[Exception]]:
        """One sample: (domains, None) on success, (None, error) on failure. StopSampling propagates."""
        try:
            return set(self.sample_once()), None
        except StopSampling:
            raise
        except Exception as e:
            print(f"Error sampling {self.name} (attempt {attempt + 1}): {e}", file=sys.stderr)
            return None, e

    def collect(self) -> Iterable[str]:
        domains: Set[str] = set()
        failures = 0
        tried = 0
        last_error: Optional[Exception] = None
        stopped: Optional[StopSampling] = None

        if self.workers > 1:
            # In batches of `workers`, so a dead or blocking site is given up
            # on after a batch or two rather than after every attempt
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                for start in range(0, self.attempts, self.workers):
                    batch = range(start, min(start + self.workers, self.attempts))
                    try:
                        for result, error in executor.map(self._try_once, batch):
                            tried += 1
                            if error is not None:
                                failures, last_error = failures + 1, error
                            domains.update(result or ())
                    except StopSampling as e:
                        stopped = e
                        break
                    if self.max_failures is not None and failures >= self.max_failures and not domains:
                        break
        else:
            for attempt in range(self.attempts):
                if attempt and self.delay:
                    time.sleep(self.delay)
                try:
                    result, error = self._try_once(attempt)
                except StopSampling as e:
                    stopped = e
                    break
                tried += 1
                if error is not None:
                    failures, last_error = failures + 1, error
                    if self.max_failures is not None and failures >= self.max_failures and not domains:
                        break
                    continue
                domains.update(result)

        if not domains:
            if stopped is not None:
                raise FetchError(f"Stopped sampling: {stopped}")
            if last_error is not None:
                raise FetchError(f"{failures}/{tried} attempts failed, last: {describe_error(last_error)}")
        else:
            if stopped is not None:
                self.warn(f"Stopped sampling after {tried} attempt(s): {stopped}")
            if failures:
                self.warn(f"{failures}/{tried} attempts failed, last: {describe_error(last_error)}")
        return domains


# --- Sources ---------------------------------------------------------------


class YopmailFetcher(HtmlFetcher):
    """Fetcher for 'yopmail com' disposable email domains"""

    def __init__(self):
        super().__init__("Yopmail", "https://yopmail.com/en/domain?d=list")

    def parse(self, soup, html):
        return extract_domains_from_text(soup.get_text())


class NoopmailFetcher(SamplingFetcher):
    """Fetcher for 'noopmail org' disposable email domains.

    Each call to /api/rd returns a single random domain with expiration info.
    The site has a small pool of ~17 domains, so 50 requests is enough.

    Blocks github IP range - run locally via vpn/proxy.
    """

    attempts = 50
    delay = 0.05  # Small delay to avoid rate limiting
    max_failures = None

    def __init__(self):
        super().__init__("Noopmail", "https://noopmail.org/api/rd")

    def sample_once(self):
        data = self.get_json(timeout=10)
        if isinstance(data, dict) and isinstance(data.get("dm"), str):
            return [data["dm"]]
        return []


class GPTMailFetcher(JsonApiFetcher):
    """Fetcher for 'mail chatgpt org uk' disposable email domains"""

    def __init__(self):
        super().__init__("GPTMail", "https://mail.chatgpt.org.uk/api/domains/status")

    def extract(self, data):
        if not isinstance(data, dict) or not data.get("success"):
            return []
        entries = data.get("data")
        # Handle both list format and object with domains array
        if isinstance(entries, dict):
            entries = entries.get("domains")
        if not isinstance(entries, list):
            return []
        return [e["domain_name"] for e in entries if isinstance(e, dict) and isinstance(e.get("domain_name"), str)]


class TinyhostFetcher(DomainFetcher):
    """Fetcher for 'tinyhost shop' disposable email domains"""

    def __init__(self):
        # Public endpoint used by the site UI; /api/all-domains/ requires a token now
        super().__init__("Tinyhost", "https://tinyhost.shop/api/random-domains/")

    def collect(self):
        """Sample the random domains API (paginated)"""
        domains: Set[str] = set()
        duplicate_pages = 0
        try:
            # Each page returns a random selection from the pool, so sample
            # several pages per run; coverage accumulates across daily runs.
            for page in range(1, 11):
                data = self.get_json(params={"page": page, "limit": 50})
                if not isinstance(data, dict) or not isinstance(data.get("domains"), list):
                    raise FetchError(f"Malformed response on page {page}")
                items = data["domains"]
                if not items:
                    break
                before = len(domains)
                domains.update(d.lower().strip() for d in strings(items) if d)
                # Pages are random samples, so stop only after several
                # consecutive pages add nothing new
                duplicate_pages = duplicate_pages + 1 if len(domains) == before else 0
                if duplicate_pages >= 4:
                    break
        except Exception as e:
            # Keep what earlier pages gave us; with nothing, it's a plain failure
            if not domains:
                raise
            self.warn(f"Stopped after {len(domains)} domain(s): {describe_error(e)}")
        return domains


class OpenInboxFetcher(JsonApiFetcher):
    """Fetcher for 'openinbox io' disposable email domains"""

    def __init__(self):
        super().__init__("OpenInbox", "https://api.openinbox.io/api/inbox/platform-domains")

    def extract(self, data):
        return strings(data.get("domains")) if isinstance(data, dict) else []


class CleanTempMailFetcher(DomainFetcher):
    """Fetcher for 'cleantempmail com' disposable email domains"""

    empty_hint = "The API may have changed."
    limit = 2000
    max_pages = 1000

    def __init__(self):
        super().__init__("CleanTempMail", "https://cleantempmail.com/api/domains")

    def collect(self):
        """Fetch all domains from the paginated API; any error discards the partial result"""
        domains: Set[str] = set()
        offset = 0

        for _ in range(self.max_pages):
            data = self.get_json(params={"limit": self.limit, "offset": offset})

            if not isinstance(data, dict):
                raise ValueError("malformed response")
            if data.get("success") is False:
                raise ValueError("API reported failure")
            page = data.get("data")
            if not isinstance(page, dict) or not isinstance(page.get("domains"), list):
                raise ValueError("malformed response")
            page_domains = page["domains"]

            total = page.get("total")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                total = None

            before = len(domains)
            domains.update(d.lower().strip() for d in strings(page_domains))

            # Stop when the API has nothing more for us, or when we either
            # reached the advertised total or made no forward progress.
            if not page_domains:
                break
            offset += len(page_domains)
            if total is not None and offset >= total:
                break
            if len(domains) == before:
                break

        return domains


class GeneratorEmailFetcher(SamplingFetcher):
    """Fetcher for 'generator email' disposable email domains.

    Each page load selects a random domain from the pool and embeds it in the
    page's JS config as cur_domain:"...", so the pool is sampled concurrently,
    a few requests at a time.
    """

    attempts = 50
    workers = 5

    def __init__(self):
        super().__init__("GeneratorEmail", "https://generator.email/")

    def sample_once(self):
        match = re.search(r'cur_domain\s*:\s*["\']([^"\']+)["\']', self.get().text)
        return [match.group(1)] if match else []


class CyberTempFetcher(JsonApiFetcher):
    """Fetcher for 'cybertemp xyz' disposable email domains"""

    def __init__(self):
        super().__init__("CyberTemp", "https://api.cybertemp.xyz/getDomains")

    def extract(self, data):
        # Either ["domain1.com", ...] or {"domains": [...]} / {"data": [...]}
        if isinstance(data, list):
            return strings(data)
        if isinstance(data, dict):
            for key in ("domains", "data"):
                if isinstance(data.get(key), list):
                    return strings(data[key])
        return []


class TempMailFetcher(SamplingFetcher):
    """Fetcher for 'temp-mail org' disposable email domains.

    temp-mail.org does not expose its domain list publicly (the /domains
    endpoint requires an auth secret). The active pool is only observable
    by requesting new mailboxes via its mailbox API, which returns a
    randomly picked domain per call. Domains rotate over time, so sampling
    a few times per run is enough to gradually cover the pool.

    Rate limits (~5-10 mailbox creations per IP, then a short block) are
    handled by stopping early and returning the domains collected so far.
    """

    empty_hint = (
        "This may be caused by rate limiting or IP/Cloudflare blocking, "
        "or the endpoint may have changed."
    )
    attempts = 30
    delay = 2  # Wait between attempts, also after failures
    max_failures = None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://temp-mail.org",
        "Referer": "https://temp-mail.org/",
    }
    payload = {"method": "getMailBox", "params": {"lang": "en"}, "id": 1}

    def __init__(self):
        super().__init__("TempMail", "https://web2.temp-mail.org/mailbox")

    def sample_once(self):
        # Not self.post(): the block/rate-limit checks need the response before raise_for_status
        response = SESSION.post(self.url, json=self.payload, headers=self.headers, timeout=15)
        # Stop early on hard blocks (Cloudflare 403, auth 401)
        if response.status_code in (401, 403):
            raise StopSampling(f"HTTP {response.status_code}")
        # Stop on rate limit: {"errorMessage":"Too Many Request","errorName":"TooManyRequestsException"}
        if response.status_code == 429 or "TooManyRequests" in response.text:
            raise StopSampling("rate limited")
        response.raise_for_status()
        domain = domain_of(response.json().get("mailbox"))
        return [domain] if domain else []


class MailTmApiFetcher(DomainFetcher):
    """Base fetcher for services that serve the mail.tm domains API"""

    def __init__(self, name: str, url: str, status_key: str):
        super().__init__(name, url)
        # The field that marks a domain usable: mail.tm sends `isActive`, other
        # services running its API may send a different flag (DuckMail: `isVerified`)
        self.status_key = status_key

    def collect(self):
        """Fetch active domains from a mail.tm-style public domains API (paginated)"""
        domains: Set[str] = set()
        page_size = None
        try:
            for page in range(1, 6):
                data = self.get_json(f"{self.url}?page={page}")
                member = data.get("hydra:member")
                if not isinstance(member, list) or not member:
                    break
                # Derive the API page size from the first page instead of assuming one
                if page_size is None:
                    page_size = len(member)
                for entry in member:
                    if isinstance(entry, dict) and entry.get(self.status_key) is True:
                        domain = entry.get("domain")
                        if isinstance(domain, str) and domain:
                            domains.add(domain)
                # Stop when a page returns fewer items than the first page did
                if len(member) < page_size:
                    break
        except Exception as e:
            # Keep what earlier pages gave us; with nothing, it's a plain failure
            if not domains:
                raise
            self.warn(f"Stopped after {len(domains)} domain(s): {describe_error(e)}")
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


class TempMailIOFetcher(JsonApiFetcher):
    """Fetcher for 'temp-mail io' disposable email domains.

    temp-mail.io (a separate service from temp-mail.org) exposes its
    active domain pool through a public JSON endpoint.
    """

    empty_hint = "The page structure may have changed."

    def __init__(self):
        super().__init__("TempMail.io", "https://api.internal.temp-mail.io/api/v2/domains")

    def extract(self, data):
        if isinstance(data, dict):
            return strings(data.get("domains"))
        return strings(data)


class ThrowawayFetcher(JsonApiFetcher):
    """Fetcher for 'throwaway io' disposable email domains.

    throwaway.io lists its whole domain pool at a public JSON endpoint:
    {"status": true, "data": {"domains": ["example.xyz", ...]}}
    It answers 403 to requests' default User-Agent; the session's browser one works.
    """

    def __init__(self):
        super().__init__("Throwaway", "https://throwaway.io/api/ai/v1/domains")

    def extract(self, data):
        inner = data.get("data") if isinstance(data, dict) else None
        return strings(inner.get("domains")) if isinstance(inner, dict) else []


class TempMailCloudFetcher(JsonApiFetcher):
    """Fetcher for 'tempmail cloud' disposable email domains.

    tempmail.cloud publishes its domain pool in its public app config:
    {"domains": [{"domain": "example.store", "active": true, "privateOwnerId": null, ...}, ...]}
    """

    def __init__(self):
        super().__init__("TempMail.cloud", "https://tempmail.cloud/api/config")

    def extract(self, data):
        entries = data.get("domains") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return []
        return [
            entry["domain"]
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("active") is True
            # Skip domains a user has claimed privately; only the shared pool is disposable for sure
            and not entry.get("privateOwnerId")
            and isinstance(entry.get("domain"), str)
        ]


class Mail123Fetcher(JsonApiFetcher):
    """Fetcher for 'mail123 fr' disposable email domains.

    mail123.fr lists its domain pool at a public JSON endpoint:
    {"success": true, "domains": ["mail123.fr", ...], "primary": "mail123.fr", ...}
    """

    def __init__(self):
        super().__init__("Mail123", "https://mail123.fr/api/v1/domains")

    def extract(self, data):
        return strings(data.get("domains")) if isinstance(data, dict) else []


class CatchMailFetcher(HtmlFetcher):
    """Fetcher for 'catchmail io' disposable email domains.

    catchmail.io has no public domains endpoint; the homepage renders the
    domain picker server-side as <select><option value="example.com">...,
    and also embeds the same list in the Next.js payload as
    {"domains":[{"domain":"example.com"},...]}.
    """

    def __init__(self):
        super().__init__("CatchMail", "https://catchmail.io/")

    def parse(self, soup, html):
        domains = set()
        for select in soup.find_all("select"):
            for option in select.find_all("option"):
                value = (option.get("value") or option.get_text() or "").strip()
                if "." in value:
                    domains.add(value)
        # Fallback: the Next.js flight payload (quotes may be backslash-escaped)
        if not domains:
            domains.update(re.findall(r'\\?"domain\\?":\\?"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\\?"', html))
        return domains


class TempFastMailFetcher(SamplingFetcher):
    """Fetcher for 'tempfastmail com' disposable email domains.

    tempfastmail.com has no domain list; each POST to /api/email-box creates a
    mailbox on a random domain from its pool:
    {"email": "name@example.com", "uuid": "..."}
    so the pool is collected by sampling several mailboxes.
    """

    empty_hint = "The API response may have changed."
    attempts = 20

    def __init__(self):
        super().__init__("TempFastMail", "https://tempfastmail.com/api/email-box")

    def sample_once(self):
        domain = domain_of(self.post(json={}, timeout=15).json().get("email"))
        return [domain] if domain else []


class TenMinuteMailNetFetcher(HtmlFetcher):
    """Fetcher for '10minutemail net' disposable email domains.

    The homepage pre-generates an address into <input id="fe_text" value="name@example.com">.
    """

    def __init__(self):
        super().__init__("10MinuteMail.net", "https://10minutemail.net/")

    def parse(self, soup, html):
        field = soup.find("input", id="fe_text")
        domain = domain_of(field.get("value")) if field else None
        return [domain] if domain else []


class DisposableMailFetcher(HtmlFetcher):
    """Fetcher for 'disposablemail com' disposable email domains.

    The homepage shows the mailbox domain in a read-only <input value="@example.com">.
    """

    def __init__(self):
        super().__init__("DisposableMail", "https://www.disposablemail.com/")

    def parse(self, soup, html):
        values = ((field.get("value") or "").strip() for field in soup.find_all("input"))
        return [value[1:] for value in values if value.startswith("@") and "." in value]


class FakeMailGeneratorFetcher(HtmlFetcher):
    """Fetcher for 'fakemailgenerator com' disposable email domains.

    The homepage lists all domains in the dropdown next to #domain-select:
    <ul class="dropdown-menu"><a href="#">@example.com</a>...</ul>
    """

    def __init__(self):
        super().__init__("FakeMailGenerator", "https://www.fakemailgenerator.com/")

    def parse(self, soup, html):
        texts = (link.get_text(strip=True) for link in soup.select("ul.dropdown-menu a"))
        return [text[1:] for text in texts if text.startswith("@") and "." in text]


class AnonymMailFetcher(SamplingFetcher):
    """Fetcher for 'anonymmail net' disposable email domains.

    Each homepage load generates an address on a random domain from the pool,
    shown as <b class="email">name@example.com</b>, so the pool is sampled.
    """

    attempts = 25

    def __init__(self):
        super().__init__("AnonymMail", "https://anonymmail.net/")

    def sample_once(self):
        tags = self.get_soup().find_all(class_="email")
        return [d for d in (domain_of(tag.get_text(strip=True)) for tag in tags) if d]


class MailBlinkerFetcher(SamplingFetcher):
    """Fetcher for 'mailblinker com' disposable email domains.

    Each page load generates an address on a random domain from the pool,
    shown as <span id="mail_address">name@example.com</span>, so the pool is sampled.
    """

    attempts = 10

    def __init__(self):
        # The bare domain answers with a meta-refresh to /en
        super().__init__("MailBlinker", "https://mailblinker.com/en")

    def sample_once(self):
        tag = self.get_soup().find(id="mail_address")
        domain = domain_of(tag.get_text(strip=True)) if tag else None
        return [domain] if domain else []


class USMailFetcher(HtmlFetcher):
    """Fetcher for 'usmail one' disposable email domains.

    usmail.one (redirects to 1mail.lt) renders its domain picker server-side:
    <select id="name_domain"><optgroup label="Free Domains"><option value="example.com">...
    """

    def __init__(self):
        super().__init__("USMail", "https://usmail.one/")

    def parse(self, soup, html):
        select = soup.find("select", id="name_domain")
        if not select:
            return []
        domains = []
        for option in select.find_all("option"):
            # Only the free groups; premium/paid domains are not handed out for free
            group = option.find_parent("optgroup")
            if group and "free" not in (group.get("label") or "").lower():
                continue
            value = (option.get("value") or "").strip()
            if "." in value:
                domains.append(value)
        return domains


class EmailFakeFetcher(SamplingFetcher):
    """Fetcher for 'email-fake com' disposable email domains.

    Domains appear as <p id="domain.tld"> inside the .tt-suggestions div, and
    the list changes between page loads, so the page is sampled concurrently,
    a few requests at a time.
    """

    attempts = 50
    workers = 5

    def __init__(self):
        super().__init__("Email-Fake", "https://email-fake.com")

    def sample_once(self):
        soup = self.get_soup()
        suggestions = soup.find("div", class_=lambda c: c and "tt-suggestions" in c.split())
        tags = suggestions.find_all("p", id=True) if suggestions else []
        # Fallback: any <p id="..."> on the page; ids that aren't domains are dropped by fetch()
        if not tags:
            tags = soup.find_all("p", id=True)
        return [tag["id"] for tag in tags]


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


# --- Blocklist update ------------------------------------------------------


def load_existing_domains(filename: str) -> Set[str]:
    """Load existing domains from blocklist file"""
    try:
        with open(filename, 'r') as f:
            return set(line.strip().lower() for line in f if line.strip())
    except FileNotFoundError:
        print(f"Warning: {filename} not found, starting with empty list", file=sys.stderr)
        return set()


def write_blocklist(domains: Set[str], filename: str) -> None:
    """Write the blocklist sorted alphabetically (case-insensitive), one domain per line"""
    with open(filename, 'w') as f:
        for domain in sorted(domains, key=str.lower):
            f.write(f"{domain}\n")


def main():
    """Main function to run all registered domain fetchers"""
    blocklist_file = "disposable_email_blocklist.conf"
    psl_local = load_local_suffixes()

    # Load the public suffix list once, to filter out subdomains
    try:
        psl = download_public_suffix_list()
    except Exception as e:
        print(f"Error loading Public Suffix List: {e}", file=sys.stderr)
        sys.exit(1)

    existing = load_existing_domains(blocklist_file)
    # Domains new to the blocklist, from all sources; written once at the end
    new_domains: Set[str] = set()
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
                # A domain counts for the first source that brought it, as when
                # each source was written to the file in turn
                missing = domains - existing - new_domains
                if missing:
                    print(f"Found {len(missing)} new domains to add from {fetcher.get_name()}:")
                    for domain in sorted(missing):
                        print(f"  + {domain}")
                else:
                    print(f"No new domains to add from {fetcher.get_name()}.")
                new_domains |= missing
                added = len(missing)
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
            if fetcher.warnings:
                stats[fetcher.get_name()]["warning"] = "; ".join(fetcher.warnings)
        except Exception as e:
            error = describe_error(e)
            print(f"Error processing {fetcher.get_name()}: {error}", file=sys.stderr)
            # Record failed fetcher with zero counts
            stats[fetcher.get_name()] = {
                "found": 0,
                "added": 0,
                "raw": 0,
                "error": error
            }
            continue

    if new_domains:
        write_blocklist(existing | new_domains, blocklist_file)

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
