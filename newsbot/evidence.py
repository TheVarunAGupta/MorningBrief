from __future__ import annotations

from dataclasses import dataclass

from newsbot.models import SourceProfile, StoryCluster
from newsbot.profiles import SourceProfiles


@dataclass(frozen=True)
class EvidenceSource:
    title: str
    url: str
    source_name: str
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

    def to_markdown(self) -> str:
        lines = [
            f"## {self.title}",
            "",
            "### Source pack",
            f"Selection score: {self.score:.2f}",
            f"Working summary: {self.summary}",
            "",
        ]
        for source in self.sources:
            profile = source.profile
            warning = "" if profile.warning == "none" else f" Warning: {profile.warning}."
            lines.extend(
                [
                    f"- {source.source_name}: {source.title}",
                    f"  Original link: {source.url}",
                    "  Profile: "
                    f"{profile.name}; {profile.region}; {profile.source_type}; "
                    f"{profile.editorial_profile}.{warning}",
                    f"  Bias: {profile.political_bias_label} ({profile.bias_score_display()})",
                    f"  Evidence note: {source.description or 'No feed description supplied.'}",
                ]
            )
        lines.extend(["", "### Weak points / caveats"])
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
            sources=[
                EvidenceSource(
                    title=article.title,
                    url=article.url,
                    source_name=article.source_name,
                    published_at=article.published_at.isoformat()
                    if article.published_at
                    else "unknown",
                    description=_clean_description(article.description),
                    profile=profiles.lookup(article.url),
                )
                for article in cluster.articles[:max_sources_per_story]
            ],
            weak_points=_weak_points(cluster, profiles),
        )
        for cluster in clusters
    ]


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
