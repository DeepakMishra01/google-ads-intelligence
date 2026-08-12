"""Send approval emails via SMTP (e.g. a team Gmail app password).

Kept tiny and dependency-free (stdlib smtplib). If SMTP isn't configured the
caller gets a clear ``configured: False`` result instead of an exception, so the
rest of the app never breaks.
"""

from __future__ import annotations

import contextlib
import smtplib
import socket
from collections.abc import Iterator
from email.message import EmailMessage
from typing import Any

from app.config.logging import get_logger
from app.config.settings import get_settings

log = get_logger(__name__)


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


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
    attachment: bytes | None = None,
    attachment_name: str | None = None,
    attachment_mime: tuple[str, str] = ("application", "octet-stream"),
) -> dict[str, Any]:
    """Send one email; returns {sent, ...}. Never raises to the caller."""
    s = get_settings()
    if not smtp_configured():
        return {"sent": False, "configured": False,
                "reason": "SMTP not configured (set SMTP_USER / SMTP_PASSWORD)."}

    msg = EmailMessage()
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
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
