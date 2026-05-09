from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    source_name: str
    description: str = ""
    published_at: dt.datetime | None = None
    region: str = "Global"
    raw: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceProfile:
    domain: str
    name: str
    region: str
    source_type: str
    editorial_profile: str
    reliability_notes: str
    warning: str
    useful_for: list[str]
    known: bool = True

    @classmethod
    def unknown(cls, domain: str) -> "SourceProfile":
        return cls(
            domain=domain,
            name="Unknown source",
            region="unknown",
            source_type="unknown",
            editorial_profile="unknown",
            reliability_notes="No curated source profile yet.",
            warning="unknown profile",
            useful_for=[],
            known=False,
        )


@dataclass
class StoryCluster:
    articles: list[Article]
    fingerprint: str
    title: str
    score: float = 0.0
    complexity_score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def domains(self) -> set[str]:
        from newsbot.urls import domain_from_url

        return {domain_from_url(article.url) for article in self.articles if article.url}

    @property
    def regions(self) -> set[str]:
        return {article.region for article in self.articles if article.region}
