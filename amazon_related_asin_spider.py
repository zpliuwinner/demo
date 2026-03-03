#!/usr/bin/env python3
"""Amazon related ASIN crawler (stdlib-only).

Given a source ASIN, fetches the product detail page and extracts other ASINs
that appear in common recommendation blocks and product links.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ASIN_TOKEN_RE = re.compile(r"\b([A-Z0-9]{10})\b", re.IGNORECASE)
DP_RE = re.compile(r"/dp/([A-Z0-9]{10})(?:[/?&#]|$)", re.IGNORECASE)
DATA_ASIN_RE = re.compile(r'data-asin=["\']([A-Z0-9]{10})["\']', re.IGNORECASE)

RELATED_HINTS = (
    "sims",
    "p13n",
    "sp_detail",
    "similarities_feature_div",
    "desktop-dp-sims",
    "purchase-sims-feature",
    "related",
    "frequently bought",
    "customers also",
)


@dataclass
class CrawlResult:
    source_asin: str
    related_asins: list[str]
    url: str


def normalize_asin(asin: str) -> str:
    value = asin.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", value):
        raise ValueError(f"Invalid ASIN: {asin!r}. ASIN must be 10 letters/numbers.")
    return value


def build_product_url(asin: str, marketplace: str = "com") -> str:
    return f"https://www.amazon.{marketplace}/dp/{asin}"


def fetch_html(url: str, timeout: float = 20.0) -> tuple[str, str]:
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            body = resp.read().decode("utf-8", errors="ignore")
            final_url = resp.geturl()
    except HTTPError as e:
        raise RuntimeError(f"HTTP error {e.code} for {url}") from e
    except URLError as e:
        raise RuntimeError(f"Network error for {url}: {e}") from e
    return unescape(body), final_url


def parse_related_asins(html: str, source_asin: str, limit: int = 30) -> list[str]:
    source_asin = source_asin.upper()
    seen = {source_asin}
    ordered: list[str] = []

    def add(asin: str) -> None:
        asin = asin.upper()
        if asin not in seen:
            seen.add(asin)
            ordered.append(asin)

    # Priority 1: Parse candidate ASINs in windows around related block hints.
    lowered = html.lower()
    window = 3000
    for hint in RELATED_HINTS:
        start = 0
        while True:
            idx = lowered.find(hint, start)
            if idx == -1:
                break
            chunk = html[max(0, idx - window) : idx + window]
            for asin in DATA_ASIN_RE.findall(chunk):
                add(asin)
            for asin in DP_RE.findall(chunk):
                add(asin)
            start = idx + len(hint)
            if len(ordered) >= limit:
                return ordered[:limit]

    # Priority 2 fallback: parse all data-asin and /dp/ links in page.
    for asin in DATA_ASIN_RE.findall(html):
        add(asin)
        if len(ordered) >= limit:
            return ordered[:limit]
    for asin in DP_RE.findall(html):
        add(asin)
        if len(ordered) >= limit:
            return ordered[:limit]

    return ordered[:limit]


def crawl_related_asins(
    asin: str,
    marketplace: str = "com",
    timeout: float = 20.0,
    pause_s: float = 0.0,
    max_related: int = 30,
) -> CrawlResult:
    asin = normalize_asin(asin)
    url = build_product_url(asin, marketplace)

    if pause_s > 0:
        time.sleep(pause_s)

    html, final_url = fetch_html(url=url, timeout=timeout)
    related = parse_related_asins(html, source_asin=asin, limit=max_related)
    return CrawlResult(source_asin=asin, related_asins=related, url=final_url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Input one ASIN and extract related ASINs from its Amazon detail page."
    )
    parser.add_argument("asin", help="Source ASIN (10 chars, e.g. B08N5WRWNW)")
    parser.add_argument(
        "--marketplace",
        default="com",
        help="Amazon marketplace domain suffix, e.g. com/co.uk/de/jp (default: com)",
    )
    parser.add_argument("--max-related", type=int, default=30, help="Maximum ASINs to return")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout (seconds)")
    parser.add_argument("--sleep", type=float, default=0.0, help="Delay before request in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = crawl_related_asins(
            asin=args.asin,
            marketplace=args.marketplace,
            timeout=args.timeout,
            pause_s=args.sleep,
            max_related=max(1, args.max_related),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "source_asin": result.source_asin,
                    "detail_url": result.url,
                    "related_asins": result.related_asins,
                    "count": len(result.related_asins),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"source_asin={result.source_asin}")
        print(f"detail_url={result.url}")
        print("related_asins:")
        for asin in result.related_asins:
            print(asin)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
