import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.schemas.news import NewsArticleInput

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    hostname = (parts.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    port = f":{parts.port}" if parts.port else ""
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), hostname + port, path, query, ""))


def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def titles_are_similar(first: str, second: str) -> bool:
    if first == second:
        return True
    first_words = set(first.split())
    second_words = set(second.split())
    if min(len(first_words), len(second_words)) < 4:
        return False
    overlap = len(first_words & second_words) / len(first_words | second_words)
    return overlap >= 0.78 or SequenceMatcher(None, first, second).ratio() >= 0.88


def deduplicate_articles(articles: list[NewsArticleInput]) -> list[NewsArticleInput]:
    kept: list[NewsArticleInput] = []
    seen_urls: set[str] = set()
    seen_titles: list[str] = []

    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        url = canonicalize_url(article.url)
        title = normalize_title(article.title)
        if url in seen_urls or any(titles_are_similar(title, seen) for seen in seen_titles):
            continue
        seen_urls.add(url)
        seen_titles.append(title)
        kept.append(article.model_copy(update={"url": url}))
    return kept
