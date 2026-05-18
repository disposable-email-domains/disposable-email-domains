#!/usr/bin/env python3

"""
================================================================================
EXAMPLE SCRIPT: Discover New Disposable Email Domains
================================================================================

This script demonstrates how to discover NEW disposable email domains by
checking found domains against an existing blocklist. Domains NOT in the
blocklist are marked as "new discoveries."

This is designed as a TEMPLATE that you can modify for your own projects.

================================================================================
HOW TO RUN
================================================================================

Local Mode (with screenshots for new domains):
    cd /path/to/disposable-email-domains
    source venv/bin/activate  # if using virtual environment
    python script/discover_new_domains.py

Custom blocklist file:
    python script/discover_new_domains.py --blocklist-file path/to/blocklist.txt

CI Mode (logging only, no screenshots):
    CI=true python script/discover_new_domains.py

================================================================================
ENVIRONMENT VARIABLES
================================================================================

    CI                      - Set to "true" to disable screenshots (default: false)

    MAX_ATTEMPTS            - Total number of email generations to attempt before
                              stopping. Each attempt fetches one email from the
                              website. (default: 100)

    MAX_UNSUCCESSFUL_ATTEMPTS - Number of consecutive attempts without finding a
                              NEW domain before stopping early. This prevents
                              wasting time if the website keeps returning the
                              same domains. (default: 30)

================================================================================
REQUIREMENTS
================================================================================

    pip install playwright
    playwright install chromium

================================================================================
WHAT TO CUSTOMIZE
================================================================================

1. TARGET_URL
   - Change to the URL of the disposable email service you want to scrape

2. EMAIL_SELECTOR
   - Update the CSS selector to match where the email is displayed on the page

3. NEW_EMAIL_BUTTON_SELECTOR
   - Update the CSS selector for the "generate new email" button

4. BLOCKLIST_PATH
   - Default path to your existing blocklist file for comparison

5. SCREENSHOT_DIR
   - Directory where screenshots of new domains will be saved

================================================================================
PAUSE FUNCTIONS - WHEN TO USE THEM
================================================================================

The script uses different pause durations to mimic human behavior and avoid
detection. Here's when each is used:

pause(config.pause_short)    - 3-8 seconds
    Use between quick actions like clicking buttons or reading simple elements

pause(config.pause_medium)   - 10-25 seconds
    Use after page loads or when waiting for content to render

pause(config.pause_long)     - 15-30 seconds
    Use after generating a new email to let the page fully update

pause(config.pause_session)  - 480-720 seconds (8-12 minutes)
    Use between browser sessions to avoid rate limiting

================================================================================
OUTPUT
================================================================================

- Logs all discovered emails to console
- Marks domains NOT in blocklist as "NEW DOMAIN FOUND"
- In local mode:
    - Saves screenshots of new domains to screenshot directory
    - Existing screenshots are treated as "known" domains (skipped)
- In CI mode: only logs findings (no screenshots)

================================================================================
"""

import argparse
import os
import sys
import time
import random
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


"""
================================================================================
CUSTOMIZE: TARGET_URL
================================================================================
The URL of the disposable email service you want to scrape. Change this to
your target website.
"""
TARGET_URL = "https://tmailor.com/temp-mail"


"""
================================================================================
CUSTOMIZE: BLOCKLIST_PATH
================================================================================
Path to your existing blocklist file. Domains found that are NOT in this file
will be marked as "new discoveries."
"""
DEFAULT_BLOCKLIST_PATH = "disposable_email_blocklist.conf"


"""
================================================================================
CUSTOMIZE: SCREENSHOT_DIR
================================================================================
Directory where screenshots of newly discovered domains will be saved.
Only used in local mode (CI=false).
"""
SCREENSHOT_DIR_NAME = "domain_screenshots"


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]


class Config:
    """
    Configuration class that reads from environment variables.
    Modify default values here or set environment variables before running.

    Attributes:
        is_ci: True if running in CI environment (CI=true). Disables screenshots.

        max_attempts: Total number of email generations to attempt. Each attempt
            fetches one email from the website. The script stops after this many
            attempts regardless of results.

        max_unsuccessful_attempts: Number of consecutive attempts without finding
            a NEW domain before stopping early. This prevents wasting time when
            the website keeps returning domains already in your blocklist. Reset
            to 0 each time a new domain is found.

        take_screenshots: If True (local mode), saves screenshots of new domains.
            Automatically False in CI mode.
    """

    def __init__(self):
        self.is_ci = os.environ.get("CI", "").lower() == "true"
        self.max_attempts = int(os.environ.get("MAX_ATTEMPTS", 100))
        self.max_unsuccessful_attempts = int(
            os.environ.get("MAX_UNSUCCESSFUL_ATTEMPTS", 30)
        )
        self.take_screenshots = not self.is_ci

        self.pause_short = (3, 8)
        self.pause_medium = (10, 25)
        self.pause_long = (15, 30)
        self.pause_session = (480, 720)


config = Config()


def load_blocklist(blocklist_file=None):
    """
    Loads the existing blocklist of known disposable email domains.
    Returns a set of lowercase domain names.

    Customize: Change the default path or file format parsing as needed.
    """
    project_root = Path(__file__).parent.parent

    if blocklist_file:
        blocklist_path = Path(blocklist_file)
    else:
        blocklist_path = project_root / DEFAULT_BLOCKLIST_PATH

    if not blocklist_path.exists():
        logger.warning(f"Blocklist file not found: {blocklist_path}")
        return set()

    with open(blocklist_path) as f:
        domains = set(
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        )

    logger.info(f"Loaded {len(domains)} domains from blocklist: {blocklist_path}")
    return domains


def load_screenshotted_domains(screenshot_dir):
    """
    In local mode, domains with existing screenshots are considered "already
    processed" and should be treated the same as domains in the blocklist.

    This prevents re-screenshotting domains you've already captured, even if
    they haven't been added to the blocklist file yet.

    Returns a set of domain names extracted from screenshot filenames.
    """
    if not screenshot_dir.exists():
        return set()

    domains = set()
    for screenshot_file in screenshot_dir.glob("*.png"):
        domain = screenshot_file.stem.lower()
        domains.add(domain)

    if domains:
        logger.info(
            f"Found {len(domains)} existing screenshots (treated as known domains)"
        )

    return domains


def extract_domain(email):
    """
    Extracts the domain portion from an email address.
    Returns None if the email format is invalid.
    """
    if "@" in email:
        return email.split("@")[1].lower()
    return None


def pause(duration_range):
    """
    Pauses execution for a random duration within the given range.
    This mimics human behavior and helps avoid detection.

    Usage:
        pause(config.pause_short)   - Quick pause (3-8s)
        pause(config.pause_medium)  - Medium pause (10-25s)
        pause(config.pause_long)    - Long pause (15-30s)
        pause(config.pause_session) - Session break (8-12 min)
    """
    delay = random.uniform(*duration_range)
    time.sleep(delay)


def human_mouse_movement(page):
    """
    Simulates random mouse movements to appear more human-like.
    Helps avoid bot detection on some websites.
    """
    try:
        width = page.viewport_size["width"]
        height = page.viewport_size["height"]
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            page.mouse.move(x, y, steps=random.randint(10, 20))
            time.sleep(random.uniform(0.2, 0.5))
    except Exception:
        pass


def human_scroll(page):
    """
    Simulates random scrolling behavior to appear more human-like.
    """
    try:
        for _ in range(random.randint(1, 2)):
            scroll_amount = random.randint(30, 100)
            direction = random.choice([1, -1])
            page.mouse.wheel(0, scroll_amount * direction)
            time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass


def simulate_reading(page):
    """
    Combines mouse movement, waiting, and scrolling to simulate
    a user reading the page content.
    """
    human_mouse_movement(page)
    time.sleep(random.uniform(1, 3))
    human_scroll(page)
    human_mouse_movement(page)


def run_discovery(blocklist_file=None):
    """
    Main discovery function. Visits the target website, extracts email domains,
    and identifies which ones are NOT in the existing blocklist.

    This is an OPEN SEARCH - it discovers ANY domain from the website and checks
    if it's already in your blocklist. No predefined target list needed.

    Returns:
        0 if new domains were found, 1 otherwise
    """
    project_root = Path(__file__).parent.parent
    screenshot_dir = project_root / SCREENSHOT_DIR_NAME

    if config.take_screenshots:
        screenshot_dir.mkdir(exist_ok=True)
        logger.info(f"Running locally - screenshots saved to: {screenshot_dir}")
    else:
        logger.info("Running in CI mode - screenshots disabled")

    blocklist = load_blocklist(blocklist_file)

    if config.take_screenshots:
        screenshotted = load_screenshotted_domains(screenshot_dir)
        blocklist = blocklist | screenshotted

    new_domains_found = set()
    known_domains_found = set()
    all_domains_seen = set()

    logger.info(f"Starting open discovery (max {config.max_attempts} attempts)")
    logger.info(f"Known domains (blocklist + screenshots): {len(blocklist)}")

    attempt = 0
    unsuccessful_attempts = 0

    with sync_playwright() as p:
        while attempt < config.max_attempts:
            if unsuccessful_attempts >= config.max_unsuccessful_attempts:
                logger.warning(
                    f"No new domains in {config.max_unsuccessful_attempts} consecutive "
                    f"attempts, stopping early"
                )
                break

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            context = browser.new_context(
                viewport=random.choice(VIEWPORTS),
                user_agent=random.choice(USER_AGENTS),
                locale="en-US",
                timezone_id="America/New_York",
                geolocation={
                    "latitude": random.uniform(30, 45),
                    "longitude": random.uniform(-120, -75),
                },
                permissions=["geolocation"],
                color_scheme=random.choice(["light", "dark"]),
            )

            context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            """
            )

            page = context.new_page()

            try:
                pause(config.pause_short)
                logger.debug(f"Navigating to {TARGET_URL}...")

                for retry in range(3):
                    try:
                        page.goto(
                            TARGET_URL,
                            wait_until="domcontentloaded",
                            timeout=60000,
                        )
                        break
                    except Exception as nav_error:
                        if retry < 2:
                            logger.debug(
                                f"Navigation failed (attempt {retry + 1}/3), retrying..."
                            )
                            pause(config.pause_medium)
                        else:
                            raise nav_error

                logger.debug(f"Page loaded. Title: {page.title()}")
                pause(config.pause_medium)
                simulate_reading(page)

                emails_this_session = random.randint(3, 5)

                for email_num in range(emails_this_session):
                    attempt += 1

                    try:
                        """
                        ================================================================
                        CUSTOMIZE: EMAIL_SELECTOR
                        ================================================================
                        Change this selector to match where the email address is
                        displayed on your target website.
                        """
                        page.wait_for_selector(
                            "input[name='currentEmailAddress']", timeout=20000
                        )
                        pause(config.pause_short)
                        human_mouse_movement(page)

                        email_input = page.locator("input[name='currentEmailAddress']")
                        email_value = (
                            email_input.get_attribute("value")
                            or email_input.input_value()
                        )

                        if not email_value or email_value == "Please wait a moment":
                            pause(config.pause_medium)
                            email_value = (
                                email_input.get_attribute("value")
                                or email_input.input_value()
                            )

                        if email_value and "@" in email_value:
                            domain = extract_domain(email_value)
                            logger.info(
                                f"[{attempt}/{config.max_attempts}] Email: {email_value}"
                            )

                            if domain and domain not in all_domains_seen:
                                all_domains_seen.add(domain)

                                if domain not in blocklist:
                                    new_domains_found.add(domain)
                                    unsuccessful_attempts = 0
                                    logger.info(f"*** NEW DOMAIN FOUND: {domain} ***")

                                    if config.take_screenshots:
                                        try:
                                            screenshot_path = (
                                                screenshot_dir / f"{domain}.png"
                                            )
                                            page.screenshot(
                                                path=str(screenshot_path),
                                                full_page=False,
                                            )
                                            logger.info(
                                                f"Screenshot saved: {screenshot_path.name}"
                                            )
                                        except Exception as ss_err:
                                            logger.debug(f"Screenshot error: {ss_err}")
                                else:
                                    known_domains_found.add(domain)
                                    logger.info(
                                        f"Known domain (already in blocklist/screenshots): {domain}"
                                    )
                                    unsuccessful_attempts += 1
                            else:
                                unsuccessful_attempts += 1
                        else:
                            logger.debug(f"No valid email found: '{email_value}'")

                        simulate_reading(page)
                        pause(config.pause_short)

                        """
                        ================================================================
                        CUSTOMIZE: NEW_EMAIL_BUTTON_SELECTOR
                        ================================================================
                        Change this selector to match the "generate new email" button
                        on your target website.
                        """
                        new_email_btn = page.locator("#btnNewEmail")
                        new_email_btn.hover()
                        pause(config.pause_short)
                        new_email_btn.click()
                        pause(config.pause_long)

                    except Exception as e:
                        logger.debug(f"Email check error: {e}")
                        pause(config.pause_medium)

            except Exception as e:
                logger.debug(f"Session error: {e}")

            finally:
                browser.close()
                if attempt < config.max_attempts:
                    logger.info(
                        f"Session break ({config.pause_session[0]}-{config.pause_session[1]}s)"
                    )
                    pause(config.pause_session)

    return write_results(new_domains_found, known_domains_found, all_domains_seen)


def write_results(new_domains, known_domains, all_domains):
    """
    Outputs the discovery results to the console.

    Customize: Add file output, database storage, or API calls here
    to save the results in your preferred format.
    """
    logger.info("=" * 70)
    logger.info("DISCOVERY RESULTS")
    logger.info("=" * 70)

    logger.info(f"Total unique domains seen: {len(all_domains)}")
    logger.info(f"New domains (not in blocklist): {len(new_domains)}")
    logger.info(f"Known domains (in blocklist): {len(known_domains)}")

    if new_domains:
        logger.info("-" * 70)
        logger.info("NEW DOMAINS TO ADD TO BLOCKLIST:")
        for domain in sorted(new_domains):
            logger.info(f"  + {domain}")

    if known_domains:
        logger.info("-" * 70)
        logger.info(f"Known domains found: {sorted(known_domains)}")

    logger.info("=" * 70)

    return 0 if new_domains else 1


def main():
    parser = argparse.ArgumentParser(
        description="Discover new disposable email domains not in the blocklist"
    )
    parser.add_argument(
        "--blocklist-file",
        help="Path to blocklist file for comparison (default: disposable_email_blocklist.conf)",
    )
    args = parser.parse_args()

    try:
        sys.exit(run_discovery(args.blocklist_file))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
