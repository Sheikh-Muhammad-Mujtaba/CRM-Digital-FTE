# Hackathon 5 — checklist

| Item | Notes |
|------|--------|
| Gmail inbound | `POST /api/gmail/sync` + OAuth (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`) |
| Gmail outbound | Same OAuth, Gmail API send |
| WhatsApp | Twilio webhooks + Twilio send |
| Web form | FastAPI intake + email reply via Gmail API |
| Kafka / Postgres / agent | As implemented |
