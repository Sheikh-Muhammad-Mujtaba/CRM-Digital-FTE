# Deployment Guide (Free-first)

This project runs best as:

- Backend API (FastAPI)
- Background worker (Kafka consumer)
- Frontend (Next.js)
- Managed Postgres
- Managed Kafka

## Recommended free/low-cost stack

- **Backend API + Worker:** [Render](https://render.com) (free tier available, may sleep)
- **Frontend:** [Vercel](https://vercel.com) free
- **Postgres:** [Neon](https://neon.tech) free
- **Kafka:** [Confluent Cloud](https://www.confluent.io/confluent-cloud/) free credits/tier

## A) Render deployment (backend + worker)

### 1. Create backend Web Service

- Root directory: `backend`
- Build command:
  - `pip install -r requirements.txt`
- Start command:
  - `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set env vars:

- `DATABASE_URL=postgresql+asyncpg://...`
- `GEMINI_API_KEY=...`
- `KAFKA_BOOTSTRAP_SERVERS=<confluent bootstrap>`
- `KAFKA_INTAKE_TOPIC=fte.inbound`
- `KAFKA_CONSUMER_GROUP=fte-message-processor`
- `GMAIL_CLIENT_ID=...`
- `GMAIL_CLIENT_SECRET=...`
- `GMAIL_REFRESH_TOKEN=...`
- `GMAIL_PUBSUB_TOPIC=projects/<project>/topics/<topic>`
- `GMAIL_WEBHOOK_SECRET=<random>`
- `TWILIO_ACCOUNT_SID=...`
- `TWILIO_AUTH_TOKEN=...`
- `TWILIO_WHATSAPP_FROM=whatsapp:+...`
- `BUSINESS_NAME=...`
- `BUSINESS_FOCUS=...`
- `CORS_ORIGINS=https://<your-frontend-domain>`

### 2. Create backend Worker Service

- Same repo + same env as API
- Root directory: `backend`
- Build command:
  - `pip install -r requirements.txt`
- Start command:
  - `python -m app.streaming.consumer`

### 3. Run migrations

Use Render shell or one-off job:

```bash
cd backend
alembic upgrade head
```

## B) Frontend deployment (Vercel free)

- Import `frontend` as project
- Set env:
  - `NEXT_PUBLIC_API_URL=https://<render-api-domain>`
- Deploy

## C) Gmail Pub/Sub setup for deployed API

1. Create Pub/Sub topic in same Google project as Gmail API.
2. Grant publisher role to:
   - `gmail-api-push@system.gserviceaccount.com`
3. Create push subscription to:
   - `https://<render-api-domain>/api/webhooks/gmail/pubsub?token=<GMAIL_WEBHOOK_SECRET>`
4. Register watch:
   - `POST https://<render-api-domain>/api/gmail/watch?token=<GMAIL_WEBHOOK_SECRET>`
5. Renew watch periodically (before expiry, usually < 7 days).

## D) Twilio webhook setup

- Incoming WhatsApp webhook URL:
  - `https://<render-api-domain>/api/intake/whatsapp`

## E) Post-deploy smoke test

1. `GET /health` -> healthy
2. `GET /ready` -> ready
3. Submit web form -> ticket + email response
4. Send WhatsApp test -> Twilio response received
5. Send Gmail test -> Pub/Sub webhook triggers queue -> agent response
6. `GET /api/reports/daily-summary?days=1` -> counts update

## Notes about free tiers

- Free services may sleep and cause cold starts.
- Kafka free plans may have throughput/topic limits.
- If persistent reliability is needed, move API + worker to paid plans first.
