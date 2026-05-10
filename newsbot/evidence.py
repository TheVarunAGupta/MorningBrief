from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from newsbot.models import SourceProfile, StoryCluster
from newsbot.profiles import SourceProfiles


@dataclass(frozen=True)
class EvidenceSource:
    title: str
    url: str
    source_name: str
    author: str
    published_at: str
    description: str
    profile: SourceProfile


@dataclass(frozen=True)
class EvidencePack:
    title: str
    summary: str
    score: float
    complexity_score: float
    sources: list[EvidenceSource]
    weak_points: list[str]

    def to_markdown(self, index: int | None = None) -> str:
        heading = f"## {index}. {self.title}" if index is not None else f"## {self.title}"
        lines = [
            heading,
            "",
            "### Start Here",
            self.summary,
            "",
            "### Source File",
            f"Story selection score: {self.score:.2f}",
            "",
        ]
        for source in self.sources:
            profile = source.profile
            warning = "" if profile.warning == "none" else f" Warning: {profile.warning}."
            lines.extend(
                [
                    f"- **Outlet:** [{source.source_name}]({source.url})",
                    f"  Headline: {source.title}",
                    f"  By: {source.author}",
                    f"  Published: {source.published_at}",
                    f"  Type: {profile.source_type}",
                    f"  Region: {profile.region}",
                    f"  Original link: {source.url}",
                    "  Source profile: "
                    f"{profile.name}; {profile.region}; {profile.source_type}; "
                    f"{profile.editorial_profile}.{warning}",
                    f"  Bias: {profile.political_bias_label} ({profile.bias_score_display()})",
                    f"  Caveat: {profile.reliability_notes or 'No curated caveat listed.'}",
                ]
            )
        lines.extend(
            [
                "",
                "### What The Sources Say",
            ]
        )
        for source in self.sources:
            lines.extend(
                [
                    f"- {source.source_name}: {source.description or 'No feed description supplied.'}",
                ]
            )
        lines.extend(
            [
                "",
                "### Fact And Claim Check",
            ]
        )
        lines.extend(f"- {point}" for point in self.weak_points)
        return "\n".join(lines)


def build_evidence_packs(
    clusters: list[StoryCluster],
    profiles: SourceProfiles,
    max_sources_per_story: int = 5,
) -> list[EvidencePack]:
    return [
        EvidencePack(
            title=cluster.title,
            summary=_summary_from_cluster(cluster),
            score=cluster.score,
            complexity_score=cluster.complexity_score,
            sources=_evidence_sources(cluster, profiles, max_sources_per_story),
            weak_points=_weak_points(cluster, profiles),
        )
        for cluster in clusters
    ]


def _evidence_sources(
    cluster: StoryCluster,
    profiles: SourceProfiles,
    max_sources_per_story: int,
) -> list[EvidenceSource]:
    sources = [
        EvidenceSource(
            title=article.title,
            url=article.url,
            source_name=article.source_name,
            author=article.author,
            published_at=_format_published_at(article.published_at),
            description=_clean_description(article.description),
            profile=profiles.lookup(article.url),
        )
        for article in cluster.articles
    ]
    ranked = sorted(
        sources,
        key=lambda source: (
            source.profile.known,
            bool(source.description),
            source.profile.warning == "none",
            source.published_at != "Not listed",
        ),
        reverse=True,
    )
    useful = [
        source
        for source in ranked
        if source.profile.known or source.description
    ]
    return useful[:max_sources_per_story]


def _summary_from_cluster(cluster: StoryCluster) -> str:
    descriptions = [
        _clean_description(article.description)
        for article in cluster.articles
        if article.description
    ]
    if descriptions:
        return descriptions[0][:280]
    return "Feed metadata did not provide a substantive summary."


def _weak_points(cluster: StoryCluster, profiles: SourceProfiles) -> list[str]:
    points: list[str] = []
    if len(cluster.domains) < 2:
        points.append("Only one independent source domain is currently represented.")
    if len(cluster.regions) < 2:
        points.append("Regional diversity is limited in the available source set.")
    unknowns = [
        article.source_name
        for article in cluster.articles
        if not profiles.lookup(article.url).known
    ]
    if unknowns:
        points.append("Curated source profile missing for: " + ", ".join(sorted(set(unknowns))))
    if not points:
        points.append("No primary-source document was fetched; verify official texts before relying on precise claims.")
    return points


def _clean_description(description: str) -> str:
    return " ".join(description.replace("\n", " ").split())


def _format_published_at(published_at: dt.datetime | None) -> str:
    if published_at is None:
        return "Not listed"
    return published_at.astimezone(dt.UTC).strftime("%d/%m/%Y %H:%M UTC")
