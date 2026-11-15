"""Public-suffix rules shared by verify.py and fetch_domains.py

A blocklist entry must sit exactly one label below a public suffix, where the
public suffixes are the upstream Public Suffix List plus the extra suffixes in
publicsuffixlist.local.
"""

from typing import Optional, Set

from publicsuffixlist import PublicSuffixList
from requests import get

PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
LOCAL_SUFFIXES_FILE = "publicsuffixlist.local"


def download_public_suffix_list(save_to: Optional[str] = None) -> PublicSuffixList:
    """Download the upstream Public Suffix List, optionally keeping a copy on disk.

    Raises on network or HTTP errors so a failed download never passes for an
    empty or garbage list.
    """
    response = get(PSL_URL, timeout=30)
    response.raise_for_status()
    if save_to:
        with open(save_to, "w", encoding="utf-8") as file:
            file.write(response.text)
    return PublicSuffixList(response.text.splitlines())


def load_local_suffixes(filename: str = LOCAL_SUFFIXES_FILE) -> Set[str]:
    """Load the extra suffixes this project treats as public."""
    with open(filename, "r", encoding="utf-8") as file:
        return {line.strip() for line in file if line.strip()}


def is_public_suffix(domain: str, psl: PublicSuffixList, psl_local: Set[str]) -> bool:
    """Check if the domain is itself a public suffix, upstream or local."""
    return psl.publicsuffix(domain) == domain or domain in psl_local


def is_valid_level_domain(domain: str, psl: PublicSuffixList, psl_local: Set[str]) -> bool:
    """Check if the domain has exactly one label below a public suffix."""
    # privateparts() is None when the domain is itself a public suffix
    private_parts = psl.privateparts(domain)
    if private_parts and len(private_parts) == 1:
        return True
    parts = domain.split(".")
    for i in range(len(parts)):
        if ".".join(parts[i:]) in psl_local and i == 1:
            return True
    return False
