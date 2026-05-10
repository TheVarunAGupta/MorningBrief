from __future__ import annotations

import html
import os
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal

from newsbot.ai import BriefAnalysis


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


def render_email(
    analysis: BriefAnalysis,
    run_date,
    subject_prefix: str = "Daily Geopolitics Brief",
) -> RenderedEmail:
    display_date = format_display_date(run_date)
    subject = f"{subject_prefix} - {display_date}"
    html_body = render_newsletter_html(
        markdown=analysis.markdown,
        title=subject_prefix,
        display_date=display_date,
        model=analysis.model,
        estimated_cost_gbp=analysis.estimated_cost_gbp,
    )
    text_body = (
        f"{subject_prefix} - {display_date}\n\n"
        + _remove_markdown_title(analysis.markdown)
        + f"\n\nGenerated with model: {analysis.model}. "
        + f"Estimated API cost: GBP {analysis.estimated_cost_gbp:.4f}."
    )
    return RenderedEmail(subject=subject, text=text_body, html=html_body)


def format_display_date(run_date) -> str:
    return run_date.strftime("%d/%m/%Y")


def send_email(rendered: RenderedEmail) -> None:
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    email_to = os.environ.get("EMAIL_TO")
    missing = [
        name
        for name, value in {
            "GMAIL_USER": gmail_user,
            "GMAIL_APP_PASSWORD": gmail_password,
            "EMAIL_TO": email_to,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing email secret(s): " + ", ".join(missing))

    message = EmailMessage()
    message["Subject"] = rendered.subject
    message["From"] = gmail_user
    message["To"] = email_to
    message.set_content(rendered.text)
    message.add_alternative(rendered.html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(message)


def render_newsletter_html(
    markdown: str,
    title: str,
    display_date: str,
    model: str,
    estimated_cost_gbp: float,
) -> str:
    content_html = markdown_to_html(markdown)
    return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f6f8fb;color:#1f2933;font-family:Arial,Helvetica,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;color:transparent;">
      Source-first geopolitics brief for {html.escape(display_date)}.
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f8fb;margin:0;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:840px;background:#ffffff;border:1px solid #d9e1ea;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background:#102a43;color:#ffffff;padding:30px 32px;">
                <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#bcccdc;">Briefing desk</div>
                <h1 style="margin:8px 0 0;font-size:28px;line-height:1.2;font-weight:700;">{html.escape(title)}</h1>
                <div style="margin-top:8px;font-size:15px;color:#d9e2ec;">{html.escape(display_date)} · A little calmer than the headlines.</div>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px 10px;">
                <div style="border-left:4px solid #2f80ed;background:#eef5ff;padding:12px 14px;margin-bottom:20px;color:#23364d;font-size:14px;line-height:1.55;">
                  Evidence comes first. Analysis follows after links, source profiles, and caveats so you can audit the trail before the interpretation.
                </div>
                <div style="border-left:4px solid #d99a20;background:#fff8e6;padding:10px 12px;margin-bottom:20px;color:#6f4e00;font-size:13px;line-height:1.5;">
                  Source profile and bias labels are preset context cues. They are not truth scores, and official or state-funded sources are treated as perspective/signalling unless corroborated.
                </div>
                {content_html}
                <div style="margin-top:28px;border-top:1px solid #d9e1ea;padding-top:14px;color:#6b7280;font-size:12px;line-height:1.5;">
                  Generated with model: {html.escape(model)}. Estimated API cost: GBP {estimated_cost_gbp:.4f}. Source profile scores are preset editorial/context labels, not truth scores.
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def markdown_to_html(markdown: str) -> str:
    lines: list[str] = []
    list_mode: Literal["ul", "ol"] | None = None
    story_open = False

    def close_list() -> None:
        nonlocal list_mode
        if list_mode:
            lines.append(f"</{list_mode}>")
            list_mode = None

    def close_story() -> None:
        nonlocal story_open
        close_list()
        if story_open:
            lines.append("</div></div>")
            story_open = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            close_list()
            continue
        if line.startswith("# "):
            continue
        elif line.startswith("## "):
            close_story()
            story_open = True
            lines.append(
                '<div style="border:1px solid #d9e1ea;border-radius:8px;'
                'margin:0 0 24px;background:#ffffff;overflow:hidden;">'
            )
            lines.append(
                '<div style="background:#f8fafc;border-bottom:1px solid #d9e1ea;'
                'padding:18px 20px;">'
                f'<h2 style="margin:0;color:#102a43;font-size:21px;line-height:1.3;">'
                f"{_inline_html(line[3:])}</h2></div>"
            )
            lines.append('<div style="padding:16px 20px 20px;">')
        elif line.startswith("### "):
            close_list()
            section = _section_title(line[4:])
            lines.append(_section_heading(section))
        elif line.startswith("- "):
            if list_mode != "ul":
                close_list()
                lines.append('<ul style="margin:8px 0 14px 20px;padding:0;color:#243b53;font-size:14px;line-height:1.55;">')
                list_mode = "ul"
            lines.append(f'<li style="margin:0 0 8px;">{_decorate_source_profile(_inline_html(line[2:]))}</li>')
        elif line.startswith("  "):
            close_list()
            lines.append(
                '<p style="margin:0 0 6px 18px;color:#52606d;font-size:13px;line-height:1.45;">'
                f"{_decorate_source_profile(_inline_html(line.strip()))}</p>"
            )
        elif re.match(r"^\d+\.\s+", line):
            if list_mode != "ol":
                close_list()
                lines.append('<ol style="margin:8px 0 14px 20px;padding:0;color:#243b53;font-size:14px;line-height:1.55;">')
                list_mode = "ol"
            item = re.sub(r"^\d+\.\s+", "", line)
            lines.append(f'<li style="margin:0 0 8px;">{_inline_html(item)}</li>')
        else:
            close_list()
            lines.append(
                '<p style="margin:0 0 12px;color:#243b53;font-size:14px;line-height:1.6;">'
                f"{_decorate_source_profile(_inline_html(line))}</p>"
            )
    close_story()
    return "\n".join(lines)


def _section_title(title: str) -> str:
    normalized = title.strip()
    if normalized.lower() == "source pack":
        return "Source File"
    if normalized.lower() in {"claim/stat check", "claim / stat check"}:
        return "Fact And Claim Check"
    if normalized.lower() == "detective analysis":
        return "AI Roundup"
    if normalized.lower() in {"weak points / caveats", "weak points"}:
        return "Weak Points"
    if normalized.lower() in {"what to watch next", "watch next"}:
        return "Watch Next"
    return normalized[:1].upper() + normalized[1:]


def _section_heading(title: str) -> str:
    color = "#102a43"
    border = "#9fb3c8"
    background = "#f8fafc"
    if title in {"Fact And Claim Check", "Weak Points"}:
        border = "#d99a20"
        background = "#fff8e6"
        color = "#7c4d00"
    elif title == "Source File":
        border = "#2f80ed"
        background = "#eef5ff"
        color = "#173f73"
    elif title == "Start Here":
        border = "#2f9e44"
        background = "#edf9f0"
        color = "#1f6f34"
    elif title == "What The Sources Say":
        border = "#7c3aed"
        background = "#f4f0ff"
        color = "#4c1d95"
    elif title == "AI Roundup":
        border = "#475569"
        background = "#f1f5f9"
        color = "#1e293b"
    return (
        f'<div style="margin:18px 0 10px;border-left:4px solid {border};'
        f'background:{background};padding:8px 10px;">'
        f'<h3 style="margin:0;color:{color};font-size:15px;line-height:1.3;">'
        f"{html.escape(title)}</h3></div>"
    )


def _inline_html(text: str) -> str:
    escaped = html.escape(text)
    linked = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" style="color:#1d4ed8;text-decoration:underline;">\1</a>',
        escaped,
    )
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", linked)


def _remove_markdown_title(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return markdown


def _decorate_source_profile(text: str) -> str:
    text = re.sub(
        r"(Bias:\s*)([^.(<]+)(\s*\(([+-]?\d+)\))",
        r'\1<span style="display:inline-block;background:#eef5ff;color:#173f73;border:1px solid #bfd7ff;border-radius:999px;padding:1px 7px;font-size:12px;font-weight:700;">\2 \4</span>',
        text,
    )
    text = text.replace(
        "Source profile:",
        '<strong style="color:#102a43;">Source profile:</strong>',
    )
    text = text.replace(
        "Evidence note:",
        '<strong style="color:#102a43;">Evidence note:</strong>',
    )
    for label in (
        "Headline:",
        "By:",
        "Published:",
        "Type:",
        "Region:",
        "Original link:",
        "Caveat:",
    ):
        text = text.replace(label, f'<strong style="color:#102a43;">{label}</strong>')
    return text
