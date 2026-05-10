import datetime as dt
import unittest

from newsbot.ai import (
    BriefAnalysis,
    DeterministicBriefGenerator,
    SYSTEM_PROMPT,
    build_prompt,
    choose_model,
    estimate_call_cost_gbp,
    estimate_text_tokens,
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
        self.assertLess(
            analysis.markdown.index("### Source pack"),
            analysis.markdown.index("### Detective analysis"),
        )

    def test_render_email_includes_links_and_analysis(self):
        analysis = BriefAnalysis(
            markdown=(
                "# Daily Geopolitics Brief - 2026-05-08\n\n"
                "## 1. UN debates sanctions package\n"
                "### Source pack\n"
                "- **Example News** ([link](https://example.com/a)): Source profile: Center-left; bias score -1.\n"
                "### Detective analysis\n"
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
        self.assertIn("Source Pack", rendered.html)
        self.assertIn("<strong>Example News</strong>", rendered.html)
        self.assertIn("https://example.com/a", rendered.html)
        self.assertIn("background:#f6f8fb", rendered.html)
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
        self.assertIn("08/05/2026", prompt)


if __name__ == "__main__":
    unittest.main()
