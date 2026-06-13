"""Alert formatting and multi-channel dispatch
(Telegram, Discord, Slack, SMTP/SendGrid email, Twilio SMS, ntfy push)."""
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from .config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


DISCLAIMER = "Research alert — not financial advice. Options involve substantial risk."


def _contract_bits(alert: dict) -> dict | None:
    """Normalized contract fields shared by every formatter."""
    c = alert.get("contract")
    if not c:
        return None
    return {
        "name": (
            f"{alert['ticker']} {c.get('expiration')} "
            f"${c.get('strike')} {'CALL' if c.get('option_type') == 'call' else 'PUT'}"
        ),
        "delta": c.get("delta"),
        "iv_pct": round(float(c["iv"]) * 100, 1) if c.get("iv") is not None else None,
        "volume": c.get("volume"),
        "oi": c.get("open_interest"),
        "spread": c.get("spread_pct"),
    }


def format_alert(alert: dict) -> str:
    """Plain text — SMS, DB record, and fallback for any channel."""
    lines = [
        f"{alert['decision']} ALERT: {alert['ticker']}" if alert["decision"] != "NO TRADE"
        else f"NO TRADE: {alert['ticker']}",
        f"Signal score: {alert['score']} / 100",
    ]
    if alert.get("confidence"):
        lines.append(f"Confidence: {alert['confidence']}")
    if alert.get("reasons"):
        lines.append("Reason:")
        lines.extend(f"- {r}" for r in alert["reasons"])
    bits = _contract_bits(alert)
    if bits:
        lines.append("Candidate contract:")
        lines.append(bits["name"])
        if bits["delta"] is not None:
            lines.append(f"Delta: {bits['delta']}")
        if bits["iv_pct"] is not None:
            lines.append(f"IV: {bits['iv_pct']}%")
        lines.append(f"Volume: {bits['volume']}")
        lines.append(f"Open Interest: {bits['oi']}")
        lines.append(f"Bid/Ask Spread: {bits['spread']}%")
    if alert.get("risks"):
        lines.append("Risk:")
        lines.extend(f"- {r}" for r in alert["risks"])
    if alert.get("invalidation_level"):
        lines.append(f"Invalidation: {alert['invalidation_level']}")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def format_alert_markdown(alert: dict, underline: bool = False) -> str:
    """Markdown — ntfy (rendered in app/web) and Discord (underline=True: __x__)."""
    emoji = {"CALL": "🟢", "PUT": "🔴"}.get(alert["decision"], "⚪")
    u = (lambda s: f"__{s}__") if underline else (lambda s: s)
    lines = [
        f"{emoji} **{alert['decision']} ALERT: {alert['ticker']}** {emoji}",
        "",
        f"**Signal score:** {alert['score']} / 100"
        + (f"  ·  **Confidence:** {u(alert['confidence'])}" if alert.get("confidence") else ""),
    ]
    if alert.get("reasons"):
        lines += ["", "📋 **Why this alert**"]
        lines += [f"• {r}" for r in alert["reasons"]]
    bits = _contract_bits(alert)
    if bits:
        lines += ["", "🎯 **Candidate contract**", f"**{u(bits['name'])}**"]
        detail = []
        if bits["delta"] is not None:
            detail.append(f"Δ **{bits['delta']}**")
        if bits["iv_pct"] is not None:
            detail.append(f"IV **{bits['iv_pct']}%**")
        detail.append(f"Vol {bits['volume']:,}" if isinstance(bits["volume"], (int, float)) else f"Vol {bits['volume']}")
        detail.append(f"OI {bits['oi']:,}" if isinstance(bits["oi"], (int, float)) else f"OI {bits['oi']}")
        detail.append(f"Spread **{bits['spread']}%**")
        lines.append(" · ".join(detail))
    if alert.get("risks"):
        lines += ["", "⚠️ **Risks**"]
        lines += [f"• *{r}*" for r in alert["risks"]]
    if alert.get("invalidation_level"):
        lines += ["", f"🛑 **Invalidation:** {u(alert['invalidation_level'])}"]
    lines += ["", f"*{DISCLAIMER}*"]
    return "\n".join(lines)


def format_alert_html(alert: dict) -> str:
    """HTML — Telegram (parse_mode=HTML) and email. Bold, italic, real underline."""
    emoji = {"CALL": "🟢", "PUT": "🔴"}.get(alert["decision"], "⚪")
    color = {"CALL": "#10b981", "PUT": "#f43f5e"}.get(alert["decision"], "#94a3b8")
    parts = [
        f'{emoji} <b>{alert["decision"]} ALERT: <span style="color:{color}">{alert["ticker"]}</span></b> {emoji}',
        "",
        f"<b>Signal score:</b> {alert['score']} / 100"
        + (f"  ·  <b>Confidence:</b> <u>{alert['confidence']}</u>" if alert.get("confidence") else ""),
    ]
    if alert.get("reasons"):
        parts += ["", "📋 <b>Why this alert</b>"]
        parts += [f"• {r}" for r in alert["reasons"]]
    bits = _contract_bits(alert)
    if bits:
        parts += ["", "🎯 <b>Candidate contract</b>", f"<b><u>{bits['name']}</u></b>"]
        detail = []
        if bits["delta"] is not None:
            detail.append(f"Δ <b>{bits['delta']}</b>")
        if bits["iv_pct"] is not None:
            detail.append(f"IV <b>{bits['iv_pct']}%</b>")
        detail.append(f"Vol {bits['volume']:,}" if isinstance(bits["volume"], (int, float)) else f"Vol {bits['volume']}")
        detail.append(f"OI {bits['oi']:,}" if isinstance(bits["oi"], (int, float)) else f"OI {bits['oi']}")
        detail.append(f"Spread <b>{bits['spread']}%</b>")
        parts.append(" · ".join(detail))
    if alert.get("risks"):
        parts += ["", "⚠️ <b>Risks</b>"]
        parts += [f"• <i>{r}</i>" for r in alert["risks"]]
    if alert.get("invalidation_level"):
        parts += ["", f"🛑 <b>Invalidation:</b> <u>{alert['invalidation_level']}</u>"]
    parts += ["", f"<i>{DISCLAIMER}</i>"]
    return "\n".join(parts)


def format_alert_slack(alert: dict) -> str:
    """Slack mrkdwn — *bold* and _italic_ (Slack has no underline)."""
    emoji = {"CALL": "🟢", "PUT": "🔴"}.get(alert["decision"], "⚪")
    lines = [
        f"{emoji} *{alert['decision']} ALERT: {alert['ticker']}* {emoji}",
        f"*Signal score:* {alert['score']} / 100"
        + (f"  ·  *Confidence:* {alert['confidence']}" if alert.get("confidence") else ""),
    ]
    if alert.get("reasons"):
        lines.append("📋 *Why this alert*")
        lines += [f"• {r}" for r in alert["reasons"]]
    bits = _contract_bits(alert)
    if bits:
        lines.append(f"🎯 *{bits['name']}*")
        lines.append(
            f"Δ *{bits['delta']}* · IV *{bits['iv_pct']}%* · Vol {bits['volume']} · "
            f"OI {bits['oi']} · Spread *{bits['spread']}%*"
        )
    if alert.get("risks"):
        lines.append("⚠️ " + " · ".join(f"_{r}_" for r in alert["risks"]))
    if alert.get("invalidation_level"):
        lines.append(f"🛑 *Invalidation:* {alert['invalidation_level']}")
    lines.append(f"_{DISCLAIMER}_")
    return "\n".join(lines)


def _send_telegram(html: str) -> None:
    httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        json={"chat_id": settings.telegram_chat_id, "text": html, "parse_mode": "HTML"},
        timeout=15.0,
    ).raise_for_status()


def _send_discord(markdown: str) -> None:
    httpx.post(settings.discord_webhook_url, json={"content": markdown}, timeout=15.0).raise_for_status()


def _send_slack(mrkdwn: str) -> None:
    httpx.post(settings.slack_webhook_url, json={"text": mrkdwn}, timeout=15.0).raise_for_status()


def _send_email(html: str, subject: str) -> None:
    msg = MIMEText(html.replace("\n", "<br>"), "html")
    msg["Subject"] = subject
    msg["From"] = settings.alert_email_from
    msg["To"] = settings.alert_email_to
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def _send_sendgrid(html: str, subject: str) -> None:
    from_email = settings.alert_email_from or settings.alert_email
    httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
        json={
            "personalizations": [{"to": [{"email": settings.alert_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{
                "type": "text/html",
                "value": f'<div style="font-family:system-ui,sans-serif;font-size:15px;'
                         f'line-height:1.5">{html.replace(chr(10), "<br>")}</div>',
            }],
        },
        timeout=15.0,
    ).raise_for_status()


def _send_twilio_sms(text: str) -> None:
    httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={"From": settings.twilio_from, "To": settings.alert_phone, "Body": text[:1500]},
        timeout=15.0,
    ).raise_for_status()


def _send_ntfy(markdown: str, subject: str, decision: str = "") -> None:
    tags = {"CALL": "chart_with_upwards_trend", "PUT": "chart_with_downwards_trend"}.get(
        decision, "bell"
    )
    httpx.post(
        f"{settings.ntfy_base_url}/{settings.ntfy_topic}",
        content=markdown.encode(),
        headers={
            "Title": subject,
            "Tags": tags,
            "Markdown": "yes",  # render bold/italic in the ntfy apps
            "Priority": "high" if decision in ("CALL", "PUT") else "default",
        },
        timeout=15.0,
    ).raise_for_status()


def dispatch(alert: dict) -> bool:
    """Send the alert to every configured channel, each in its richest dialect:
    HTML (Telegram, email), Markdown (ntfy, Discord), mrkdwn (Slack), plain (SMS)."""
    text = format_alert(alert)
    md = format_alert_markdown(alert)
    md_discord = format_alert_markdown(alert, underline=True)
    html = format_alert_html(alert)
    slack = format_alert_slack(alert)
    subject = f"{alert['decision']} alert: {alert['ticker']} ({alert['score']}/100)"
    sent = False
    channels = [
        (settings.telegram_bot_token and settings.telegram_chat_id, "telegram", lambda: _send_telegram(html)),
        (settings.discord_webhook_url, "discord", lambda: _send_discord(md_discord)),
        (settings.slack_webhook_url, "slack", lambda: _send_slack(slack)),
        (settings.smtp_host and settings.alert_email_to, "email", lambda: _send_email(html, subject)),
        (settings.sendgrid_api_key and settings.alert_email, "sendgrid", lambda: _send_sendgrid(html, subject)),
        (
            settings.twilio_account_sid and settings.twilio_auth_token
            and settings.twilio_from and settings.alert_phone,
            "twilio-sms",
            lambda: _send_twilio_sms(text),
        ),
        (settings.ntfy_topic, "ntfy", lambda: _send_ntfy(md, subject, alert["decision"])),
    ]
    for configured, name, send in channels:
        if not configured:
            continue
        try:
            send()
            sent = True
        except Exception:
            log.exception("Failed to send %s alert for %s", name, alert["ticker"])
    return sent
