from __future__ import annotations

import datetime as dt
import hashlib
import math
import re

from newsbot.models import Article, StoryCluster

STOPWORDS = {
    "a",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "latest",
    "new",
    "of",
    "on",
    "over",
    "says",
    "the",
    "to",
    "via",
    "with",
}

CANONICAL_TERMS = {
    "answer": "response",
    "answered": "response",
    "answers": "response",
    "replied": "response",
    "replies": "response",
    "reply": "response",
    "responds": "response",
    "response": "response",
    "mediating": "mediator",
    "mediation": "mediator",
    "mediator": "mediator",
    "mediators": "mediator",
    "pakistani": "pakistan",
    "plans": "proposal",
    "plan": "proposal",
    "proposal": "proposal",
    "proposals": "proposal",
    "truce": "ceasefire",
    "truces": "ceasefire",
}

RESPONSE_STORY_TERMS = {"response", "proposal", "ceasefire", "peace", "war", "mediator"}

IMPACT_KEYWORDS = {
    "alliance",
    "border",
    "ceasefire",
    "conflict",
    "coup",
    "defence",
    "defense",
    "diplomacy",
    "election",
    "energy",
    "escalation",
    "export",
    "food",
    "hostage",
    "invasion",
    "military",
    "missile",
    "nato",
    "nuclear",
    "peace",
    "sanction",
    "sanctions",
    "security",
    "shipping",
    "supply",
    "tariff",
    "trade",
    "treaty",
    "troops",
    "un",
    "war",
}


def title_tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {
        CANONICAL_TERMS.get(word, word)
        for word in words
        if word not in STOPWORDS and len(word) > 1
    }


def fingerprint_article(article: Article) -> str:
    tokens = sorted(title_tokens(article.title))
    normalized = " ".join(tokens)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _similarity(first: Article, second: Article) -> float:
    left = title_tokens(first.title)
    right = title_tokens(second.title)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _related_signature(first: Article, second: Article) -> bool:
    left = title_tokens(first.title)
    right = title_tokens(second.title)
    if "iran" not in left or "iran" not in right:
        return False
    if "us" not in left or "us" not in right:
        return False
    if not (left & {"response", "proposal", "mediator"}):
        return False
    if not (right & {"response", "proposal", "mediator"}):
        return False
    return bool(left & RESPONSE_STORY_TERMS and right & RESPONSE_STORY_TERMS)


def cluster_articles(articles: list[Article], threshold: float = 0.28) -> list[StoryCluster]:
    clusters: list[StoryCluster] = []
    for article in articles:
        match: StoryCluster | None = None
        for cluster in clusters:
            if any(
                _similarity(article, existing) >= threshold
                or _related_signature(article, existing)
                for existing in cluster.articles
            ):
                match = cluster
                break
        if match is None:
            clusters.append(
                StoryCluster(
                    articles=[article],
                    fingerprint=fingerprint_article(article),
                    title=article.title,
                )
            )
        else:
            match.articles.append(article)
            match.title = _best_title(match.articles)
    return clusters


def rank_clusters(
    clusters: list[StoryCluster],
    weights: dict[str, float],
    recent_fingerprints: set[str],
    now: dt.datetime | None = None,
) -> list[StoryCluster]:
    now = now or dt.datetime.now(dt.UTC)
    for cluster in clusters:
        score, complexity, reasons = _score_cluster(cluster, weights, recent_fingerprints, now)
        cluster.score = score
        cluster.complexity_score = complexity
        cluster.reasons = reasons
    return sorted(clusters, key=lambda cluster: cluster.score, reverse=True)


def _score_cluster(
    cluster: StoryCluster,
    weights: dict[str, float],
    recent_fingerprints: set[str],
    now: dt.datetime,
) -> tuple[float, float, list[str]]:
    all_tokens = set().union(*(title_tokens(article.title) for article in cluster.articles))
    impact_hits = all_tokens & IMPACT_KEYWORDS
    source_count = len(cluster.articles)
    domain_count = len(cluster.domains)
    region_count = len(cluster.regions)
    newest = max(
        (article.published_at for article in cluster.articles if article.published_at),
        default=now,
    )
    age_hours = max((now - newest).total_seconds() / 3600, 0)
    recency_score = max(0.0, 1.0 - (age_hours / 36.0))

    score = 0.0
    score += math.log1p(source_count) * weights.get("article_count", 1.0)
    score += domain_count * weights.get("domain_diversity", 1.0)
    score += region_count * weights.get("region_diversity", 1.0)
    score += min(len(impact_hits), 6) * weights.get("impact_keywords", 1.0)
    score += recency_score * weights.get("recency", 1.0)
    if cluster.fingerprint in recent_fingerprints:
        score -= weights.get("history_penalty", 0.0)

    reasons = [
        f"{source_count} source item(s)",
        f"{domain_count} unique domain(s)",
        f"{region_count} region label(s)",
    ]
    if impact_hits:
        reasons.append("impact terms: " + ", ".join(sorted(impact_hits)[:6]))
    if cluster.fingerprint in recent_fingerprints:
        reasons.append("recently covered fingerprint")

    complexity = min(10.0, 2.0 + domain_count + region_count + (len(impact_hits) * 0.75))
    return max(score, 0.0), complexity, reasons


def _best_title(articles: list[Article]) -> str:
    return max(articles, key=lambda article: len(title_tokens(article.title))).title
