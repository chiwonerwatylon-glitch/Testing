import logging
import os
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 10
MAX_CHARS = 30000
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)
SKIP_TAGS = {'script', 'style', 'nav', 'footer', 'noscript'}

_lock = threading.Lock()
_cache = {'text': '', 'fetched_at': 0.0}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = ' '.join(data.split())
            if text:
                self._chunks.append(text)

    def get_text(self):
        return '\n'.join(self._chunks)


def _html_to_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


def _build_urls(base_url):
    urls = [base_url]
    host = urlparse(base_url).netloc
    for path in (os.environ.get('FML_WEBSITE_PATHS') or '').split(','):
        path = path.strip()
        if not path:
            continue
        url = urljoin(base_url, path)
        # Same host only
        if urlparse(url).netloc == host and url not in urls:
            urls.append(url)
    return urls


def _cache_ttl_seconds():
    try:
        hours = float(os.environ.get('FML_WEBSITE_CACHE_HOURS') or 6)
    except ValueError:
        hours = 6
    return max(hours, 0) * 3600


def _fetch_all(base_url):
    texts = []
    for url in _build_urls(base_url):
        response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        page_text = _html_to_text(response.text)
        if page_text:
            texts.append(page_text)
    return '\n\n'.join(texts)[:MAX_CHARS]


def get_fml_website_text():
    """Return cached plain text from the configured FML website, or "" if unavailable."""
    base_url = (os.environ.get('FML_WEBSITE_URL') or '').strip()
    if not base_url:
        return ''

    with _lock:
        now = time.monotonic()
        if _cache['fetched_at'] and now - _cache['fetched_at'] < _cache_ttl_seconds():
            return _cache['text']
        try:
            text = _fetch_all(base_url)
        except (requests.RequestException, ValueError) as exc:
            logger.warning('Could not fetch FML website content: %s', type(exc).__name__)
            return _cache['text']
        _cache['text'] = text
        _cache['fetched_at'] = now
        return text
