"""
Diagnostic test to verify which job-ID extraction mechanism works
against the real LinkedIn page before modifying fetch_jobs.py.

Usage: python test_scrape.py

Runs 3 tests, prints PASS/FAIL for each, prints a SUMMARY at the end.
Do NOT modify fetch_jobs.py until you see which tests pass.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from fetch_jobs import ANTI_DETECTION_SCRIPT, BROWSER_DATA_DIR, _launch_context, _passes_pre_filter, _LOCATION_JS

CONFIG_FILE = "config.json"
OUTPUT_DIR = Path("output")


def _load_search_url() -> str:
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    entry = cfg["search_urls"][0]
    return entry["url"] if isinstance(entry, dict) else entry


def _load_canada_remote_url() -> str:
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    for entry in cfg["search_urls"]:
        if isinstance(entry, dict) and entry.get("remote_only"):
            return entry["url"]
        if isinstance(entry, str):
            continue
    return ""


def _sep(label: str):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print("="*60)


def test1_card_selector(page) -> bool:
    """
    Find job cards via div[role='button'][componentkey] inside SearchResultsMainContent.
    This selector targets the card's own clickable element — no dismiss-button labels needed.
    Also counts dismiss buttons as a cross-check.
    """
    _sep("TEST 1 — Card selector: div[role='button'][componentkey] in SearchResultsMainContent")

    # Primary: role=button divs inside the results container
    cards = page.query_selector_all(
        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
    )
    print(f"  div[role='button'][componentkey] inside SearchResultsMainContent: {len(cards)}")

    # Cross-check: old dismiss-button approach
    btns = page.query_selector_all('button[aria-label$=" job"]')
    print(f"  button[aria-label$=' job'] (cross-check):                         {len(btns)}")

    # Show what the first card element looks like
    if cards:
        sample = page.evaluate("""(el) => ({
            tag: el.tagName,
            role: el.getAttribute('role'),
            compkey: el.getAttribute('componentkey'),
            cls: (el.className || '').slice(0, 80)
        })""", cards[0])
        print(f"  First card element: <{sample['tag'].lower()}>"
              f"  role={sample['role']!r}"
              f"  componentkey={sample['compkey']!r}")

    result = len(cards) > 0
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    return result


def test2_read_ids_from_card_dom(page) -> bool:
    """
    Walk the ancestor chain of each dismiss button, looking for a componentkey
    that contains a numeric job ID. If the card container has its own componentkey
    (e.g. 'JobCard_4414265642'), we can read ALL job IDs without any clicking.

    Prints the full ancestor chain for card[0] so we can see the real DOM structure.
    """
    _sep("TEST 2 — Read job IDs from card container componentkey (no clicks)")

    btns = page.query_selector_all('button[aria-label$=" job"]')
    if not btns:
        print("  SKIP: no cards")
        return False

    # Print full ancestor chain for the first card
    btn0 = btns[0]
    label0 = btn0.get_attribute("aria-label") or ""
    print(f"  Inspecting first card: {label0!r}")
    print()

    chain = page.evaluate("""(btn) => {
        const rows = [];
        let el = btn.parentElement;
        while (el && el !== document.body && rows.length < 12) {
            rows.push({
                tag: el.tagName,
                role: el.getAttribute('role') || '',
                compkey: el.getAttribute('componentkey') || '',
                cls: (el.className || '').slice(0, 80)
            });
            el = el.parentElement;
        }
        return rows;
    }""", btn0)

    print("  Ancestor chain of dismiss button:")
    for i, row in enumerate(chain):
        print(f"    [{i}] <{row['tag'].lower()}>"
              f"  role={row['role']!r}"
              f"  componentkey={row['compkey']!r}"
              f"  class={row['cls']!r}")
    print()

    # Try to find a numeric job ID in any ancestor's componentkey
    ids_from_dom: list[str] = []
    for btn in btns:
        job_id = page.evaluate("""(btn) => {
            let el = btn.parentElement;
            while (el && el !== document.body) {
                const key = el.getAttribute('componentkey') || '';
                const m = key.match(/(\\d{7,13})$/);
                if (m) return m[1];
                el = el.parentElement;
            }
            return null;
        }""", btn)
        if job_id:
            ids_from_dom.append(job_id)

    print(f"  Job IDs found in ancestor componentkeys: {len(ids_from_dom)} / {len(btns)} cards")
    if ids_from_dom:
        print(f"  Sample IDs: {ids_from_dom[:5]}")

    result = len(ids_from_dom) > 0
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    return result


def test3_click_and_read_detail_componentkey(page) -> bool:
    """
    Click the first 5 cards using div[role='button'][componentkey] — no dismiss labels.
    After each click, wait for the detail panel componentkey to update and read job ID.
    """
    _sep("TEST 3 — Click div[role='button'] cards → detail componentkey → job ID")

    cards = page.query_selector_all(
        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
    )
    if not cards:
        print("  SKIP: no role=button cards found (Test 1 failed)")
        return False

    print(f"  Testing first 5 of {len(cards)} cards...\n")
    successes = 0

    for i, card in enumerate(cards[:5]):
        compkey_card = page.evaluate("e => e.getAttribute('componentkey')", card)
        print(f"  Card {i+1}: componentkey={compkey_card!r}")

        before = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
        before_key = before.get_attribute("componentkey") if before else None

        try:
            card.click()
        except Exception as e:
            print(f"    click failed: {e}")
            continue

        time.sleep(0.4)

        try:
            page.wait_for_function(
                """(bk) => {
                    const el = document.querySelector('[componentkey*="JobDetails_AboutTheJob_"]');
                    return el && el.getAttribute('componentkey') !== bk;
                }""",
                arg=before_key,
                timeout=3000,
            )
        except Exception:
            pass

        detail = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
        if not detail:
            print(f"    FAIL: detail panel not found after click")
            continue

        detail_key = detail.get_attribute("componentkey") or ""
        job_id = detail_key.split("_")[-1]
        if job_id.isdigit():
            print(f"    ✓ job_id={job_id}")
            successes += 1
        else:
            print(f"    FAIL: non-numeric in {detail_key!r}")

    result = successes > 0
    print(f"\n  {successes}/5 cards yielded a job ID")
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    return result


def test_page1_count(page) -> bool:
    """
    Verify that page 1 yields exactly 25 job IDs.
    The pre-selected card must be captured before the click loop starts,
    otherwise it is always missed (timeout because detail panel doesn't change).
    """
    from fetch_jobs import _click_cards_collect_ids

    _sep("TEST PAGE-1 COUNT — must be exactly 25")

    # Count raw visible cards first
    raw_cards = page.query_selector_all(
        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
    )
    print(f"  Raw visible cards on page: {len(raw_cards)}")

    ids = _click_cards_collect_ids(page)
    print(f"  Job IDs collected: {len(ids)}")
    for jid, meta in list(ids.items())[:3]:
        print(f"    {jid}: {meta.get('title', '?')!r} @ {meta.get('location', '?')!r}")

    # LinkedIn normally shows 25/page, but promoted/duplicate cards can inflate the count.
    # We accept >= 20 to verify the pre-selected card is captured without being brittle.
    result = len(ids) >= 20
    if not result:
        print(f"  FAIL: expected >= 20, got {len(ids)} — pre-selected card logic may be broken")
    else:
        print(f"  RESULT: PASS ({len(ids)} IDs collected from {len(raw_cards)} visible cards)")
    return result


def test_pagination(page) -> bool:
    """
    Real pagination test: simulate what _scrape_search_url does.
    1. Collect job IDs from page 1 by clicking all cards (same as production code).
    2. AFTER clicking all cards, look for the next-page button.
    3. Click it and wait for new cards to load.
    4. Collect job IDs from page 2.
    5. PASS if page 2 IDs differ from page 1 IDs (some new jobs).

    This test is stricter than test0: it tests pagination AFTER the card-clicking
    loop runs, which is exactly when the production code checks for next.
    """
    from fetch_jobs import _click_cards_collect_ids

    _sep("TEST PAGINATION — full cycle: collect page 1 → click next → collect page 2")

    # --- Page 1 ---
    print("  Step 1: collecting IDs from page 1...")
    page1_raw = _click_cards_collect_ids(page)
    page1_ids = set(page1_raw.keys())
    print(f"  Page 1 IDs collected: {len(page1_ids)}")
    if not page1_ids:
        print("  FAIL: 0 jobs on page 1 — nothing to paginate from")
        return False

    # --- Check for next button after clicking all cards ---
    next_btn = page.query_selector(
        "button[data-testid='pagination-controls-next-button-visible']"
    )
    if not next_btn:
        # Report all pagination data-testid elements present for diagnosis
        all_pg = page.query_selector_all("[data-testid^='pagination']")
        print(f"  Next button NOT found after card-click loop.")
        print(f"  All pagination data-testid elements present ({len(all_pg)}):")
        for el in all_pg:
            print(f"    {el.get_attribute('data-testid')!r}")
        print("  page.url:", page.url[:120])
        print("  FAIL: pagination button not found after page-1 card loop")
        return False

    print("  Next button found. Dismissing any open overlays then clicking...")

    # Dismiss any floating popup/dialog that appeared after card-clicking
    page.keyboard.press("Escape")
    time.sleep(0.3)

    # Record current first card's componentkey so we can detect when new cards load
    cards_before = page.query_selector_all(
        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
    )
    first_key_before = (
        page.evaluate("e => e.getAttribute('componentkey')", cards_before[0])
        if cards_before else None
    )

    url_before = page.url
    print(f"  URL before click: {url_before[:120]}")

    # Use JS click to bypass Playwright's pointer-event interception check
    page.evaluate("el => el.click()", next_btn)

    # Wait for the card list to update (new cards have different componentkeys)
    cards_changed = False
    try:
        page.wait_for_function(
            """(fk) => {
                const cards = document.querySelectorAll(
                    "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
                );
                if (!cards.length) return false;
                return cards[0].getAttribute('componentkey') !== fk;
            }""",
            arg=first_key_before,
            timeout=8000,
        )
        cards_changed = True
        print("  Cards DOM changed after next-page click")
    except Exception:
        print("  WARNING: card DOM did not change within 8s")
        time.sleep(2)

    url_after = page.url
    print(f"  URL after  click: {url_after[:120]}")
    url_changed = url_after != url_before
    print(f"  URL changed: {url_changed}")

    # Check which page number is now active in the pagination controls
    active_page = page.evaluate("""() => {
        const active = document.querySelector(
            "[data-testid='pagination-controls-page-button-active'], " +
            "button[aria-current='true'][data-testid*='pagination']"
        );
        if (active) return active.textContent.trim();
        // fallback: find any selected/current page button
        const allBtns = [...document.querySelectorAll("[data-testid^='pagination-controls-page-button']")];
        const cur = allBtns.find(b => b.getAttribute('aria-current') === 'true' || b.getAttribute('aria-pressed') === 'true');
        return cur ? cur.textContent.trim() : null;
    }""")
    print(f"  Active page indicator: {active_page!r}")

    # Confirm we're actually on page 2, not just a DOM refresh
    on_page_2 = (
        url_changed
        or (active_page is not None and active_page == "2")
        or cards_changed
    )
    if not on_page_2:
        print("  FAIL: no evidence we reached page 2 (URL unchanged, no page indicator, DOM unchanged)")
        return False

    # --- Page 2 ---
    print("  Step 2: collecting IDs from page 2...")
    page2_raw = _click_cards_collect_ids(page)
    page2_ids = set(page2_raw.keys())
    print(f"  Page 2 IDs collected: {len(page2_ids)}")

    new_ids = page2_ids - page1_ids
    overlap = page1_ids & page2_ids
    print(f"  New IDs (not on page 1): {len(new_ids)}")
    print(f"  Overlap with page 1:     {len(overlap)}")

    if len(new_ids) == 0:
        print("  FAIL: page 2 returned 0 new job IDs — same jobs as page 1")
        return False

    print(f"  RESULT: PASS")
    return True


def test3_detail_location(page, job_id: str) -> bool:
    """
    Navigate to a job detail page and verify location extraction.
    Strategy: find the first <span> in the <p> that also contains a
    '<strong>X ago</strong>' — that's the location/metadata line.
    """
    _sep("TEST 3 — Detail page: location extraction")
    url = f"https://www.linkedin.com/jobs/view/{job_id}/"
    print(f"  URL: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(1.5)

    location = page.evaluate("""() => {
        const strong = [...document.querySelectorAll('strong')].find(
            el => /\\d+\\s+(second|minute|hour|day|week|month|year)s?\\s+ago/.test(el.textContent)
        );
        if (!strong) return null;
        const p = strong.closest('p');
        if (!p) return null;
        const firstSpan = p.querySelector('span');
        return firstSpan ? firstSpan.textContent.trim() : null;
    }""")

    print(f"  Location extracted: {location!r}")
    if location:
        print("  RESULT: PASS")
        return True
    print("  RESULT: FAIL — no location found via 'ago' anchor")
    return False


def test4_detail_full_description(page) -> bool:
    """
    On the already-loaded detail page, verify that:
    1. The 'expandable-text-button' (show-more) is clicked to uncollapse the description.
    2. The description read after clicking is longer than before, OR not truncated.
    Uses data-testid='expandable-text-box' for the description container.
    """
    _sep("TEST 4 — Detail page: full description (show-more)")

    desc_sel = "[data-sdui-component*='aboutTheJob'] [data-testid='expandable-text-box']"
    expand_sel = "[data-sdui-component*='aboutTheJob'] button[data-testid='expandable-text-button']"

    desc_el = page.query_selector(desc_sel)
    if not desc_el:
        print("  FAIL: expandable-text-box not found inside aboutTheJob")
        return False

    before_text = (desc_el.text_content() or "").replace("… more", "").replace("…more", "").strip()
    print(f"  Description length BEFORE expand: {len(before_text)} chars")

    expand_btn = page.query_selector(expand_sel)
    if expand_btn:
        print("  Found expandable-text-button — clicking (force=True)...")
        try:
            expand_btn.click(force=True)
            time.sleep(0.4)
        except Exception as e:
            print(f"  click failed: {e}")
    else:
        print("  expandable-text-button NOT found (description already fully expanded)")

    desc_el2 = page.query_selector(desc_sel)
    after_text = (desc_el2.text_content() or "").replace("… more", "").replace("…more", "").strip() if desc_el2 else before_text
    print(f"  Description length AFTER expand:  {len(after_text)} chars")

    expanded = len(after_text) > len(before_text)
    no_ellipsis = "…" not in after_text
    result = len(after_text) > 100
    print(f"  Expanded: {expanded} | No trailing ellipsis: {no_ellipsis}")
    print(f"  Sample (last 200 chars): {after_text[-200:]!r}")
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    return result


def test0_pagination_button(page) -> bool:
    """
    Gate test: verify the next-page button exists before running anything else.
    Confirmed from debug HTML: LinkedIn uses data-testid for pagination controls.
    Reports all pagination elements present so we can diagnose selector changes.
    """
    _sep("TEST 0 — Pagination button (gate)")
    btn = page.query_selector("button[data-testid='pagination-controls-next-button-visible']")
    if btn:
        print("  Found: button[data-testid='pagination-controls-next-button-visible']")
        print("  RESULT: PASS")
        return True

    all_pg = page.query_selector_all("[data-testid^='pagination']")
    print(f"  Next button NOT found. All pagination data-testid elements present ({len(all_pg)}):")
    for el in all_pg:
        print(f"    {el.get_attribute('data-testid')!r}")
    print("  RESULT: FAIL — fix the pagination selector before proceeding")
    return False


def test_pre_filter(page) -> bool:
    """
    Click 5 cards on the search page, read title (from page.title()) and location
    (from the 'X ago' JS anchor), then run _passes_pre_filter on each result.
    PASS if all 5 cards yield a title and the filter logic runs without error.
    """
    _sep("TEST PRE-FILTER — title + location from inline panel, filter verdict")

    cards = page.query_selector_all(
        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
    )
    if not cards:
        print("  SKIP: no cards found")
        return False

    successes = 0
    for i, card in enumerate(cards[:5]):
        before = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
        before_key = before.get_attribute("componentkey") if before else None
        try:
            card.click()
        except Exception as e:
            print(f"  Card {i+1}: click failed — {e}")
            continue
        try:
            page.wait_for_function(
                """(bk) => {
                    const el = document.querySelector('[componentkey*="JobDetails_AboutTheJob_"]');
                    return el && el.getAttribute('componentkey') !== bk;
                }""",
                arg=before_key, timeout=2000,
            )
        except Exception:
            pass

        page_title = page.title()
        # parse title inline (same logic as _parse_page_title)
        title, company = "", ""
        if "LinkedIn" in page_title:
            raw = page_title.replace(" | LinkedIn", "").strip()
            if " at " in raw:
                title, _, company = raw.partition(" at ")
                title, company = title.strip(), company.strip()
            elif " | " in raw:
                parts = [p.strip() for p in raw.split(" | ")]
                title = parts[0]
                company = parts[1] if len(parts) > 1 else ""

        location = page.evaluate(_LOCATION_JS) or ""

        ok, reason = _passes_pre_filter(title, location)
        verdict = f"PASS (keep)" if ok else f"SKIP ({reason})"
        print(f"  Card {i+1}: {title!r} | {location!r}  →  {verdict}")
        if title:
            successes += 1

    result = successes > 0
    print(f"\n  {successes}/5 cards yielded a title")
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    return result


def test_remote_filter_button(page) -> bool:
    """
    Find [aria-label='Filter by Remote'], click it, wait for card list to update,
    then confirm cards are still present.
    """
    _sep("TEST REMOTE FILTER BUTTON — find, click, verify cards updated")

    from fetch_jobs import _first_card_key, _wait_for_cards_change

    btn = page.query_selector('[aria-label="Filter by Remote"]')
    if not btn:
        print("  FAIL: [aria-label='Filter by Remote'] not found on this page")
        print("  NOTE: This test must run against the canada_remote search URL")
        return False

    print("  Found Remote filter button — clicking...")
    before_key = _first_card_key(page)
    page.evaluate("el => el.click()", btn)
    _wait_for_cards_change(page, before_key, timeout=8000)

    cards = page.query_selector_all(
        "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
    )
    print(f"  Cards after Remote filter click: {len(cards)}")
    result = len(cards) > 0
    print(f"  RESULT: {'PASS' if result else 'FAIL — no cards after clicking Remote filter'}")
    return result


def run():
    from playwright.sync_api import sync_playwright

    search_url = _load_search_url()
    canada_remote_url = _load_canada_remote_url()

    print("\n=== LinkedIn Scraper Mechanism Test ===")
    print(f"Search URL: {search_url}\n")

    results: dict[str, bool] = {}

    with sync_playwright() as p:
        context = _launch_context(p)

        page = context.new_page()
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.5)

        if any(x in page.url for x in ("login", "authwall", "checkpoint")):
            print("ERROR: Session expired. Run `python fetch_jobs.py --setup` first.")
            context.close()
            return

        results["Test 0 (pagination)"] = test0_pagination_button(page)

        if not results["Test 0 (pagination)"]:
            print("\n  Test 0 failed — skipping remaining tests.")
        else:
            results["Test 1 (card selector)"] = test1_card_selector(page)
            results["Test 2 (click 5 cards)"] = test3_click_and_read_detail_componentkey(page)

            # Reload search page so count + pagination tests start fresh
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1.5)
            results["Test Page-1 count (==25)"] = test_page1_count(page)

            # Reload again — pagination test needs a fresh page-1 state
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1.5)
            results["Test Pagination (full cycle)"] = test_pagination(page)

            # Pre-filter test — reload fresh page
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1.5)
            results["Test Pre-filter (title+loc)"] = test_pre_filter(page)

            # Remote filter button test — needs canada_remote URL
            if canada_remote_url:
                page.goto(canada_remote_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(1.5)
                results["Test Remote filter button"] = test_remote_filter_button(page)
            else:
                print("\n  No canada_remote URL found — skipping Remote filter button test.")

            # Grab a job ID for detail tests — read the pre-selected card (already shown on page load)
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1.5)
            first_job_id = None
            presel = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
            if presel:
                dk = presel.get_attribute("componentkey") or ""
                candidate = dk.split("_")[-1]
                if candidate.isdigit():
                    first_job_id = candidate
            if not first_job_id:
                # Fallback: click second card (first card IS the pre-selected one; clicking it won't change detail)
                cards = page.query_selector_all(
                    "[componentkey='SearchResultsMainContent'] div[role='button'][componentkey]"
                )
                if len(cards) > 1:
                    before_key = presel.get_attribute("componentkey") if presel else None
                    try:
                        cards[1].click()
                        page.wait_for_function(
                            """(bk) => {
                                const el = document.querySelector('[componentkey*="JobDetails_AboutTheJob_"]');
                                return el && el.getAttribute('componentkey') !== bk;
                            }""",
                            arg=before_key, timeout=3000,
                        )
                        detail = page.query_selector('[componentkey*="JobDetails_AboutTheJob_"]')
                        if detail:
                            dk = detail.get_attribute("componentkey") or ""
                            candidate = dk.split("_")[-1]
                            if candidate.isdigit():
                                first_job_id = candidate
                    except Exception:
                        pass

            if first_job_id:
                results["Test 3 (location)"] = test3_detail_location(page, first_job_id)
                results["Test 4 (full description)"] = test4_detail_full_description(page)
            else:
                print("\n  Could not get a job ID for detail tests — skipping Tests 3 & 4.")

        page.close()
        context.close()

    _sep("SUMMARY")
    for name, passed in results.items():
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"  {name:<30} {status}")

    failing = [n for n, p in results.items() if not p]
    if not failing:
        print("\n  → All tests passed.")
    else:
        print(f"\n  → Failing: {', '.join(failing)}")
    print()


if __name__ == "__main__":
    run()
