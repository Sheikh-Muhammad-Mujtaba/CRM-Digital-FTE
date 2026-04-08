import asyncio
import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def _twilio_configured() -> bool:
    return bool(
        os.getenv("TWILIO_ACCOUNT_SID")
        and os.getenv("TWILIO_AUTH_TOKEN")
        and os.getenv("TWILIO_WHATSAPP_FROM")
    )


def _is_placeholder_email(email: str | None) -> bool:
    if not email:
        return True
    return email.endswith("@intake.placeholder")


async def send_email_smtp(to_addr: str, subject: str, body: str) -> str:
    if not _smtp_configured():
        return "Email outbound skipped (set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)."

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.environ["SMTP_FROM"]
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    def _send_sync():
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)

    await asyncio.to_thread(_send_sync)
    return f"Email sent to {to_addr}."


async def send_twilio_whatsapp(to_number: str, body: str) -> str:
    if not _twilio_configured():
        return "WhatsApp outbound skipped (set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM)."

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    from_wa = os.environ["TWILIO_WHATSAPP_FROM"]
    to_wa = to_number.strip()
    if not to_wa.startswith("whatsapp:"):
        to_wa = f"whatsapp:{to_wa}" if to_wa.startswith("+") else f"whatsapp:+{to_wa}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {"From": from_wa, "To": to_wa, "Body": body[:1600]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, data=data, auth=(sid, token))
        if r.status_code >= 400:
            logger.error("Twilio error %s: %s", r.status_code, r.text)
            return f"WhatsApp send failed: HTTP {r.status_code}"
    return f"WhatsApp message sent to {to_wa}."


async def dispatch_channel_reply(
    *,
    channel: str,
    customer_email: str | None,
    customer_phone: str | None,
    response_text: str,
) -> str:
    """
    Deliver the agent reply on the correct channel.
    - web + email: SMTP to the address from the form / CRM.
    - email: SMTP to the customer email.
    - whatsapp: Twilio WhatsApp API.
    """
    business = os.getenv("BUSINESS_NAME", "Support")
    subj = os.getenv("SUPPORT_EMAIL_SUBJECT_PREFIX", f"[{business}] Support")

    if channel == "whatsapp":
        if not customer_phone:
            return "WhatsApp outbound skipped (no customer phone on record)."
        return await send_twilio_whatsapp(customer_phone, response_text)

    if channel in ("web", "email"):
        if _is_placeholder_email(customer_email):
            return "Email outbound skipped (no valid customer email)."
        assert customer_email is not None
        subject = f"{subj} — Response to your inquiry"[:200]
        if channel == "web":
            body = (
                f"Thank you for contacting {business}.\n\n"
                f"{response_text}\n\n—\n{business} Support"
            )
        else:
            body = f"{response_text}\n\n—\n{business} Support"
        try:
            return await send_email_smtp(customer_email, subject, body)
        except Exception as exc:
            logger.exception("SMTP failure")
            return f"Email send failed: {exc!s}"

    return f"No outbound adapter for channel={channel!r}."
