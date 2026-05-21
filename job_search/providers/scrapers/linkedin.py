"""LinkedIn job provider — Playwright-based two-phase scraper."""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .base import JobProvider


# ── Browser constants ──────────────────────────────────────────────────────────

ANTI_DETECTION_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = { runtime: {} };
"""

_SCROLL_LIST_JS = """
() => {
    const selectors = [
        '.jobs-search-results-list',
        '.scaffold-layout__list',
        '.jobs-search-results__list'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.scrollHeight > el.clientHeight) {
            el.scrollBy(0, 600);
            return sel;
        }
    }
    window.scrollBy(0, 600);
    return 'window';
}
"""

_LOCATION_JS = """() => {
    const strong = [...document.querySelectorAll('strong')].find(
        el => /\\d+\\s+(second|minute|hour|day|week|month|year)s?\\s+ago/.test(el.textContent)
    );
    if (!strong) return '';
    const p = strong.closest('p');
    if (!p) return '';
    const firstSpan = p.querySelector('span');
    return firstSpan ? firstSpan.textContent.trim() : '';
}"""


# ── Pure utility functions (module-level for easy testing) ─────────────────────

def extract_job_id(url: str) -> Optional[str]:
    match = re.search(r"/jobs/view/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"currentJobId=(\d+)", url)
    return match.group(1) if match else None


def _parse_page_title(page_title: str) -> str:
    """Extract job title from a LinkedIn page title string (first segment before ' | ')."""
    if "LinkedIn" not in page_title:
        return ""
    raw = re.sub(r"\s*\|\s*LinkedIn\b.*$", "", page_title).strip()
    if not raw:
        return ""
    title = raw.split(" | ")[0].strip()
    if " at " in title:
        title = title.partition(" at ")[0].strip()
    return title



def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_FRENCH_SECTION_RE = re.compile(
    r"(version\s+fran[çc]aise|en\s+fran[çc]ais|---\s*french|french\s+version"
    r"|\(french\s+below\)|bilingue)",
    re.IGNORECASE,
)


def _strip_french_section(text: str) -> str:
    """Remove bilingual French section from a job description, keeping only English."""
    m = _FRENCH_SECTION_RE.search(text)
    if m:
        return text[: m.start()].strip()
    return text


def _passes_pre_filter(
    title: str,
    location: str,
    cfg: dict,
    assume_remote: bool = False,
    company: str = "",
) -> tuple[bool, str]:
    """
    Code-based fast filter run before any detail page is fetched.
    cfg is the linkedin: section from config.yaml.
    Returns (True, "") to keep the job, or (False, reason) to skip it.
    """
    pre = cfg.get("pre_filter", {})
    loc_cfg = cfg.get("location_filter", {})

    # Blocked companies
    blocked_companies = {c.lower() for c in pre.get("blocked_companies", [])}
    if company.lower() in blocked_companies:
        return False, f"blocked company: {company}"

    # Staff-level titles
    staff_pattern = pre.get("staff_title_pattern", "")
    if staff_pattern and re.search(staff_pattern, title, re.IGNORECASE):
        return False, "staff-level title"

    # Lead/principal-level titles
    lead_pattern = pre.get("lead_principal_title_pattern", "")
    if lead_pattern and re.search(lead_pattern, title, re.IGNORECASE):
        return False, "lead/principal-level title"

    if not location:
        return True, ""

    loc = location.lower()

    metro_van = loc_cfg.get("metro_vancouver", [])
    blocked_non_bc = loc_cfg.get("blocked_non_bc_cities", [])

    if any(city in loc for city in metro_van):
        return True, ""

    if any(city in loc for city in blocked_non_bc):
        return False, f"non-BC city: {location}"

    is_remote = "remote" in loc
    has_bc = "british columbia" in loc or " bc" in loc or loc.startswith("bc")
    has_canada = "canada" in loc

    if assume_remote:
        return True, ""

    if is_remote and (has_canada or has_bc):
        return True, ""

    if (has_bc or has_canada) and not is_remote:
        return False, f"non-Metro BC onsite: {location}"

    if not has_bc and not has_canada and not is_remote:
        return False, f"outside BC/Canada: {location}"

    return True, ""


# ── Provider ───────────────────────────────────────────────────────────────────

class LinkedInProvider(JobProvider):
    """Playwright-based LinkedIn job scraper."""

    def __init__(
        self,
        output_dir: Path,
        debug_dir: Path,
        browser_data_dir: Path,
        linkedin_cfg: dict,
    ):
        self.output_dir = output_dir
        self.debug_dir = debug_dir
        self.browser_data_dir = browser_data_dir
        self.linkedin_cfg = linkedin_cfg

    # ── Public interface ──────────────────────────────────────────────────────

    def setup(self) -> None:
        """Open a visible browser for one-time LinkedIn login. Session saved to browser_data/."""
        from playwright.sync_api import sync_playwright

        print("Opening browser for LinkedIn login...")
        print("Log in, then come back here and press Enter.\n")

        with sync_playwright() as p:
            context = self._launch_context(p)
            page = context.new_page()
            page.goto("https://www.linkedin.com/login")
            input("Press Enter once you are logged in and can see your LinkedIn feed...")
            context.close()

        print("\nSession saved to browser_data/. Run `python main.py fetch` to start scraping.")

    def fetch_jobs(self, search_urls: List[dict]) -> List[dict]:
        """
        Phase 1: Click job cards → collect IDs + preview metadata → save job_ids checkpoint.
        Phase 2: Fetch full details for each job that passed the pre-filter.
        Returns list of raw job dicts.
        """
        from playwright.sync_api import sync_playwright

        if not self.browser_data_dir.exists() or not any(self.browser_data_dir.iterdir()):
            print("No saved session found. Run `python main.py fetch --setup` first.")
            return []

        jobs: dict[str, dict] = {}

        with sync_playwright() as p:
            context = self._launch_context(p)

            print("Checking session...")
            check = context.new_page()
            self._goto(check, "https://www.linkedin.com/feed/")
            time.sleep(random.uniform(3, 7))
            if any(x in check.url for x in ("login", "authwall", "checkpoint")):
                print("Session expired. Run `python main.py fetch --setup` to log in again.")
                check.close()
                context.close()
                return []
            print(f"Session active (at: {check.url[:70]})")
            check.close()

            for url_idx, url_entry in enumerate(search_urls):
                label = url_entry.get("label", f"url{url_idx+1}")
                before = len(jobs)
                print(f"\n[{url_idx+1}/{len(search_urls)}] '{label}' — {url_entry['url'][:70]}...")
                page = context.new_page()
                try:
                    self._scrape_search_url(page, url_entry, jobs, url_idx)
                except Exception as e:
                    print(f"  Error: {e}")
                finally:
                    page.close()
                added = len(jobs) - before
                print(f"  → '{label}' done: {added} passed pre-filter  (running total: {len(jobs)})")

            context.close()

        if not jobs:
            return []

        # Save IDs checkpoint — allows resuming detail fetch with --from-ids if interrupted.
        today = datetime.now().strftime("%Y-%m-%d")
        raw_dir = self.output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        ids_path = raw_dir / f"job_ids_{today}.json"
        ids_to_save = [
            {k: v for k, v in job.items() if k not in ("company", "description")}
            for job in jobs.values()
        ]
        with open(ids_path, "w", encoding="utf-8") as f:
            json.dump(ids_to_save, f, indent=2, ensure_ascii=False)
        print(f"\n{'─'*50}")
        print(f"Pre-filter done: {len(jobs)} jobs queued for detail fetch")
        print(f"IDs saved → {ids_path}  (resume later with --from-ids {ids_path})")
        print(f"{'─'*50}")

        self._fetch_all_details(jobs)
        jobs = self._filter_blocked_companies(jobs)
        return list(jobs.values())

    def fetch_jobs_from_ids(self, ids_path: str) -> List[dict]:
        """Read a saved job_ids JSON, re-apply pre-filter, and fetch full details."""
        path = Path(ids_path)
        if not path.exists():
            print(f"ERROR: {ids_path} not found.")
            return []

        with open(path, "r", encoding="utf-8") as f:
            raw: list[dict] = json.load(f)

        jobs: dict[str, dict] = {}
        skipped = 0
        for item in raw:
            job_id = item.get("id", "")
            if not job_id:
                continue
            ok, _ = _passes_pre_filter(
                item.get("title", ""), item.get("location", ""), self.linkedin_cfg,
                company=item.get("company", ""),
            )
            if not ok:
                skipped += 1
                continue
            jobs[job_id] = {
                "id": job_id,
                "title": item.get("title", ""),
                "company": item.get("company", ""),
                "location": item.get("location", ""),
                "url": item.get("url", f"https://www.linkedin.com/jobs/view/{job_id}/"),
                "description": "",
            }

        print(
            f"Loaded {len(raw)} IDs from {path.name}  →  "
            f"{len(jobs)} pass pre-filter, {skipped} skipped"
        )
        if not jobs:
            print("Nothing to fetch.")
            return []

        self._fetch_all_details(jobs)
        jobs = self._filter_blocked_companies(jobs)
        return list(jobs.values())

    # ── Private helpers ───────────────────────────────────────────────────────

    def _filter_blocked_companies(self, jobs: dict) -> dict:
        blocked = {
            c.lower()
            for c in self.linkedin_cfg.get("pre_filter", {}).get("blocked_companies", [])
        }
        if not blocked:
            return jobs
        filtered = {jid: j for jid, j in jobs.items() if j.get("company", "").lower() not in blocked}
        removed = len(jobs) - len(filtered)
        if removed:
            print(f"Blocked-company filter removed {removed} job(s) after detail fetch.")
        return filtered

    def _launch_context(self, p):
        """Persistent Playwright context reusing the same Chrome profile (always headed)."""
        self.browser_data_dir.mkdir(exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(self.browser_data_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/Vancouver",
            extra_http_headers={
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            },
        )
        context.add_init_script(ANTI_DETECTION_SCRIPT)
        return context

    def _goto(self, page, url: str, timeout: int = 30000) -> bool:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return True
        except Exception as e:
            err = str(e)
            if "ERR_HTTP_RESPONSE_CODE_FAILURE" in err or "ERR_TOO_MANY_REDIRECTS" in err:
                time.sleep(random.uniform(8, 20))
                return False
            raise

    def _save_html(self, page, label: str):
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / f"debug_{label}.html"
        try:
            path.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass

    def _fetch_all_details(self, jobs: dict[str, dict]):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            context = self._launch_context(p)
            detail_page = context.new_page()
            first_detail = True
            fetched_ok = 0

            print(f"Fetching details for {len(jobs)} jobs...")
            for i, (job_id, job) in enumerate(jobs.items(), 1):
                print(f"  [{i:>3}/{len(jobs)}] ", end="", flush=True)
                try:
                    self._fetch_job_detail(detail_page, job, save_html=first_detail)
                    first_detail = False
                    if job.get("description") or job.get("title"):
                        fetched_ok += 1
                except Exception as e:
                    print(f"ERROR fetching {job_id}: {e}")
                time.sleep(random.uniform(10, 25))

            detail_page.close()
            context.close()

        missing = len(jobs) - fetched_ok
        print(f"{'─'*50}")
        print(f"Details received: {fetched_ok}/{len(jobs)}", end="")
        if missing:
            print(f"  ({missing} missing — saved to output/debug/debug_detail_missing_*)")
        else:
            print()

    def _click_cards_collect_ids(self, page) -> dict[str, dict]:
        """Click each job card and collect job_id → {title, company, location}."""
        collected: dict[str, dict] = {}
        clicked_keys: set[str] = set()

        def _read_preview() -> dict:
            title = _parse_page_title(page.title())
            location = page.evaluate(_LOCATION_JS) or ""
            # company is intentionally "" — the card DOM does not expose it reliably.
            # Company name is only available after the detail page fetch.
            # Apply company blocklist in _filter_blocked_companies(), not here.
            return {"title": title, "company": "", "location": _clean(location)}

        preselected = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
        if preselected:
            pk = preselected.get_attribute("componentkey") or ""
            candidate = pk.split("_")[-1]
            if candidate.isdigit() and candidate not in collected:
                collected[candidate] = _read_preview()

        for _ in range(10):
            cards = page.query_selector_all(
                "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
            )
            found_new = False

            for card in cards:
                compkey = page.evaluate("e => e.getAttribute('componentkey')", card) or ""
                if compkey in clicked_keys:
                    continue
                clicked_keys.add(compkey)
                found_new = True

                before = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
                before_key = before.get_attribute("componentkey") if before else None

                try:
                    card.click()
                except Exception:
                    continue

                try:
                    page.wait_for_function(
                        """(bk) => {
                            const el = document.querySelector('[componentkey*="JobDetails_AboutTheJob_"]');
                            return el && el.getAttribute('componentkey') !== bk;
                        }""",
                        arg=before_key,
                        timeout=1500,
                    )
                except Exception:
                    continue

                detail = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
                if not detail:
                    continue

                detail_key = detail.get_attribute("componentkey") or ""
                job_id = detail_key.split("_")[-1]
                if job_id.isdigit() and job_id not in collected:
                    collected[job_id] = _read_preview()

                time.sleep(random.uniform(2, 6))

            if not found_new:
                break

            try:
                page.evaluate(_SCROLL_LIST_JS)
            except Exception:
                break
            time.sleep(random.uniform(1.5, 4))

        return collected

    def _wait_for_cards_change(self, page, from_key, timeout: int = 8000):
        try:
            page.wait_for_function(
                """(fk) => {
                    const cards = document.querySelectorAll(
                        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
                    );
                    if (!cards.length) return false;
                    return cards[0].getAttribute('componentkey') !== fk;
                }""",
                arg=from_key,
                timeout=timeout,
            )
        except Exception:
            time.sleep(random.uniform(4, 9))

    def _first_card_key(self, page) -> Optional[str]:
        cards = page.query_selector_all(
            "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
        )
        return page.evaluate("e => e.getAttribute('componentkey')", cards[0]) if cards else None

    def _scrape_search_url(self, page, url_entry: dict, jobs: dict, url_idx: int):
        search_url = url_entry["url"]
        label = url_entry.get("label", f"url{url_idx+1}")
        remote_only = url_entry.get("remote_only", False)

        self._goto(page, search_url, timeout=30000)
        time.sleep(random.uniform(5, 12))

        if any(x in page.url for x in ("login", "authwall", "checkpoint")):
            print("  Redirected to login — session may have expired.")
            return

        if remote_only:
            before_key = self._first_card_key(page)
            remote_btn = page.query_selector('[aria-label="Filter by Remote"]')
            if remote_btn:
                print(f"  Clicking Remote filter...")
                page.evaluate("el => el.click()", remote_btn)
                self._wait_for_cards_change(page, before_key, timeout=6000)
                print(f"  Remote filter applied.")
            else:
                print(f"  WARNING: Remote filter button not found — proceeding unfiltered.")

        page_num = 0
        while True:
            page_num += 1
            self._save_html(page, f"{label}_p{page_num}")

            preview = self._click_cards_collect_ids(page)

            new_count = 0
            skipped: list[str] = []
            for job_id, meta in preview.items():
                ok, reason = _passes_pre_filter(
                    meta["title"], meta["location"], self.linkedin_cfg,
                    assume_remote=remote_only,
                    company=meta.get("company", ""),
                )
                if not ok:
                    skipped.append(reason)
                    continue
                if job_id not in jobs:
                    jobs[job_id] = {
                        "id": job_id,
                        "title": meta["title"],
                        "company": meta["company"],
                        "location": meta["location"],
                        "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                        "description": "",
                        "_remote_only": remote_only,
                    }
                    new_count += 1

            dupe_count = len(preview) - new_count - len(skipped)
            parts = [f"found {len(preview)}", f"{new_count} new"]
            if skipped:
                reason_counts: dict[str, int] = {}
                for r in skipped:
                    key = r.split(":")[0].strip()
                    reason_counts[key] = reason_counts.get(key, 0) + 1
                reason_summary = ", ".join(
                    f"{k} ×{v}" if v > 1 else k for k, v in reason_counts.items()
                )
                parts.append(f"{len(skipped)} filtered ({reason_summary})")
            if dupe_count > 0:
                parts.append(f"{dupe_count} dupe")
            print(f"  Page {page_num}: {', '.join(parts)}")

            if len(preview) == 0 and page_num == 1:
                print(f"  0 jobs found on page 1. Check output/debug/debug_{label}_p1.html.")

            if len(preview) > 0 and len(skipped) / len(preview) >= 0.70:
                print(f"  ≥70% filtered ({len(skipped)}/{len(preview)}) — stopping early.")
                break

            next_btn = page.query_selector(
                "button[data-testid='pagination-controls-next-button-visible']"
            )
            if not next_btn:
                break

            first_key = self._first_card_key(page)
            page.keyboard.press("Escape")
            time.sleep(random.uniform(2, 5))
            page.evaluate("el => el.click()", next_btn)
            self._wait_for_cards_change(page, first_key)
            time.sleep(random.uniform(5, 14))

    def _fetch_job_detail(self, page, job: dict, save_html: bool = False):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        self._goto(page, job["url"], timeout=15000)

        try:
            page.wait_for_selector(
                "[data-sdui-component*='aboutTheJob'], h1, #job-details",
                timeout=5000,
            )
        except PlaywrightTimeout:
            pass

        if save_html:
            self._save_html(page, "detail_first")

        try:
            btn = page.query_selector(
                "[data-sdui-component*='aboutTheJob'] button[data-testid='expandable-text-button']"
            )
            if btn:
                btn.click(force=True)
                time.sleep(random.uniform(1, 3))
        except Exception:
            pass

        t = _parse_page_title(page.title())
        if t:
            job["title"] = t

        company = ""
        for el in page.query_selector_all('a[href*="/company/"]'):
            text = _clean(el.inner_text())
            if text:
                company = text
                break
        if not company:
            el = page.query_selector('a[href*="/company/"][aria-label]')
            if el:
                aria = el.get_attribute("aria-label") or ""
                m = re.match(r"Company,\s*(.+?)\.", aria)
                company = m.group(1).strip() if m else _clean(aria)
        if not company:
            for sel in [
                ".job-details-jobs-unified-top-card__company-name",
                ".jobs-unified-top-card__company-name",
                ".topcard__org-name-link",
                ".topcard__flavor--black-link",
            ]:
                el = page.query_selector(sel)
                if el:
                    text = _clean(el.inner_text())
                    if text:
                        company = text
                        break
        if company:
            job["company"] = company

        if not job.get("location"):
            location = page.evaluate(_LOCATION_JS)
            if location:
                job["location"] = _clean(location)

        desc_el = page.query_selector(
            "[data-sdui-component*='aboutTheJob'] [data-testid='expandable-text-box']"
        )
        if desc_el:
            raw_desc = desc_el.text_content() or ""
            raw_desc = raw_desc.replace("… more", "").replace("…more", "").strip()
            if raw_desc:
                job["description"] = _strip_french_section(_clean(raw_desc))

        if not job["description"]:
            for sel in [
                ".show-more-less-html__markup",
                ".description__text",
                "#job-details",
                ".jobs-description__content",
                ".jobs-description",
            ]:
                el = page.query_selector(sel)
                if el and el.inner_text().strip():
                    job["description"] = _strip_french_section(_clean(el.inner_text()))
                    break

        for el in page.query_selector_all(
            ".description__job-criteria-text, "
            ".job-details-jobs-unified-top-card__job-insight span"
        ):
            text = el.inner_text().strip()
            if any(t in text for t in ["Full-time", "Part-time", "Contract", "Temporary", "Internship"]):
                job["employment_type"] = text
                break

        if not job["description"]:
            self._save_html(page, f"detail_missing_desc_{job['id']}")

        company_display = job.get("company") or "?"
        title_display = job.get("title") or "?"
        location_display = job.get("location") or ""
        desc_len = len(job.get("description", ""))
        loc_note = f" · {location_display}" if location_display else ""
        desc_note = f"  [{desc_len} chars]" if desc_len else "  [NO DESCRIPTION]"
        print(f"{company_display} — {title_display[:45]}{loc_note}{desc_note}")
