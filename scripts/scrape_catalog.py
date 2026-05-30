"""
scrape_catalog.py
=================
Scrapes the SHL product catalog (Individual Test Solutions ONLY) and writes a
clean JSON file that the rest of the app can consume.

Why a separate script?
    Scraping is slow and network-dependent. We do it ONCE, save the result to
    `data/catalog.json`, and the live service just reads that file. The service
    never scrapes at request time -> fast, deterministic, offline-friendly.

What it produces (data/catalog.json):
    [
      {
        "name": "Java 8 (New)",
        "url": "https://www.shl.com/products/product-catalog/view/java-8-new/",
        "test_type": ["K"],
        "remote_testing": true,
        "adaptive_irt": false,
        "description": "Multi-choice test that measures ...",
        "job_levels": "Mid-Professional, Professional Individual Contributor"
      },
      ...
    ]

Run:
    python scripts/scrape_catalog.py                 # full scrape + descriptions
    python scripts/scrape_catalog.py --no-descriptions   # faster, listing only
    python scripts/scrape_catalog.py --max-pages 3   # quick test
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://www.shl.com"
CATALOG = BASE + "/products/product-catalog/"
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "catalog.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SHL-Recommender-Scraper/1.0)"}
PAGE_SIZE = 12  # the SHL catalog shows 12 rows per page
SSL_CTX = ssl.create_default_context()


def fetch(url: str, timeout: int = 25) -> str:
    """Download a URL and return its HTML as text. Raises on failure."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return resp.read().decode("utf-8", "ignore")


def isolate_individual_table(html: str) -> str:
    """
    The catalog page renders TWO tables: 'Pre-packaged Job Solutions' and
    'Individual Test Solutions'. We only want the second one, so we slice the
    HTML from the 'Individual Test Solutions' heading to the next </table>.
    """
    marker = "Individual Test Solutions"
    start = html.find(marker)
    if start == -1:
        return ""
    end = html.find("</table>", start)
    return html[start: end if end != -1 else len(html)]


# Individual-test rows have NO data-course-id (unlike pre-packaged rows), so we
# match any <tr> inside the already-isolated Individual table and keep the ones
# that contain a product link.
ROW_RE = re.compile(r"<tr\b(.*?)</tr>", re.S)
LINK_RE = re.compile(r'<a href="(/products/product-catalog/view/[^"]+)">(.*?)</a>', re.S)
GENERAL_TD_RE = re.compile(r'<td class="custom__table-heading__general[^"]*">(.*?)</td>', re.S)
KEY_RE = re.compile(r'product-catalogue__key"[^>]*>([A-Z])<')


def parse_rows(table_html: str) -> list[dict]:
    """Turn the Individual-Test-Solutions table HTML into structured rows."""
    rows = []
    for row_html in ROW_RE.findall(table_html):
        link = LINK_RE.search(row_html)
        if not link:
            continue  # header row / spacer -> skip
        path, name = link.group(1), re.sub(r"\s+", " ", link.group(2)).strip()
        # The three 'general' cells are, in order: Remote, Adaptive, Test Type.
        cells = GENERAL_TD_RE.findall(row_html)
        remote = len(cells) > 0 and "-yes" in cells[0]
        adaptive = len(cells) > 1 and "-yes" in cells[1]
        keys = KEY_RE.findall(row_html)  # ['K'] or ['A','B','P', ...]
        rows.append({
            "name": name,
            "url": BASE + path,
            "test_type": keys,
            "remote_testing": remote,
            "adaptive_irt": adaptive,
            "description": "",
            "job_levels": "",
        })
    return rows


DESC_RE = re.compile(r"Description</h4>\s*<p>(.*?)</p>", re.S)
JOBLVL_RE = re.compile(r"Job levels</h4>\s*<p>(.*?)</p>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub("", text)).strip()


def enrich(item: dict) -> dict:
    """Visit a product's detail page and pull its description + job levels."""
    try:
        html = fetch(item["url"])
        d = DESC_RE.search(html)
        j = JOBLVL_RE.search(html)
        if d:
            item["description"] = clean(d.group(1))
        if j:
            item["job_levels"] = clean(j.group(1))
    except Exception as exc:  # one bad page must not kill the whole scrape
        print(f"  ! description failed for {item['name']}: {exc}", file=sys.stderr)
    return item


def scrape_listing(max_pages: int | None) -> list[dict]:
    """Walk every page of the Individual Test Solutions table."""
    items: dict[str, dict] = {}  # keyed by URL -> automatic de-duplication
    start, page = 0, 0
    while True:
        if max_pages is not None and page >= max_pages:
            break
        url = f"{CATALOG}?start={start}&type=1"
        print(f"page {page + 1}: {url}")
        html = fetch(url)
        rows = parse_rows(isolate_individual_table(html))
        new = [r for r in rows if r["url"] not in items]
        if not new:  # no fresh rows -> we've reached the end
            break
        for r in new:
            items[r["url"]] = r
        start += PAGE_SIZE
        page += 1
        time.sleep(0.4)  # be polite to the server
    return list(items.values())


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape SHL Individual Test Solutions")
    ap.add_argument("--no-descriptions", action="store_true",
                    help="skip per-product detail pages (much faster)")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="limit number of listing pages (for quick tests)")
    ap.add_argument("--workers", type=int, default=8,
                    help="parallel workers for description enrichment")
    args = ap.parse_args()

    print("Scraping catalog listing ...")
    items = scrape_listing(args.max_pages)
    print(f"Found {len(items)} individual test solutions.")

    if not args.no_descriptions:
        print("Fetching descriptions (this is the slow part) ...")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(enrich, it): it for it in items}
            done = 0
            for _ in as_completed(futures):
                done += 1
                if done % 25 == 0:
                    print(f"  {done}/{len(items)} descriptions done")

    items.sort(key=lambda x: x["name"].lower())
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    print(f"Wrote {len(items)} items -> {DATA_FILE}")


if __name__ == "__main__":
    main()
