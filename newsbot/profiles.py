from __future__ import annotations

from dataclasses import dataclass

from newsbot.models import SourceProfile
from newsbot.urls import domain_from_url


@dataclass(frozen=True)
class SourceProfiles:
    profiles: dict[str, SourceProfile]

    @classmethod
    def from_records(cls, records: list[dict[str, object]]) -> "SourceProfiles":
        profiles: dict[str, SourceProfile] = {}
        for record in records:
            domain = str(record["domain"]).lower()
            profiles[domain] = SourceProfile(
                domain=domain,
                name=str(record.get("name", domain)),
                region=str(record.get("region", "unknown")),
                source_type=str(record.get("source_type", "unknown")),
                editorial_profile=str(record.get("editorial_profile", "unknown")),
                political_bias_label=str(record.get("political_bias_label", "Unknown")),
                political_bias_score=int(record.get("political_bias_score", 0)),
                reliability_notes=str(record.get("reliability_notes", "")),
                warning=str(record.get("warning", "none")),
                useful_for=list(record.get("useful_for", [])),
                known=True,
            )
        return cls(profiles)

    def lookup(self, url: str) -> SourceProfile:
        domain = domain_from_url(url)
        if domain in self.profiles:
            return self.profiles[domain]
        for known_domain, profile in self.profiles.items():
            if domain.endswith(f".{known_domain}"):
                return profile
        return SourceProfile.unknown(domain)
