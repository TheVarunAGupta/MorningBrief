import datetime as dt
import json
import unittest
from unittest import mock

from newsbot.ai import (
    ANALYSIS_SECTIONS,
    BriefAnalysis,
    DeterministicBriefGenerator,
    DEFAULT_OUTPUT_TOKENS,
    OpenAIBriefGenerator,
    SYSTEM_PROMPT,
    build_prompt,
    compose_brief_markdown,
    choose_model,
    estimate_call_cost_gbp,
    estimate_text_tokens,
    validate_analysis_markdown,
)
from newsbot.emailer import render_email
from newsbot.evidence import EvidencePack, EvidenceSource
from newsbot.models import SourceProfile


class AiAndEmailTests(unittest.TestCase):
    def test_estimate_text_tokens_is_stable_and_nonzero(self):
        self.assertEqual(estimate_text_tokens("one two three four"), 1)
        self.assertGreater(estimate_text_tokens("word " * 100), 20)

    def test_cost_estimate_uses_model_rates(self):
        cost = estimate_call_cost_gbp(
            model="gpt-5.4-mini",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            usd_to_gbp=0.8,
        )

        self.assertAlmostEqual(cost, 4.2, places=2)

    def test_choose_model_uses_deep_only_when_complex_and_under_budget(self):
        cheap = choose_model(
            complexity_score=3.0,
            estimated_input_tokens=3000,
            monthly_spend_gbp=0.0,
            monthly_cap_gbp=5.0,
            daily_model="gpt-5.4-mini",
            deep_model="gpt-5.4",
        )
        deep = choose_model(
            complexity_score=8.0,
            estimated_input_tokens=3000,
            monthly_spend_gbp=0.0,
            monthly_cap_gbp=5.0,
            daily_model="gpt-5.4-mini",
            deep_model="gpt-5.4",
        )
        capped = choose_model(
            complexity_score=8.0,
            estimated_input_tokens=900_000,
            monthly_spend_gbp=4.95,
            monthly_cap_gbp=5.0,
            daily_model="gpt-5.4-mini",
            deep_model="gpt-5.4",
        )

        self.assertEqual(cheap, "gpt-5.4-mini")
        self.assertEqual(deep, "gpt-5.4")
        self.assertEqual(capped, "gpt-5.4-mini")

    def test_deterministic_generator_preserves_source_first_structure(self):
        pack = EvidencePack(
            title="UN debates sanctions package",
            summary="Several diplomatic sources describe a sanctions debate.",
            score=9.0,
            complexity_score=7.0,
            sources=[
                EvidenceSource(
                    title="UN debates sanctions package",
                    url="https://example.com/a",
                    source_name="Example News",
                    author="Diplomatic Desk",
                    published_at="2026-05-08T06:00:00+00:00",
                    description="Diplomats cite energy and border security.",
                    profile=SourceProfile(
                        domain="example.com",
                        name="Example News",
                        region="Europe",
                        source_type="news",
                        editorial_profile="center-left",
                        reliability_notes="Check numbers.",
                        warning="none",
                        useful_for=["European framing"],
                        known=True,
                    ),
                )
            ],
            weak_points=["Primary source not found for quoted figures."],
        )

        analysis = DeterministicBriefGenerator().generate([pack], "2026-05-08")

        self.assertIn("## 1. UN debates sanctions package", analysis.markdown)
        self.assertIn("### Start Here", analysis.markdown)
        self.assertIn("### Source File", analysis.markdown)
        self.assertIn("### What The Sources Say", analysis.markdown)
        self.assertIn("### AI Roundup", analysis.markdown)
        self.assertLess(
            analysis.markdown.index("### Start Here"),
            analysis.markdown.index("### AI Roundup"),
        )
        self.assertEqual(DEFAULT_OUTPUT_TOKENS, 4500)

    def test_render_email_includes_links_and_analysis(self):
        analysis = BriefAnalysis(
            markdown=(
                "# Daily Geopolitics Brief - 2026-05-08\n\n"
                "## 1. UN debates sanctions package\n"
                "### Start Here\n"
                "Diplomats are debating a sanctions package after a border escalation.\n"
                "### Source File\n"
                "- **Example News** ([link](https://example.com/a)): Source profile: Center-left; bias score -1.\n"
                "### AI Roundup\n"
                "Follow the money and diplomatic leverage."
            ),
            model="offline",
            estimated_cost_gbp=0.0,
        )

        rendered = render_email(
            analysis,
            run_date=dt.date(2026, 5, 8),
            subject_prefix="Daily Geopolitics Brief",
        )

        self.assertIn("Daily Geopolitics Brief - 08/05/2026", rendered.subject)
        self.assertIn("Daily Geopolitics Brief", rendered.html)
        self.assertIn("08/05/2026", rendered.html)
        self.assertIn("Start Here", rendered.html)
        self.assertIn("Source File", rendered.html)
        self.assertIn("AI Roundup", rendered.html)
        self.assertIn("<strong>Example News</strong>", rendered.html)
        self.assertIn("https://example.com/a", rendered.html)
        self.assertIn("background:#f6f8fb", rendered.html)
        self.assertIn("max-width:840px", rendered.html)
        self.assertIn("Briefing desk", rendered.html)
        self.assertIn("border-left:4px solid #d99a20", rendered.html)
        self.assertIn("Follow the money", rendered.text)

    def test_render_email_converts_numbered_lists_and_bold_text(self):
        analysis = BriefAnalysis(
            markdown=(
                "# Daily Geopolitics Brief - 2026-05-08\n\n"
                "## 1. Trade route pressure\n"
                "### Alternative explanations\n"
                "1. **Negotiating signal** rather than settled policy.\n"
                "2. **Domestic politics** may be driving the timing."
            ),
            model="offline",
            estimated_cost_gbp=0.0,
        )

        rendered = render_email(analysis, run_date=dt.date(2026, 5, 8))

        self.assertIn("<ol", rendered.html)
        self.assertIn("<strong>Negotiating signal</strong>", rendered.html)
        self.assertIn("<strong>Domestic politics</strong>", rendered.html)

    def test_ai_prompt_asks_for_neutral_reader_friendly_journalism(self):
        prompt = build_prompt([], "2026-05-08")

        self.assertIn("professional news email journalist", SYSTEM_PROMPT)
        self.assertIn("normal reader", SYSTEM_PROMPT)
        self.assertIn("do not push an agenda", SYSTEM_PROMPT)
        self.assertIn("Return only the analysis sections", prompt)
        self.assertIn("Start Here", prompt)
        self.assertIn("Source File", prompt)
        self.assertIn("What The Sources Say", prompt)
        self.assertIn("AI Roundup", prompt)
        self.assertIn("08/05/2026", prompt)

    def test_compose_brief_keeps_source_sections_deterministic(self):
        pack = EvidencePack(
            title="Iran response to US proposal",
            summary="Iran replied to a US proposal through Pakistani mediation.",
            score=10.0,
            complexity_score=8.0,
            sources=[
                EvidenceSource(
                    title="Iran sends response to US proposal",
                    url="https://example.com/a",
                    source_name="Example News",
                    author="Not listed",
                    published_at="10/05/2026 06:00 UTC",
                    description="Iran sent a response through Pakistan.",
                    profile=SourceProfile(
                        domain="example.com",
                        name="Example News",
                        region="Global",
                        source_type="news",
                        editorial_profile="center",
                        political_bias_label="Center",
                        political_bias_score=0,
                        reliability_notes="Use as a baseline only.",
                        warning="none",
                        useful_for=[],
                    ),
                )
            ],
            weak_points=["Proposal text was not included."],
        )
        ai_sections = (
            "## 1. Iran response to US proposal\n"
            "### AI Roundup\n"
            "This is analysis only.\n"
            "### Alternative Explanations\n"
            "- It may be bargaining language.\n"
            "### Weak Points\n"
            "- Documents are missing.\n"
            "### Watch Next\n"
            "- Watch for official texts.\n"
        )

        brief = compose_brief_markdown([pack], ai_sections, "2026-05-10")

        self.assertLess(brief.index("### Source File"), brief.index("### AI Roundup"))
        self.assertIn("### Fact And Claim Check", brief)
        self.assertIn("Use as a baseline only.", brief)
        self.assertIn("This is analysis only.", brief)

    def test_validate_analysis_markdown_rejects_incomplete_story(self):
        incomplete = (
            "## 1. Story\n"
            "### AI Roundup\n"
            "Analysis.\n"
        )

        with self.assertRaisesRegex(RuntimeError, "missing required analysis sections"):
            validate_analysis_markdown(incomplete, story_count=1)

        truncated = (
            "## 1. Story\n"
            "### AI Roundup\n"
            "Analysis.\n"
            "### Alternative Explanations\n"
            "Another possibility.\n"
            "### Weak Points\n"
            "Documents are missing.\n"
            "### Watch Next\n"
        )
        with self.assertRaisesRegex(RuntimeError, "empty analysis section"):
            validate_analysis_markdown(truncated, story_count=1)

        complete = (
            "## 1. Story\n"
            + "\n".join(f"### {section}\nText." for section in ANALYSIS_SECTIONS)
        )
        validate_analysis_markdown(complete, story_count=1)

    def test_openai_generator_retries_transient_timeout(self):
        pack = EvidencePack(
            title="Border talks resume",
            summary="Officials say talks resumed after a border escalation.",
            score=7.0,
            complexity_score=5.0,
            sources=[
                EvidenceSource(
                    title="Border talks resume",
                    url="https://example.com/talks",
                    source_name="Example News",
                    author="Reporter",
                    published_at="13/05/2026 06:00 UTC",
                    description="Talks resumed after a border escalation.",
                    profile=SourceProfile(
                        domain="example.com",
                        name="Example News",
                        region="Global",
                        source_type="news",
                        editorial_profile="center",
                        political_bias_label="Center",
                        political_bias_score=0,
                        reliability_notes="Known source.",
                        warning="none",
                        useful_for=[],
                    ),
                )
            ],
            weak_points=["Official text not available."],
        )
        output_text = (
            "## 1. Border talks resume\n"
            "### AI Roundup\n"
            "Talks may shift leverage if security guarantees become concrete.\n"
            "### Alternative Explanations\n"
            "- This may be public signalling.\n"
            "### Weak Points\n"
            "- Official text is missing.\n"
            "### Watch Next\n"
            "- Watch for named mediator statements.\n"
        )
        payload = {
            "output": [
                {"content": [{"type": "output_text", "text": output_text}]}
            ]
        }
        observed_timeouts = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        def fake_urlopen(request, timeout):
            observed_timeouts.append(timeout)
            if len(observed_timeouts) == 1:
                raise TimeoutError("The read operation timed out")
            return FakeResponse()

        generator = OpenAIBriefGenerator(api_key="test-key")
        with mock.patch("newsbot.ai.urllib.request.urlopen", side_effect=fake_urlopen):
            analysis = generator.generate([pack], "2026-05-13")

        self.assertEqual(observed_timeouts, [240, 240])
        self.assertIn("Talks may shift leverage", analysis.markdown)


if __name__ == "__main__":
    unittest.main()
