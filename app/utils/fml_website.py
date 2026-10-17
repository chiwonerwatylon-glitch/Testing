from __future__ import annotations

import logging
import os
import threading
import time
from html.parser import HTMLParser
from typing import List
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 10
MAX_CHARS = 30_000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SKIP_TAGS = {"script", "style", "nav", "footer", "noscript"}

_lock = threading.Lock()
_cache = {"text": "", "fetched_at": 0.0}


class _TextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor, skipping navigation and non-content tags."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # attrs unused
        if tag in SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = " ".join(data.split())
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        return "\n".join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


def _build_urls(base_url: str) -> list[str]:
    """Build list of URLs to fetch, restricted to the same host."""
    urls: list[str] = [base_url]
    host = urlparse(base_url).netloc

    raw_paths = os.environ.get("FML_WEBSITE_PATHS") or ""
    for path in raw_paths.split(","):
        path = path.strip()
        if not path:
            continue
        url = urljoin(base_url, path)
        # Same host only
        if urlparse(url).netloc == host and url not in urls:
            urls.append(url)

    return urls


def _cache_ttl_seconds() -> float:
    """Cache TTL in seconds, based on FML_WEBSITE_CACHE_HOURS (default 6)."""
    try:
        hours = float(os.environ.get("FML_WEBSITE_CACHE_HOURS") or 6)
    except ValueError:
        hours = 6.0
    return max(hours, 0.0) * 3600.0


def _fetch_all(base_url: str) -> str:
    """Fetch and concatenate text content from all configured URLs."""
    texts: list[str] = []
    for url in _build_urls(base_url):
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT,
        )
        response.raise_for_status()
        page_text = _html_to_text(response.text)
        if page_text:
            texts.append(page_text)
    return "\n\n".join(texts)[:MAX_CHARS]


def get_fml_website_text() -> str:
    """Return cached plain text from the configured FML website, or "" if unavailable."""
    base_url = (os.environ.get("FML_WEBSITE_URL") or "").strip()
    if not base_url:
        return ""

    with _lock:
        now = time.monotonic()
        ttl = _cache_ttl_seconds()
        if _cache["fetched_at"] and now - _cache["fetched_at"] < ttl:
            return _cache["text"]

        try:
            text = _fetch_all(base_url)
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "Could not fetch FML website content: %s",
                type(exc).__name__,
            )
            # Return whatever we had cached previously (may be empty).
            return _cache["text"]

        _cache["text"] = text
        _cache["fetched_at"] = now
        return text
