import asyncio
import logging
import os

import httpx

from integrations.gmail_api import send_email_message

logger = logging.getLogger(__name__)


def _gmail_oauth_configured() -> bool:
    return bool(
        os.getenv("GMAIL_CLIENT_ID")
        and os.getenv("GMAIL_CLIENT_SECRET")
        and os.getenv("GMAIL_REFRESH_TOKEN")
    )


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


async def _send_email_via_gmail_api(to_addr: str, subject: str, body: str) -> str:
    if not _gmail_oauth_configured():
        return "Email skipped: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN."

    def _send():
        send_email_message(to_addr, subject, body)

    try:
        await asyncio.to_thread(_send)
    except Exception as exc:
        logger.exception("Gmail API send failed")
        return f"Gmail send failed: {exc!s}"
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
        response = await client.post(url, data=data, auth=(sid, token))
        if response.status_code >= 400:
            logger.error("Twilio error %s: %s", response.status_code, response.text)
            return f"WhatsApp send failed: HTTP {response.status_code}"
    return f"WhatsApp message sent to {to_wa}."


async def dispatch_channel_reply(
    *,
    channel: str,
    customer_email: str | None,
    customer_phone: str | None,
    response_text: str,
) -> str:
    business = os.getenv("BUSINESS_NAME", "Support")

    if channel == "whatsapp":
        if not customer_phone:
            return "WhatsApp outbound skipped (no customer phone on record)."
        return await send_twilio_whatsapp(customer_phone, response_text)

    if channel in ("web", "email"):
        if _is_placeholder_email(customer_email):
            return "Email skipped (no valid customer email)."
        assert customer_email is not None
        subject = f"[{business}] Support — Response to your inquiry"[:200]
        body = (
            f"Thank you for contacting {business}.\n\n{response_text}\n\n—\n{business} Support"
            if channel == "web"
            else f"{response_text}\n\n—\n{business} Support"
        )
        try:
            return await _send_email_via_gmail_api(customer_email, subject, body)
        except Exception as exc:
            logger.exception("Email outbound failure")
            return f"Email failed: {exc!s}"

    return f"No outbound adapter for channel={channel!r}."
