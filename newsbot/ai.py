from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from newsbot.evidence import EvidencePack

MODEL_RATES_USD_PER_MILLION = {
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
}

DEFAULT_OUTPUT_TOKENS = 4500
DEFAULT_OPENAI_TIMEOUT_SECONDS = 240
DEFAULT_OPENAI_MAX_RETRIES = 2
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
ANALYSIS_SECTIONS = (
    "AI Roundup",
    "Alternative Explanations",
    "Weak Points",
    "Watch Next",
)
SOURCE_SECTIONS = (
    "Start Here",
    "Source File",
    "What The Sources Say",
    "Fact And Claim Check",
)


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


def _int_env(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


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
        lines: list[str] = []
        for index, pack in enumerate(packs, start=1):
            lines.extend(
                [
                    f"## {index}. {pack.title}",
                    "",
                    "### AI Roundup",
                    "- Why now: available source metadata points to a live diplomatic or security pressure point, but the exact causal chain needs primary-source verification.",
                    "- Who benefits: identify states, blocs, firms, or armed groups that gain leverage if the reported move succeeds.",
                    "- Second-order effects: watch sanctions exposure, alliance signalling, energy or trade chokepoints, migration pressure, and domestic political incentives.",
                    "",
                    "### Alternative Explanations",
                    "- The story may reflect negotiation signalling rather than a settled policy shift.",
                    "- Media prominence may be driven by source access or regional attention rather than underlying importance.",
                    "",
                    "### Weak Points",
                    *[f"- {point}" for point in pack.weak_points],
                    "",
                    "### Watch Next",
                    "- Look for official texts, votes, sanctions lists, troop movements, budget lines, commodity reactions, or named denials.",
                    "",
                ]
            )
        return BriefAnalysis(
            markdown=compose_brief_markdown(packs, "\n".join(lines), run_date),
            model="offline",
            estimated_cost_gbp=0.0,
        )


class OpenAIBriefGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        daily_model: str = "gpt-5.4-mini",
        deep_model: str = "gpt-5.4",
        monthly_cap_gbp: float = 5.0,
        monthly_spend_gbp: float = 0.0,
        request_timeout_seconds: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.daily_model = daily_model
        self.deep_model = deep_model
        self.monthly_cap_gbp = monthly_cap_gbp
        self.monthly_spend_gbp = monthly_spend_gbp
        self.request_timeout_seconds = request_timeout_seconds or _int_env(
            "OPENAI_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_OPENAI_TIMEOUT_SECONDS,
            minimum=1,
        )
        self.max_retries = (
            max(0, max_retries)
            if max_retries is not None
            else _int_env("OPENAI_MAX_RETRIES", DEFAULT_OPENAI_MAX_RETRIES, minimum=0)
        )

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
        data = self._send_request(request)
        analysis_markdown = _extract_response_text(data)
        validate_analysis_markdown(analysis_markdown, story_count=len(packs))
        return BriefAnalysis(
            markdown=compose_brief_markdown(packs, analysis_markdown, run_date),
            model=model,
            estimated_cost_gbp=estimated_cost,
        )

    def _send_request(self, request: urllib.request.Request) -> dict[str, object]:
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.request_timeout_seconds,
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code not in TRANSIENT_HTTP_STATUS_CODES or attempt == attempts:
                    raise RuntimeError(
                        f"OpenAI API request failed: {exc.code} {details}"
                    ) from exc
            except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
                if attempt == attempts:
                    raise RuntimeError(
                        "OpenAI API request failed after "
                        f"{attempts} attempt(s) with {self.request_timeout_seconds}s "
                        f"timeout: {exc}"
                    ) from exc
        raise RuntimeError("OpenAI API request failed without returning a response.")


SYSTEM_PROMPT = """You are a professional news email journalist writing a personal daily geopolitics brief for a normal reader.
Rules:
- Write in a calm, clear, reader-friendly style. Above all, do not push an agenda.
- Be politically neutral: explain incentives and tradeoffs without telling the reader what to think.
- Avoid dramatic language, partisan framing, moral grandstanding, and insider jargon.
- Source pack first, analysis second. Never lead with interpretation.
- Use only the supplied source pack. Do not invent sources or facts.
- Keep original links visible and clearly label each source profile and preset bias/context score.
- Label state-affiliated, official, advocacy, and unknown profiles clearly without treating them as neutral referees.
- Treat uncertain claims honestly: unverified, context missing, definition-dependent, or primary source not found.
- Detective analysis should explain chains of incentives: because X funds/enables/pressures Y, Z may gain or lose leverage, indirectly affecting A/B.
- Include alternative explanations and what would change the assessment.
- Write for a 10-minute read.
- The source sections are generated deterministically by code. Write only the analysis sections requested by the user prompt.
"""


def build_prompt(packs: list[EvidencePack], run_date: str) -> str:
    source_pack_text = "\n\n".join(
        pack.to_markdown(index=index)
        for index, pack in enumerate(packs, start=1)
    )
    display_date = _display_date(run_date)
    return f"""Run date: {display_date}

Write the analysis layer for the daily geopolitics brief from these evidence packs.

Return only the analysis sections for each story. Do not write or rewrite Start Here, Source File, What The Sources Say, or Fact And Claim Check. Those sections are inserted by code from the evidence pack.

For each story:
## N. Story title
### AI Roundup
Explain the causal chain, incentives, money/security/legal/trade routes, who benefits, who loses leverage, and second-order effects. Keep this reader-friendly and neutral.
### Alternative Explanations
Plausible explanations that would change the interpretation.
### Weak Points
What the evidence pack cannot prove, where definitions may be slippery, and which claims rely on weak or partial sourcing.
### Watch Next
Concrete signals to monitor: official texts, votes, sanctions lists, troop movements, budget lines, market reactions, named denials, or mediator statements.

Evidence packs:
{source_pack_text}
"""


def compose_brief_markdown(
    packs: list[EvidencePack],
    analysis_markdown: str,
    run_date: str,
) -> str:
    validate_analysis_markdown(analysis_markdown, story_count=len(packs))
    display_date = _display_date(run_date)
    lines = [f"# Daily Geopolitics Brief - {display_date}", ""]
    for index, pack in enumerate(packs, start=1):
        lines.extend(
            [
                pack.to_markdown(index=index),
                "",
                _extract_story_analysis(analysis_markdown, index).strip(),
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def validate_analysis_markdown(markdown: str, story_count: int) -> None:
    if story_count == 0:
        return
    for index in range(1, story_count + 1):
        block = _extract_story_analysis(markdown, index)
        missing = [
            section
            for section in ANALYSIS_SECTIONS
            if f"### {section}" not in block
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"OpenAI analysis for story {index} missing required analysis sections: {joined}"
            )
        empty = [
            section
            for section in ANALYSIS_SECTIONS
            if not _section_body(block, section).strip()
        ]
        if empty:
            joined = ", ".join(empty)
            raise RuntimeError(
                f"OpenAI analysis for story {index} has empty analysis section(s): {joined}"
            )
        source_leaks = [
            section
            for section in SOURCE_SECTIONS
            if f"### {section}" in block
        ]
        if source_leaks:
            joined = ", ".join(source_leaks)
            raise RuntimeError(
                f"OpenAI analysis for story {index} included deterministic source sections: {joined}"
            )


def _display_date(run_date: str) -> str:
    try:
        year, month, day = run_date.split("-")
    except ValueError:
        return run_date
    return f"{day}/{month}/{year}"


def _extract_story_analysis(markdown: str, story_index: int) -> str:
    matches = list(re.finditer(r"(?m)^##\s+(\d+)\.\s+.*$", markdown))
    if not matches:
        if story_index == 1:
            return markdown
        raise RuntimeError(f"OpenAI analysis is missing story heading {story_index}.")
    for offset, match in enumerate(matches):
        if int(match.group(1)) != story_index:
            continue
        start = match.end()
        end = matches[offset + 1].start() if offset + 1 < len(matches) else len(markdown)
        return markdown[start:end].strip()
    raise RuntimeError(f"OpenAI analysis is missing story heading {story_index}.")


def _section_body(block: str, section: str) -> str:
    pattern = re.compile(rf"(?m)^###\s+{re.escape(section)}\s*$")
    match = pattern.search(block)
    if not match:
        return ""
    next_heading = re.search(r"(?m)^###\s+", block[match.end() :])
    if next_heading:
        return block[match.end() : match.end() + next_heading.start()]
    return block[match.end() :]


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
