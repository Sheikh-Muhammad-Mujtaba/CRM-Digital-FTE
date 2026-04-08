# Local Testing Guide

This guide validates the full Customer Support FTE loop locally:
web/whatsapp/gmail inbound -> Kafka -> agent skills/tools -> outbound reply.

## 1) Prerequisites

- Python 3.11+ (3.12 recommended)
- Node 20+
- Docker Desktop (for Kafka + Zookeeper)
- A running Postgres DB (local or Neon)
- Gmail OAuth values in `backend/.env`:
  - `GMAIL_CLIENT_ID`
  - `GMAIL_CLIENT_SECRET`
  - `GMAIL_REFRESH_TOKEN`
- Gemini + Twilio keys if testing AI + WhatsApp:
  - `GEMINI_API_KEY`
  - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`

## 2) Configure env

In `backend/.env`, make sure at least:

- `DATABASE_URL=postgresql+asyncpg://...`
- `KAFKA_BOOTSTRAP_SERVERS=localhost:29092`
- `KAFKA_INTAKE_TOPIC=fte.inbound`
- `KAFKA_CONSUMER_GROUP=fte-message-processor`
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
- `GMAIL_PUBSUB_TOPIC=projects/<project>/topics/<topic>`
- `GMAIL_WEBHOOK_SECRET=<random>` (recommended)
- `GEMINI_API_KEY=<key>`

In `frontend/.env`:

- `NEXT_PUBLIC_API_URL=http://localhost:8000`

## 3) Install and start services

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Consumer (new terminal):

```bash
cd backend
.venv\Scripts\activate
python -m app.streaming.consumer
```

Kafka:

```bash
docker compose up -d
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## 4) Quick health checks

- API root: `GET http://localhost:8000/`
- API health: `GET http://localhost:8000/health`
- API ready: `GET http://localhost:8000/ready`
- Metrics: `GET http://localhost:8000/metrics`

## 5) Validate skills/tool flow (required by hackathon)

The agent skills are implemented in `backend/app/agent/core.py` and mapped in `specs/skills-manifest.md`:

1. `get_customer_history`
2. `search_knowledge_base`
3. `create_ticket`
4. `escalate_to_human` (when required)
5. `send_response`

Expected behavior:

- Every conversation writes `messages` and `tickets`.
- Email/web outbound goes through Gmail API (`users.messages.send`).
- WhatsApp outbound goes through Twilio API.

## 6) Test each channel

### Web form

1. Open `http://localhost:3000`.
2. Submit name + email + issue text.
3. Verify API returns queued message.
4. Verify consumer logs show agent run.
5. Verify customer receives email response and DB has ticket/message rows.

### WhatsApp

1. Point Twilio WhatsApp webhook to:
   - `POST /api/intake/whatsapp`
2. Send message from your test number.
3. Verify inbound event in consumer logs and outbound Twilio send status.

### Gmail inbound (manual sync)

1. Send an email to the connected Gmail inbox.
2. Trigger sync:
   - `POST /api/gmail/sync?token=<GMAIL_WEBHOOK_SECRET>`
3. Verify queued count > 0 and consumer handles it.

## 7) Gmail Pub/Sub webhook test

1. Create Pub/Sub topic + push subscription in GCP.
2. Grant publisher role to `gmail-api-push@system.gserviceaccount.com` on topic.
3. Set push endpoint:
   - `POST https://<public-api>/api/webhooks/gmail/pubsub?token=<GMAIL_WEBHOOK_SECRET>`
4. Register Gmail watch:
   - `POST /api/gmail/watch?token=<GMAIL_WEBHOOK_SECRET>`
5. Send a test email, confirm webhook + queue + agent processing.

## 8) Daily report endpoint check

Call:

`GET /api/reports/daily-summary?days=1`

Verify non-zero counts after tests.

## 9) Common failures

- `503 Database not reachable`: check `DATABASE_URL` and network.
- Gmail send/fetch errors: refresh token may miss required scopes (`gmail.readonly`, `gmail.modify`, `gmail.send`).
- No consumer activity: verify Kafka up and `KAFKA_BOOTSTRAP_SERVERS` matches.
- WhatsApp not sent: verify Twilio env vars and approved sender in `TWILIO_WHATSAPP_FROM`.
