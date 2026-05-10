from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable

from newsbot.models import Article
from newsbot.urls import domain_from_url

Fetcher = Callable[[str], bytes]


def collect_articles(sources_config: dict[str, object], fetcher: Fetcher | None = None) -> list[Article]:
    fetcher = fetcher or fetch_url
    articles: list[Article] = []
    for feed in sources_config.get("rss_feeds", []):
        if not isinstance(feed, dict) or not feed.get("url"):
            continue
        try:
            articles.extend(parse_rss_feed(fetcher(str(feed["url"])), feed))
        except Exception:
            continue
    for query in sources_config.get("gdelt_queries", []):
        if not isinstance(query, dict):
            continue
        try:
            payload = json.loads(fetcher(build_gdelt_url(query)).decode("utf-8"))
            articles.extend(
                parse_gdelt_articles(
                    payload,
                    source_name=str(query.get("name", "GDELT")),
                    region=str(query.get("region", "Global")),
                )
            )
        except Exception:
            continue
    return dedupe_articles(articles)


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NewsBot/0.1 personal geopolitics brief"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def parse_rss_feed(payload: bytes, feed: dict[str, object]) -> list[Article]:
    root = ET.fromstring(payload)
    articles: list[Article] = []
    for item in root.findall(".//item"):
        title = _node_text(item, "title")
        link = _node_text(item, "link")
        if not title or not link:
            continue
        articles.append(
            Article(
                title=_clean_text(title),
                url=link.strip(),
                source_name=str(feed.get("name", domain_from_url(link))),
                description=_clean_text(_node_text(item, "description")),
                published_at=parse_rss_datetime(_node_text(item, "pubDate")),
                region=str(feed.get("region", "Global")),
                author=_rss_author(item),
                raw={"feed": feed.get("name", "")},
            )
        )
    return articles


def build_gdelt_url(query: dict[str, object]) -> str:
    params = {
        "query": str(query.get("query", "")),
        "mode": "artlist",
        "format": "json",
        "timespan": str(query.get("timespan", "24h")),
        "maxrecords": str(query.get("max_records", 75)),
        "sort": str(query.get("sort", "hybridrel")),
    }
    return "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)


def parse_gdelt_articles(
    payload: dict[str, object],
    source_name: str,
    region: str,
) -> list[Article]:
    articles: list[Article] = []
    for item in payload.get("articles", []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url:
            continue
        domain = str(item.get("domain") or domain_from_url(url))
        articles.append(
            Article(
                title=_clean_text(title),
                url=url,
                source_name=domain or source_name,
                description=_clean_text(str(item.get("snippet", ""))),
                published_at=parse_gdelt_datetime(str(item.get("seendate", ""))),
                region=str(item.get("sourceCountry") or region),
                author="Not listed",
                raw={"collector": source_name},
            )
        )
    return articles


def dedupe_articles(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    result: list[Article] = []
    for article in articles:
        key = article.url.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result


def parse_rss_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None
    parsed = email.utils.parsedate_to_datetime(value)
    if parsed and parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed


def parse_gdelt_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC)
    except ValueError:
        return None


def _node_text(item: ET.Element, name: str) -> str:
    node = item.find(name)
    return node.text if node is not None and node.text else ""


def _rss_author(item: ET.Element) -> str:
    for candidate in ("author", "creator"):
        value = _node_text(item, candidate)
        if value:
            return _clean_text(value)
    for child in item:
        if child.tag.lower().endswith("creator") and child.text:
            return _clean_text(child.text)
    return "Not listed"


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())
