"""Branded, escaped multipart email content for Coyote3 notification workflows."""

from html import escape
from urllib.parse import urlsplit

SEVERITY_COLORS = {
    "info": "#3f5277",
    "important": "#67508e",
    "warning": "#8a5900",
    "critical": "#aa2944",
    "success": "#246950",
}


def render_email(
    *,
    subject: str,
    text_body: str,
    severity: str,
    environment: str,
    action_url: str = "",
    action_label: str = "Open Coyote3",
) -> str:
    """Render an email-safe table layout without trusting caller-supplied HTML.

    Args:
        subject: Heading, escaped as text.
        text_body: Plain text, escaped with paragraph breaks preserved.
        severity: Supported semantic severity label.
        environment: Deployment label; production is not emphasized.
        action_url: Optional absolute HTTP(S) destination for the primary action.
        action_label: Escaped action label.

    Returns:
        HTML body referencing the attached coyote3-logo image by Content-ID.

    Raises:
        ValueError: When severity or a supplied action URL is invalid.
    """
    if severity not in SEVERITY_COLORS:
        raise ValueError("Unsupported email severity")
    color = SEVERITY_COLORS[severity]
    action = ""
    if action_url:
        parsed = urlsplit(action_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("Email action URL must be absolute HTTP(S)")
        action = (
            f'<p style="margin:28px 0"><a href="{escape(action_url, quote=True)}" '
            'style="display:inline-block;background:#584470;color:#fff;padding:12px 20px;'
            f'border-radius:6px;text-decoration:none">{escape(action_label)}</a></p>'
        )
    paragraphs = "".join(
        '<p style="margin:0 0 16px;line-height:1.6;overflow-wrap:anywhere">'
        + escape(part).replace("\n", "<br>")
        + "</p>"
        for part in text_body.split("\n\n")
    )
    env = (
        f'<p style="color:#8a5900">{escape(environment.upper())} ENVIRONMENT</p>'
        if environment and environment.lower() != "production"
        else ""
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#edf0f4;color:#252a34;font-family:Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#fff;border-top:5px solid {color}">
<tr><td style="padding:24px 28px;background:#f4f3f7">
<img src="cid:coyote3-logo" width="100" height="60" alt="Coyote3" style="vertical-align:middle;object-fit:contain">
<strong style="font-size:24px;vertical-align:middle;margin-left:16px">Coyote3</strong>
<p style="margin-bottom:0;color:#5b6170">Clinical genomics</p></td></tr>
<tr><td style="padding:28px">{env}<span style="display:inline-block;background:{color};color:#fff;padding:5px 10px;border-radius:4px;font-size:12px;font-weight:bold">{severity.upper()}</span>
<h1 style="font-size:22px;line-height:1.3;margin:18px 0">{escape(subject)}</h1>
{paragraphs}{action}</td></tr>
<tr><td style="padding:20px 28px;background:#f4f3f7;color:#5b6170;font-size:12px;line-height:1.6">
This is an automated Coyote3 message. This mailbox is not monitored; do not reply.
Contact your Coyote3 administrator for assistance.<br>Coyote3 &middot; Account and application notifications
</td></tr></table></td></tr></table></body></html>"""
