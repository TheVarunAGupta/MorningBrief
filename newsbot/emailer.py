from __future__ import annotations

import html
import os
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

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
    subject = f"{subject_prefix} - {run_date.isoformat()}"
    html_body = markdown_to_html(analysis.markdown)
    html_body += (
        f"<hr><p><small>Generated with model: {html.escape(analysis.model)}. "
        f"Estimated API cost: GBP {analysis.estimated_cost_gbp:.4f}.</small></p>"
    )
    text_body = (
        analysis.markdown
        + f"\n\nGenerated with model: {analysis.model}. "
        + f"Estimated API cost: GBP {analysis.estimated_cost_gbp:.4f}."
    )
    return RenderedEmail(subject=subject, text=text_body, html=html_body)


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


def markdown_to_html(markdown: str) -> str:
    lines: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h1>{_inline_html(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h2>{_inline_html(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h3>{_inline_html(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                lines.append("<ul>")
                in_list = True
            lines.append(f"<li>{_inline_html(line[2:])}</li>")
        else:
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<p>{_inline_html(line)}</p>")
    if in_list:
        lines.append("</ul>")
    return "\n".join(lines)


def _inline_html(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
