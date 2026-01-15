#!/usr/bin/env python3

"""
Disposable Email Domain Verification Script

Verifies domains by visiting tmailor.com and logging when target domains are found.
Designed for both local development and CI/CD pipelines.

Usage:
    Local:
        source venv/bin/activate
        python scripts/verify_domains.py

    Custom domains file:
        python scripts/verify_domains.py --domains-file path/to/domains.txt

Environment Variables:
    MAX_ATTEMPTS        - Maximum verification attempts (default: 100)
    MAX_NO_RESULTS      - Stop after N attempts with no new results (default: 30)

Requirements:
    pip install playwright
    playwright install chromium
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

DEFAULT_DOMAINS = [
    "2fa.vn",
    "4save.net",
    "acc1s.com",
    "acc1s.net",
    "accclone.com",
    "aliban.org",
    "aruxprem.nl",
    "beelsil.com",
    "bigddns.com",
    "bigddns.net",
    "bigddns.org",
    "bookgame.org",
    "cdnmia.com",
    "choichay.com",
    "cloud-temp.com",
    "cloudtempmail.net",
    "coffeejadore.com",
    "connho.com",
    "contaco.org",
    "cordobes.fun",
    "dulich84.com",
    "eacademia.uk",
    "emailcoffeehouse.com",
    "emailhub.uk",
    "emailracc.com",
    "emailtik.com",
    "evoprem.my.id",
    "fastddns.net",
    "fastddns.org",
    "fbhotro.com",
    "jude1.name.ng",
    "kaldih.my.id",
    "kenhphim.net",
    "ket-qua.org",
    "kontoko.org",
    "libinit.com",
    "maillog.uk",
    "meocon.org",
    "mikfarm.com",
    "mikrotikvn.com",
    "mokook.com",
    "n-h-m.com",
    "nhmvn.com",
    "nickmxh.com",
    "pingddns.com",
    "pingddns.org",
    "pippoc.com",
    "pongpong.org",
    "qirauna.site",
    "rafxyzstore.my.id",
    "s3k.net",
    "smartha.shop",
    "sonphuongthinh.com",
    "spartanteam.net",
    "srfigservices.in",
    "tatadidi.com",
    "taxibmt.net",
    "tempmailor.com",
    "tempmailor.net",
    "tenhub.uk",
    "theparent.agency",
    "tikmail.org",
    "tiktakgrab.com",
    "tmailor.net",
    "tokmail.net",
    "trangzim.uk",
    "tsmtp.org",
    "tubeemail.com",
    "vinaemail.com",
    "vncctv.info",
    "vncctv.net",
    "x1ix.com",
    "xehop.org",
    "zozozo123.com",
]

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
    def __init__(self):
        self.max_attempts = int(os.environ.get("MAX_ATTEMPTS", 1000))
        self.max_no_results = int(os.environ.get("MAX_NO_RESULTS", 100))

        self.pause_short = (3, 8)
        self.pause_medium = (10, 25)
        self.pause_long = (15, 30)
        self.pause_session = (480, 720)


config = Config()


def load_domains(domains_file=None):
    if domains_file and Path(domains_file).exists():
        with open(domains_file) as f:
            domains = [
                line.strip().lower()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
        logger.info(f"Loaded {len(domains)} domains from {domains_file}")
        return set(domains)
    return set(d.lower() for d in DEFAULT_DOMAINS)


def extract_domain(email):
    if "@" in email:
        return email.split("@")[1].lower()
    return None


def pause(duration_range):
    delay = random.uniform(*duration_range)
    time.sleep(delay)


def human_mouse_movement(page):
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
    try:
        for _ in range(random.randint(1, 2)):
            scroll_amount = random.randint(30, 100)
            direction = random.choice([1, -1])
            page.mouse.wheel(0, scroll_amount * direction)
            time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass


def simulate_reading(page):
    human_mouse_movement(page)
    time.sleep(random.uniform(1, 3))
    human_scroll(page)
    human_mouse_movement(page)


def get_already_verified(domains):
    project_root = Path(__file__).parent.parent
    screenshot_dir = project_root / "domain_screenshots"
    verified = set()
    for domain in domains:
        if (screenshot_dir / f"{domain}.png").exists():
            verified.add(domain)
    return verified


def run_verification(domains_file=None):
    domains_to_find = load_domains(domains_file)

    already_verified = get_already_verified(domains_to_find)
    if already_verified:
        logger.info(
            f"Skipping {len(already_verified)} domains with existing screenshots"
        )
        domains_to_find = domains_to_find - already_verified

    if not domains_to_find:
        logger.info("All domains already have screenshots!")
        return 0

    found_domains = set()

    logger.info(
        f"Looking for {len(domains_to_find)} domains (max {config.max_attempts} attempts)"
    )

    attempt = 0
    no_results_counter = 0

    with sync_playwright() as p:
        while attempt < config.max_attempts:
            if found_domains == domains_to_find:
                logger.info("All domains verified!")
                break

            if no_results_counter >= config.max_no_results:
                logger.warning(
                    f"No new results in {config.max_no_results} attempts, stopping"
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
                logger.info("Navigating to tmailor.com...")
                page.goto(
                    "https://tmailor.com/temp-mail",
                    wait_until="networkidle",
                    timeout=90000,
                )
                logger.info(f"Page loaded. Title: {page.title()}")
                pause(config.pause_medium)
                simulate_reading(page)

                emails_this_session = random.randint(3, 5)
                logger.info(f"Will check {emails_this_session} emails this session")

                for email_num in range(emails_this_session):
                    if found_domains == domains_to_find:
                        break

                    attempt += 1

                    try:
                        logger.info(f"Waiting for email input (attempt {attempt})...")
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
                        logger.info(f"Initial email value: '{email_value}'")

                        if not email_value or email_value == "Please wait a moment":
                            logger.info("Email not ready, waiting longer...")
                            pause(config.pause_medium)
                            email_value = (
                                email_input.get_attribute("value")
                                or email_input.input_value()
                            )
                            logger.info(f"Email value after wait: '{email_value}'")

                        if email_value and "@" in email_value:
                            domain = extract_domain(email_value)
                            logger.info(
                                f"[{attempt}/{config.max_attempts}] Email: {email_value}"
                            )

                            if (
                                domain in domains_to_find
                                and domain not in found_domains
                            ):
                                found_domains.add(domain)
                                no_results_counter = 0
                                logger.info(
                                    f"*** MATCH FOUND: {domain} ({len(found_domains)}/{len(domains_to_find)}) ***"
                                )
                            else:
                                no_results_counter += 1
                        else:
                            logger.warning(f"No valid email found: '{email_value}'")

                        simulate_reading(page)
                        pause(config.pause_short)

                        new_email_btn = page.locator("#btnNewEmail")
                        new_email_btn.hover()
                        pause(config.pause_short)
                        new_email_btn.click()
                        logger.info("Clicked new email button")
                        pause(config.pause_long)

                    except Exception as e:
                        logger.warning(f"Email check error: {e}")
                        pause(config.pause_medium)

            except Exception as e:
                logger.error(f"Session error: {e}")

            finally:
                browser.close()
                if attempt < config.max_attempts:
                    logger.info(
                        f"Session break ({config.pause_session[0]}-{config.pause_session[1]}s)"
                    )
                    pause(config.pause_session)

    return write_results(domains_to_find, found_domains)


def write_results(domains_to_find, found_domains):
    logger.info("=" * 60)
    logger.info(f"RESULTS: {len(found_domains)}/{len(domains_to_find)} domains found")
    logger.info("=" * 60)

    if found_domains:
        logger.info(f"Found domains: {sorted(found_domains)}")

    missing = domains_to_find - found_domains
    if missing:
        logger.info(f"Not found ({len(missing)}): {sorted(missing)}")

    return 0 if found_domains else 1


def main():
    parser = argparse.ArgumentParser(description="Verify disposable email domains")
    parser.add_argument(
        "--domains-file", help="Path to file with domains to verify (one per line)"
    )
    args = parser.parse_args()

    try:
        sys.exit(run_verification(args.domains_file))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
