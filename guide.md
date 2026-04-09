# CRM Digital FTE - Local Testing and Deployment Guide

## 1) Prerequisites
- Python 3.10+
- Node.js 18+
- Docker Desktop (for Kafka/Zookeeper)
- PostgreSQL (Neon or local Postgres)

## 2) Environment Setup

### ⚠️ CRITICAL: Gemini API Key Setup
**Before running anything, you MUST get a free Gemini API key:**

1. **Get your free API key:**
   - Visit: https://aistudio.google.com/app/apikeys
   - Click "Create API Key" → "Create API key in new project"
   - Copy the key (starts with `abcd...`)

2. **Add to backend/.env:**
   ```bash
   # backend/.env
   GEMINI_API_KEY=abcd...
   ```

3. **Verify it's loaded:**
   ```bash
   # PowerShell
   $env:GEMINI_API_KEY
   # Should show: abcd...
   ```

If this step is skipped, you'll see:
```
openai.BadRequestError: Error code: 400 - Missing or invalid Authorization header
```

### Backend env
1. Copy `backend/env.example` to `backend/.env`.
2. Fill required values:
   - ✅ `GEMINI_API_KEY` (see above - CRITICAL)
   - `DATABASE_URL`
   - `KAFKA_BOOTSTRAP_SERVERS` (default local: `localhost:29092`)
   - Optional for webhooks: `TWILIO_*`, `GMAIL_*`

3. **Minimal .env template:**
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/crm_fte
   GEMINI_API_KEY=abcd...
   KAFKA_BOOTSTRAP_SERVERS=localhost:29092
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=adminpass
   ```

### Frontend env
1. Create `frontend/.env.local`.
2. Add:
   - `NEXT_PUBLIC_API_URL=http://localhost:8000`

## 3) Install Dependencies

### Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend
```powershell
cd frontend
npm install
```

## 4) Start Local Infrastructure

From repo root:
```powershell
docker-compose up -d
```

This starts Kafka and Zookeeper used by the intake stream.

## 5) Database Migration

```powershell
cd backend
.\venv\Scripts\activate
alembic upgrade head
```

## 6) Run Services

Open 3 terminals:

### Terminal A - API
```powershell
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

### Terminal B - Kafka Consumer Worker
```powershell
cd backend
.\venv\Scripts\activate
python -m workers.message_processor
```

### Terminal C - Frontend
```powershell
cd frontend
npm run dev
```

## 7) Local Test Flow

1. Open `http://localhost:3000` for web intake form testing.
2. Submit a support message.
3. Validate:
   - API accepts request (`/api/intake/web`)
   - Kafka consumer processes event
   - Agent tools run and persist messages/tickets in DB.
4. Open `http://localhost:3000/admin` to view admin portal KPIs and latest tickets.
5. You will be redirected to `http://localhost:3000/admin/login`.
6. Use admin credentials from env (`ADMIN_USERNAME`, `ADMIN_PASSWORD`) to sign in and load protected metrics.

## 8) Testing Webhooks

### Web Form Integration (Test Immediately)
```bash
# Test web intake endpoint
curl -X POST http://localhost:8000/api/intake/web \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "message": "I need help with my account",
    "subject": "Support Request"
  }'

# Response should be:
# {"status": "success", "message": "Message queued for processing"}
```

### WhatsApp/Twilio Integration (Optional - Requires Setup)
```bash
# Simulate Twilio webhook (local testing)
curl -X POST http://localhost:8000/api/intake/whatsapp \
  -F "From=whatsapp:+1234567890" \
  -F "Body=Test message from WhatsApp" \
  -F "MessageSid=SM123456789" \
  -F "AccountSid=AC123456789"

# To connect real Twilio:
# 1. Get public URL: ngrok http 8000
# 2. Configure in Twilio console:
#    Phone Numbers → Your WhatsApp number → Webhook URL
#    Set to: https://your-public-url.ngrok.io/api/intake/whatsapp
```

### Gmail Integration (Optional - Requires Setup)
```bash
# Manual Gmail sync (polls inbox)
curl -X POST http://localhost:8000/api/gmail/sync \
  -H "X-Admin-User: admin" \
  -H "X-Admin-Pass: adminpass"

# Register Gmail watch (Pub/Sub push)
curl -X POST http://localhost:8000/api/gmail/watch \
  -H "X-Admin-User: admin" \
  -H "X-Admin-Pass: adminpass"

# To configure Gmail:
# See TROUBLESHOOTING.md section "Gmail Webhook Not Working"
```

### Verify Messages in Database
```bash
# Connect to database and check:
SELECT 
  c.id,
  m.sender_type,
  m.content,
  m.channel,
  m.created_at
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
ORDER BY m.created_at DESC
LIMIT 10;
```

## 9) Useful Health Endpoints
- `GET http://localhost:8000/health`
- `GET http://localhost:8000/ready`
- `GET http://localhost:8000/api/reports/daily-summary` (admin headers required)
- `GET http://localhost:8000/api/admin/dashboard` (admin headers required)
- `GET http://localhost:8000/api/admin/dashboard/analytics` (admin headers required)
- `GET http://localhost:8000/api/admin/dashboard/activity` (admin headers required)

## 10) Troubleshooting

**"GEMINI_API_KEY is not set"**
- Solution: See section 2) CRITICAL: Gemini API Key Setup
- Verify: `$env:GEMINI_API_KEY` shows your API key
- Get key: https://aistudio.google.com/app/apikeys

**"Connection refused" on Kafka**
- Solution: Run `docker-compose up -d` in root directory

**"Database URL invalid"**
- Solution: Check `DATABASE_URL` format in backend/.env
- Format: `postgresql+asyncpg://user:pass@host:5432/dbname`

**"No such file" for Gmail service account**
- Solution: Set `GMAIL_SERVICE_ACCOUNT_JSON` to correct path
- Or leave blank if not using Gmail integration

For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 11) Deployment (Recommended Layout)

### Option A - Split Deploy (Simple)
- **Frontend**: Vercel
- **Backend API + Worker**: Render/Fly/VM
- **Database**: Neon Postgres
- **Kafka**: Confluent Cloud

### Option B - Kubernetes (Hackathon Target)
1. Build and push backend image.
2. Apply manifests:
   - `k8s/namespace.yaml`
   - `k8s/configmap.yaml`
3. Deploy API and worker separately (different deployments).
4. Configure autoscaling for workers.

## 12) Production Checklist
- Secrets injected via environment variables or secret manager.
- CORS restricted to known frontend domains.
- Webhook signatures validated (Twilio/Gmail).
- Database backups enabled.
- Worker restarts and DLQ handling configured.
- Basic monitoring on API latency, escalation rate, ticket throughput.
