"""Send approval emails.

Two transports: the **Resend HTTP API** (preferred — works on hosts like Render
that block outbound SMTP) and **SMTP** (fallback / local dev). If neither is
configured the caller gets ``configured: False`` instead of an exception, so the
rest of the app never breaks.
"""

from __future__ import annotations

import base64
import contextlib
import smtplib
import socket
from collections.abc import Iterator
from email.message import EmailMessage
from typing import Any

from app.config.logging import get_logger
from app.config.settings import get_settings

log = get_logger(__name__)


def _recipients(to: str) -> list[str]:
    return [a.strip() for a in (to or "").split(",") if a.strip()]


def _sender_parts() -> tuple[str, str]:
    """(name, email) from EMAIL_FROM (accepts 'Name <email>' or a bare email)."""
    from email.utils import parseaddr

    s = get_settings()
    raw = s.email_from or s.smtp_from or s.smtp_user
    name, addr = parseaddr(raw)
    return (name or "KollegeApply Ads"), addr


def _send_via_brevo(
    *, to: str, subject: str, body: str, html: str | None,
    attachment: bytes | None, attachment_name: str | None,
    cc: str | None = None,
) -> dict[str, Any]:
    """Send over the Brevo HTTPS API (port 443). Sender verified by email link —
    no DNS needed — so it works when you can't touch domain records."""
    import httpx

    s = get_settings()
    _name, addr = _sender_parts()
    if not addr:
        return {"sent": False, "configured": False,
                "reason": "Set EMAIL_FROM to your Brevo-verified sender address."}
    payload: dict[str, Any] = {
        "sender": {"email": addr, "name": _name},
        "to": [{"email": a} for a in _recipients(to)],
        "subject": subject,
        "textContent": body,
    }
    if cc and _recipients(cc):
        payload["cc"] = [{"email": a} for a in _recipients(cc)]
    if html:
        payload["htmlContent"] = html
    if attachment is not None and attachment_name:
        payload["attachment"] = [{
            "content": base64.b64encode(attachment).decode("ascii"),
            "name": attachment_name,
        }]
    try:
        resp = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": s.brevo_api_key, "Content-Type": "application/json",
                     "accept": "application/json"},
            json=payload,
            timeout=20,
        )
        if resp.status_code >= 400:
            return {"sent": False, "configured": True,
                    "reason": f"Brevo {resp.status_code}: {resp.text[:200]}"}
        return {"sent": True, "configured": True, "to": to, "via": "brevo"}
    except Exception as exc:  # noqa: BLE001
        log.info("email.brevo_failed", to=to, error=str(exc))
        return {"sent": False, "configured": True, "reason": str(exc)}


def _send_via_resend(
    *, to: str, subject: str, body: str, html: str | None,
    attachment: bytes | None, attachment_name: str | None,
    cc: str | None = None,
) -> dict[str, Any]:
    """Send over the Resend HTTPS API (port 443 — not blocked by Render)."""
    import httpx

    s = get_settings()
    sender = s.email_from or s.smtp_from or s.smtp_user
    if not sender:
        return {"sent": False, "configured": False,
                "reason": "Set EMAIL_FROM to a Resend-verified sender address."}
    payload: dict[str, Any] = {
        "from": sender,
        "to": _recipients(to),
        "subject": subject,
        "text": body,
    }
    if cc and _recipients(cc):
        payload["cc"] = _recipients(cc)
    if html:
        payload["html"] = html
    if attachment is not None and attachment_name:
        payload["attachments"] = [{
            "filename": attachment_name,
            "content": base64.b64encode(attachment).decode("ascii"),
        }]
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {s.resend_api_key}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        if resp.status_code >= 400:
            return {"sent": False, "configured": True,
                    "reason": f"Resend {resp.status_code}: {resp.text[:200]}"}
        return {"sent": True, "configured": True, "to": to, "via": "resend"}
    except Exception as exc:  # noqa: BLE001 — surface a clean error to the UI
        log.info("email.resend_failed", to=to, error=str(exc))
        return {"sent": False, "configured": True, "reason": str(exc)}


@contextlib.contextmanager
def _prefer_ipv4() -> Iterator[None]:
    """Force DNS resolution to IPv4 for the duration.

    Hosts like Render advertise IPv6 but often can't route it outbound, so a plain
    smtplib connection to smtp.gmail.com fails with '[Errno 101] Network is
    unreachable'. Pinning getaddrinfo to AF_INET dodges that. Scoped narrowly to
    the send; IPv4 works everywhere so this is safe.
    """
    original = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002
        return original(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_only  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.getaddrinfo = original  # type: ignore[assignment]


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_user and s.smtp_password)


def email_configured() -> bool:
    s = get_settings()
    return bool(s.brevo_api_key or s.resend_api_key) or smtp_configured()


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
    cc: str | None = None,
    attachment: bytes | None = None,
    attachment_name: str | None = None,
    attachment_mime: tuple[str, str] = ("application", "octet-stream"),
) -> dict[str, Any]:
    """Send one email; returns {sent, ...}. Never raises to the caller.

    ``cc`` is a comma-joined list of copy recipients. Uses Brevo/Resend HTTP APIs
    when configured (work behind SMTP-blocking hosts like Render); else SMTP.
    """
    s = get_settings()
    if s.brevo_api_key:
        return _send_via_brevo(
            to=to, subject=subject, body=body, html=html, cc=cc,
            attachment=attachment, attachment_name=attachment_name,
        )
    if s.resend_api_key:
        return _send_via_resend(
            to=to, subject=subject, body=body, html=html, cc=cc,
            attachment=attachment, attachment_name=attachment_name,
        )
    if not smtp_configured():
        return {"sent": False, "configured": False,
                "reason": "Email not configured (set BREVO_API_KEY or RESEND_API_KEY, "
                          "or SMTP_USER / SMTP_PASSWORD for local use)."}

    msg = EmailMessage()
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    if attachment is not None and attachment_name:
        maintype, subtype = attachment_mime
        msg.add_attachment(
            attachment, maintype=maintype, subtype=subtype, filename=attachment_name
        )

    try:
        with _prefer_ipv4(), smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
            if s.smtp_use_tls:
                server.starttls()
            server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
        return {"sent": True, "configured": True, "to": to}
    except Exception as exc:  # noqa: BLE001 — surface a clean error to the UI
        log.info("email.send_failed", to=to, error=str(exc))
        return {"sent": False, "configured": True, "reason": str(exc)}
