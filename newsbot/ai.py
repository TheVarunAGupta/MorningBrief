from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from newsbot.evidence import EvidencePack

MODEL_RATES_USD_PER_MILLION = {
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
}

DEFAULT_OUTPUT_TOKENS = 1800


@dataclass(frozen=True)
class BriefAnalysis:
    markdown: str
    model: str
    estimated_cost_gbp: float


def estimate_text_tokens(text: str) -> int:
    if not text.strip():
        return 0
    return max(1, len(text.split()) // 4)


def estimate_call_cost_gbp(
    model: str,
    input_tokens: int,
    output_tokens: int = DEFAULT_OUTPUT_TOKENS,
    usd_to_gbp: float = 0.8,
) -> float:
    rates = MODEL_RATES_USD_PER_MILLION.get(
        model, MODEL_RATES_USD_PER_MILLION["gpt-5.4-mini"]
    )
    usd = (
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"]
    )
    return usd * usd_to_gbp


def choose_model(
    complexity_score: float,
    estimated_input_tokens: int,
    monthly_spend_gbp: float,
    monthly_cap_gbp: float,
    daily_model: str,
    deep_model: str,
) -> str:
    deep_cost = estimate_call_cost_gbp(deep_model, estimated_input_tokens)
    if complexity_score >= 7.0 and monthly_spend_gbp + deep_cost <= monthly_cap_gbp:
        return deep_model
    return daily_model


class DeterministicBriefGenerator:
    def generate(self, packs: list[EvidencePack], run_date: str) -> BriefAnalysis:
        lines = [
            f"# Daily Geopolitics Brief - {run_date}",
            "",
            "This dry-run brief is generated without the OpenAI API. It preserves the source-first structure for local review.",
            "",
        ]
        for index, pack in enumerate(packs, start=1):
            lines.extend(
                [
                    f"## {index}. {pack.title}",
                    "",
                    "### Source pack",
                    f"Selection score: {pack.score:.2f}",
                    f"Working summary: {pack.summary}",
                    "",
                ]
            )
            for source in pack.sources:
                profile = source.profile
                warning = "" if profile.warning == "none" else f" Warning: {profile.warning}."
                lines.extend(
                    [
                        f"- [{source.source_name}]({source.url}): {source.title}",
                        "  Source profile: "
                        f"{profile.name}; {profile.region}; {profile.source_type}; "
                        f"{profile.editorial_profile}.{warning}",
                        f"  Evidence note: {source.description or 'No feed description supplied.'}",
                    ]
                )
            lines.extend(
                [
                    "",
                    "### Claim/stat check",
                    *[f"- {point}" for point in pack.weak_points],
                    "",
                    "### Detective analysis",
                    "- Why now: available source metadata points to a live diplomatic or security pressure point, but the exact causal chain needs primary-source verification.",
                    "- Who benefits: identify states, blocs, firms, or armed groups that gain leverage if the reported move succeeds.",
                    "- Second-order effects: watch sanctions exposure, alliance signalling, energy or trade chokepoints, migration pressure, and domestic political incentives.",
                    "",
                    "### Alternative explanations",
                    "- The story may reflect negotiation signalling rather than a settled policy shift.",
                    "- Media prominence may be driven by source access or regional attention rather than underlying importance.",
                    "",
                    "### Weak points",
                    *[f"- {point}" for point in pack.weak_points],
                    "",
                    "### What to watch next",
                    "- Look for official texts, votes, sanctions lists, troop movements, budget lines, commodity reactions, or named denials.",
                    "",
                ]
            )
        return BriefAnalysis(markdown="\n".join(lines), model="offline", estimated_cost_gbp=0.0)


class OpenAIBriefGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        daily_model: str = "gpt-5.4-mini",
        deep_model: str = "gpt-5.4",
        monthly_cap_gbp: float = 5.0,
        monthly_spend_gbp: float = 0.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.daily_model = daily_model
        self.deep_model = deep_model
        self.monthly_cap_gbp = monthly_cap_gbp
        self.monthly_spend_gbp = monthly_spend_gbp

    def generate(self, packs: list[EvidencePack], run_date: str) -> BriefAnalysis:
        prompt = build_prompt(packs, run_date)
        input_tokens = estimate_text_tokens(prompt)
        complexity = max((pack.complexity_score for pack in packs), default=0.0)
        model = choose_model(
            complexity_score=complexity,
            estimated_input_tokens=input_tokens,
            monthly_spend_gbp=self.monthly_spend_gbp,
            monthly_cap_gbp=self.monthly_cap_gbp,
            daily_model=self.daily_model,
            deep_model=self.deep_model,
        )
        estimated_cost = estimate_call_cost_gbp(model, input_tokens)
        if self.monthly_spend_gbp + estimated_cost > self.monthly_cap_gbp:
            model = self.daily_model
            estimated_cost = estimate_call_cost_gbp(model, input_tokens)
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required unless --dry-run is used.")

        payload = {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": prompt,
            "max_output_tokens": DEFAULT_OUTPUT_TOKENS,
            "store": False,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API request failed: {exc.code} {details}") from exc
        return BriefAnalysis(
            markdown=_extract_response_text(data),
            model=model,
            estimated_cost_gbp=estimated_cost,
        )


SYSTEM_PROMPT = """You produce a personal daily geopolitics intelligence brief.
Rules:
- Source pack first, analysis second. Never lead with interpretation.
- Use only the supplied source pack. Do not invent sources or facts.
- Keep original links visible.
- Label state-affiliated, official, advocacy, and unknown profiles clearly.
- Treat uncertain claims honestly: unverified, context missing, definition-dependent, or primary source not found.
- Detective analysis should explain chains of incentives: because X funds/enables/pressures Y, Z may gain or lose leverage, indirectly affecting A/B.
- Include alternative explanations and what would change the assessment.
- Write for a 10-minute read.
"""


def build_prompt(packs: list[EvidencePack], run_date: str) -> str:
    source_pack_text = "\n\n".join(pack.to_markdown() for pack in packs)
    return f"""Run date: {run_date}

Write the daily geopolitics brief from these evidence packs.

Required structure:
# Daily Geopolitics Brief - {run_date}

For each story:
## N. Story title
### Source pack
Short bullets with links and source profile labels.
### Claim/stat check
Stats, definitions, missing primary sources, or context caveats.
### Detective analysis
Explain the causal chain, incentives, money/security/legal/trade routes, who benefits, who loses leverage, and second-order effects.
### Alternative explanations
### Weak points
### What to watch next

Evidence packs:
{source_pack_text}
"""


def _extract_response_text(data: dict[str, object]) -> str:
    texts: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                texts.append(str(content.get("text", "")))
    if texts:
        return "\n".join(texts)
    raise RuntimeError("OpenAI API response did not contain output_text content.")
