# CRM Digital FTE - Autonomous Customer Success Platform

<div align="center">

**An enterprise-grade AI-powered customer success platform using Gemini 2.5 Flash and OpenAI Agents SDK for autonomous multi-channel support.**

[Features](#features) • [Quick Start](#quick-start) • [Architecture](#architecture) • [API Docs](#api-documentation) • [Admin Dashboard](#admin-dashboard) • [Deployment](#deployment)

</div>

---

## Overview

**CRM Digital FTE** (Full-Time Equivalent) is a production-ready autonomous customer success platform that processes support inquiries across multiple channels and responds intelligently using AI agents. The system combines:

- **Intelligent Routing** - Google Gemini 2.5 Flash with OpenAI Agents SDK for semantic understanding and autonomous decision-making
- **Multi-Channel Intake** - Unified ingestion from Web Forms, Twilio WhatsApp, and Gmail
- **Event-Driven Architecture** - Kafka-based async streaming for scalable message processing
- **Knowledge Management** - pgvector-powered semantic search across corporate documentation
- **Comprehensive Admin Dashboard** - Real-time KPIs, sentiment analysis, and conversation tracking

## Features

### 🤖 Intelligent Agent System
- **Autonomous Response Generation** - AI-driven responses that adapt to customer intent and channel context
- **Knowledge Base Integration** - Vector-based semantic search across corporate documentation via PostgreSQL pgvector
- **Conversation Memory** - Full customer history tracking for context-aware responses
- **Smart Escalation** - Automatic detection and escalation of complex issues to human agents
- **Multi-Tool Execution** - Simultaneous function calls for search, ticketing, and response dispatch

### 📡 Multi-Channel Support
- **Web Forms** - Glassmorphism-styled responsive intake forms (Next.js)
- **Email Integration** - Gmail webhook support for seamless email-to-ticket conversion
- **WhatsApp** - Twilio WhatsApp integration for mobile-first support
- **Channel-Aware Responses** - Automatic tone and format adjustment based on communication channel

### 📊 Admin Operations Dashboard
- **Real-Time KPIs** - Tickets (total/open), message volume, escalation rate, sentiment score
- **Sentiment Analysis** - Keyword-based message sentiment classification with positive/negative/neutral distribution
- **Activity Timeline** - Complete conversation trace with enriched metadata and filtering
- **Channel Status** - Per-channel performance metrics and health status
- **Negative Watchlist** - Curated feed of recent negative customer interactions for proactive response

### 🗄️ Enterprise Data Layer
- **Async SQLAlchemy** - Fully async ORM for high-concurrency database operations
- **PostgreSQL with pgvector** - Vector embeddings for semantic search and similarity matching
- **Neon Database** - Serverless PostgreSQL with automatic backups and scaling
- **Alembic Migrations** - Version-controlled database schema evolution
- **Structured Query Layer** - Modular, type-safe database queries

## Quick Start

### Prerequisites
- **Python** 3.10 or later
- **Node.js** 18 or later
- **Docker & Docker Compose** (for local Kafka)
- **PostgreSQL** (Neon or self-hosted)
- **API Keys**
  - Google Gemini API key (for AI agent)
  - Twilio credentials (for WhatsApp)
  - Gmail service account (for email integration)

### Installation (5 minutes)

1. **Clone and navigate to project**
   ```bash
   cd d:\Mujtaba_data\CRM-Digital-FTE
   ```

2. **Set up environment files**
   ```bash
   # Backend configuration
   cp backend/env.example backend/.env
   
   # Frontend configuration
   cp frontend/.env.example frontend/.env.local
   ```

3. **Configure `.env` with your credentials**
   ```bash
   # backend/.env
   DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
   GEMINI_API_KEY=your-gemini-api-key
   KAFKA_BOOTSTRAP_SERVERS=localhost:29092
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your-secure-password
   ```

4. **Start infrastructure services**
   ```bash
   # Starts Kafka and Zookeeper
   docker-compose up -d
   ```

5. **Install and run backend**
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn main:app --reload --port 8000
   ```

6. **Install and run frontend** (new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

7. **Start message processing worker** (new terminal)
   ```bash
   cd backend
   .\venv\Scripts\activate
   python -m workers.message_processor
   ```

**System is ready at:** http://localhost:3000

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTAKE CHANNELS                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │Web Forms │  │  Gmail   │  │ WhatsApp │                       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
└───────┼─────────────┼─────────────┼──────────────────────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   FastAPI Intake Router    │
        │   (/api/intake/*)          │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │    Kafka Event Stream      │
        │ (Message Producer/Buffer)  │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │  Kafka Consumer Worker     │
        │ (message_processor.py)     │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────────────┐
        │   OpenAI Agents SDK Agent Orchestrator   │
        │   (app/agent/core.py)              │
        │                                    │
        │  Tools:                            │
        │  • search_knowledge_base          │
        │  • get_customer_history           │
        │  • create_ticket                  │
        │  • escalate_to_human              │
        │  • send_response                  │
        └─────────────┬──────────────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   PostgreSQL + pgvector    │
        │   • Messages               │
        │   • Customers              │
        │   • Tickets                │
        │   • Knowledge Base         │
        │   • Conversations          │
        └────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   ADMIN DASHBOARD LAYER                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   /admin (Next.js 16)                                    │   │
│  │                                                          │   │
│  │  • Real-time KPI cards (6 metrics)                      │   │
│  │  • Sentiment distribution and analysis                  │   │
│  │  • Activity timeline with filtering                     │   │
│  │  • Conversation trace with metadata                     │   │
│  │  • Channel status monitoring                            │   │
│  │  • Negative sentiment watchlist                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                       │
│  ┌──────────────────────▼──────────────────────┐               │
│  │  Protected Admin API Endpoints              │               │
│  │  • GET /api/admin/dashboard                │               │
│  │  • GET /api/admin/dashboard/analytics      │               │
│  │  • GET /api/admin/dashboard/activity       │               │
│  │  • GET /api/reports/daily-summary          │               │
│  └─────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| Component | Location | Purpose | Tech Stack |
|-----------|----------|---------|-----------|
| **Frontend** | `/frontend` | Web forms, admin dashboard, user interface | Next.js 16.2, React 19, TypeScript, Tailwind CSS 4 |
| **API Server** | `/backend/api` | REST endpoints for intake, health, admin queries | FastAPI, SQLAlchemy, Pydantic |
| **Agent Orchestrator** | `/backend/app/agent` | AI decision-making and tool execution | OpenAI Agents SDK, Gemini 2.5 Flash, Python 3.10+ |
| **Message Worker** | `/backend/workers` | Kafka consumer and event processing | Confluent Kafka, AsyncIO |
| **Database Layer** | `/backend/database` | Models, migrations, and query modules | SQLAlchemy 2.0 (async), Alembic, PostgreSQL |
| **Message Bus** | Docker (Compose) | Event streaming and decoupling | Apache Kafka, ZooKeeper |

---

## Technology Stack

### Backend
- **Runtime:** Python 3.10+
- **Web Framework:** FastAPI (async)
- **ORM:** SQLAlchemy 2.0 (async)
- **AI Framework:** OpenAI Agents SDK
- **LLM Model:** Google Gemini 2.5 Flash
- **Database:** PostgreSQL + pgvector extension
- **Message Queue:** Apache Kafka (Confluent)
- **Vector Search:** pgvector (cosine distance)
- **Migrations:** Alembic
- **API Documentation:** Swagger/OpenAPI

### Frontend
- **Framework:** Next.js 16.2.2
- **React Version:** 19.2.4
- **Language:** TypeScript 5
- **Styling:** Tailwind CSS 4
- **Authentication:** Session-based with cookie gate
- **HTTP Client:** Native fetch API

### Infrastructure
- **Containerization:** Docker & Docker Compose
- **Orchestration:** Kubernetes-ready (k8s/ folder)
- **Deployment:** Cloud-ready (Neon, AWS, GCP, Azure)

---

## Configuration

### Environment Variables

#### Backend (backend/.env)
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/crm_fte

# AI/LLM
GEMINI_API_KEY=your-google-gemini-api-key

# Message Queue
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_GROUP_ID=crm-fte-consumer

# Admin Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# Integrations
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890

GMAIL_SERVICE_ACCOUNT_JSON=path/to/service-account.json

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

#### Frontend (frontend/.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

---

## Running the System

### Development Environment (3 Terminals)

**Terminal 1 - API Server**
```bash
cd backend
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Message Worker**
```bash
cd backend
.\venv\Scripts\activate
python -m workers.message_processor
```

**Terminal 3 - Frontend Dev Server**
```bash
cd frontend
npm run dev
```

### Health Checks

Verify all systems are operational:

```bash
# API Health
curl http://localhost:8000/health

# Ready Status
curl http://localhost:8000/ready

# Admin Dashboard
curl -H "X-Admin-User: admin" \
     -H "X-Admin-Pass: password" \
     http://localhost:8000/api/admin/dashboard
```

### Common Commands

```bash
# Database migrations
cd backend
alembic upgrade head
alembic downgrade -1

# View migration status
alembic current

# Create new migration
alembic revision --autogenerate -m "Description"

# Run tests
pytest tests/

# Code formatting
black .
isort .

# Type checking
mypy backend/
```

---

## API Documentation

### Public Endpoints

#### Health Check
```
GET /health
GET /ready
```

#### Message Intake

**Web Form**
```
POST /api/intake/web
Content-Type: application/json

{
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "message": "I need help with my account",
  "subject": "Account Issue"
}
```

**Gmail Webhook** (configured via Google Workspace settings)
```
POST /api/integrations/gmail/webhook
```

**WhatsApp Webhook** (via Twilio)
```
POST /api/integrations/whatsapp/webhook
```

### Protected Admin Endpoints

All admin endpoints require authentication headers:
```
X-Admin-User: admin_username
X-Admin-Pass: admin_password
```

#### Dashboard Data
```
GET /api/admin/dashboard?hours=24&limit=50

Response:
{
  "kpis": {
    "total_tickets": 142,
    "open_tickets": 18,
    "total_messages": 486,
    "escalation_rate": 0.12,
    "avg_sentiment_score": 0.68
  },
  "sentiment_distribution": {
    "positive": 234,
    "neutral": 145,
    "negative": 107
  },
  "channel_status": [
    {
      "channel": "web",
      "message_count": 234,
      "ticket_count": 42,
      "escalation_count": 5
    }
  ],
  "recent_logs": [...]
}
```

#### Analytics
```
GET /api/admin/dashboard/analytics?hours=168&bucket_hours=1

Response:
{
  "timeseries": [
    {
      "timestamp": "2026-04-09T12:00:00Z",
      "messages_count": 45,
      "escalations_count": 3
    }
  ]
}
```

#### Activity Feed
```
GET /api/admin/dashboard/activity?hours=24&limit=100&channel=web&sender_type=customer&sentiment=negative

Response:
{
  "activities": [
    {
      "id": "uuid",
      "timestamp": "2026-04-09T12:30:00Z",
      "customer_id": "cust_123",
      "conversation_id": "conv_456",
      "channel": "web",
      "sender_type": "customer",
      "content": "This product is broken!",
      "sentiment_score": -0.92,
      "sentiment_label": "negative"
    }
  ]
}
```

#### Daily Summary Report
```
GET /api/reports/daily-summary?days=7

Response:
{
  "daily_metrics": [
    {
      "date": "2026-04-09",
      "ticket_count": 42,
      "message_count": 156,
      "escalation_count": 8
    }
  ]
}
```

---

## Admin Dashboard

### Features

**Dashboard URL:** http://localhost:3000/admin

The admin dashboard provides comprehensive visibility into system operations:

#### 1. Executive KPIs (Real-Time)
- **Total Tickets** - Cumulative support tickets
- **Open Tickets** - Active unresolved issues
- **Total Messages** - All customer communications
- **Message Escalation Rate** - Percentage requiring escalation
- **Sentiment Score** - Average sentiment (-1 to +1)
- **System Health** - Dashboard data freshness indicator

#### 2. Sentiment Analysis
- **Positive Messages** - Count and percentage
- **Neutral Messages** - Count and percentage
- **Negative Messages** - Count and percentage
- **Average Sentiment** - Weighted score across all messages

#### 3. Activity Timeline
- **Chronological Message Feed** - All messages with metadata
- **Filtering Options:**
  - By channel (web, email, whatsapp)
  - By sender (customer, agent, system)
  - By sentiment (positive, neutral, negative)
- **Message Details:**
  - Customer ID and name
  - Conversation status
  - Sentiment classification
  - Response metadata (if applicable)

#### 4. Negative Sentiment Watchlist
- Recent negative messages (last 8)
- Sorted by recency
- Quick escalation actions available

#### 5. Channel Performance
- Per-channel message volume
- Per-channel ticket creation rate
- Per-channel response time

#### 6. Status Logs
- System events chronologically
- Error tracking
- Processing status

### Authentication

**Login Process:**
1. Visit http://localhost:3000/admin
2. Redirected to login page (/admin/login)
3. Enter credentials (from ADMIN_USERNAME / ADMIN_PASSWORD in .env)
4. Session stored in browser sessionStorage
5. Cookie gate set (crm_admin_gate=1)
6. Dashboard loads with KPI data

---

## Agent Architecture

### Autonomous Decision Loop

The agent orchestrator (`backend/app/agent/core.py`) implements a fully autonomous decision-making pipeline:

1. **Message Ingestion** - Kafka consumer passes customer message to agent
2. **Context Loading** - Agent retrieves customer history and company context
3. **Intent Analysis** - Gemini 2.5 Flash analyzes customer intent semantically
4. **Knowledge Search** - Vector search across KB for relevant documentation
5. **Tool Selection** - Agent decides which tools to call based on intent:
   - `search_knowledge_base` - For FAQ/documentation responses
   - `get_customer_history` - For context-aware personalization
   - `create_ticket` - For issues requiring tracking
   - `escalate_to_human` - For complex/urgent matters
   - `send_response` - For outbound communication
6. **Response Generation** - Gemini generates response adapted to channel
7. **Persistence** - Response and metadata saved to database
8. **Delivery** - Message sent back via appropriate channel (email/SMS/WhatsApp)

### Agent Tools

| Tool | Input Type | Database Table | Purpose |
|------|-----------|-----------------|---------|
| `search_knowledge_base` | Query string + vector embedding | `knowledge_base` | Semantic search across corporate docs |
| `get_customer_history` | Customer ID | `messages`, `tickets` | Retrieve conversation context |
| `create_ticket` | Issue title, description, severity | `tickets` | Create support ticket for tracking |
| `escalate_to_human` | Reason, priority level | `tickets` | Flag conversation for human review |
| `send_response` | Response text, channel | `messages` | Persist agent response to database |

---

## Development

### Project Structure

```
CRM-Digital-FTE/
├── backend/                      # Python FastAPI backend
│   ├── app/
│   │   ├── agent/               # OpenAI Agents SDK agent orchestrator
│   │   │   ├── core.py          # Main agent decision loop
│   │   │   └── deps.py          # Dependency injection context
│   │   └── main.py              # FastAPI app initializer
│   ├── api/
│   │   ├── main.py              # API router aggregator
│   │   ├── routes.py            # Public intake routes
│   │   ├── schemas.py           # Pydantic request/response models
│   │   └── routers/
│   │       ├── health.py        # Health check endpoints
│   │       ├── intake.py        # Intake channel routers
│   │       ├── admin.py         # Protected admin endpoints
│   │       └── gmail_routes.py  # Gmail webhook handler
│   ├── database/
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── queries/             # Reusable query modules
│   │   │   ├── dashboard.py     # Admin KPI queries
│   │   │   ├── reporting.py     # Report generation queries
│   │   │   └── sentiment.py     # Sentiment analysis queries
│   │   └── migrations/          # Alembic DB schema versions
│   ├── workers/                 # Async message processors
│   │   ├── kafka.py             # Kafka consumer wrapper
│   │   └── message_processor.py # Main event loop
│   ├── integrations/            # External API integrations
│   │   └── gmail_api.py
│   ├── channels/
│   │   ├── web_form_handler.py  # Web intake processing
│   │   ├── gmail_handler.py
│   │   └── whatsapp_handler.py
│   ├── context/                 # Prompt engineering & brand files
│   ├── alembic/                 # Database migrations
│   ├── main.py                  # Entry point
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── env.example
├── frontend/                     # Next.js 16 frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Web intake form
│   │   │   ├── admin/
│   │   │   │   ├── page.tsx     # Admin dashboard
│   │   │   │   ├── login/       # Admin login page
│   │   │   │   └── layout.tsx   # Admin layout
│   │   │   └── layout.tsx
│   │   ├── lib/
│   │   │   └── admin-auth.ts    # Session/cookie helpers
│   │   └── components/          # Reusable React components
│   ├── src/proxy.ts             # Next.js 16 route middleware
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── next.config.ts
├── docker-compose.yml           # Local Kafka + ZooKeeper
├── k8s/                         # Kubernetes manifests
├── specs/                       # Technical documentation
├── guide.md                     # Local testing guide
├── AGENTS.md                    # Agent architecture docs
└── README.md                    # This file
```

### Code Standards

- **Python:** PEP 8, async/await for I/O
- **TypeScript:** Strict mode, ESLint enforcement
- **Naming:** Snake case (Python), camelCase (TypeScript)
- **Documentation:** Docstrings on all public functions
- **Testing:** Unit tests in `tests/` with pytest

### Running Tests

```bash
cd backend
pytest tests/ -v
pytest tests/test_agent.py -vv  # Specific test file
pytest tests/ --cov=.           # With coverage
```

---

## Deployment

### Local Production Build

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm run build
npm run start
```

### Docker Deployment

```bash
# Build images
docker-compose build

# Run production
docker-compose -f docker-compose.yml up -d
```

### Kubernetes Deployment

Helm charts and Kubernetes manifests are provided in `k8s/`:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
# ... apply other manifests
```

### Cloud Deployment

**Supported Platforms:**
- AWS ECS/EKS
- Google Cloud Run
- Azure Container Instances
- Heroku
- Railway
- Render

**Database Hosting:**
- Neon (PostgreSQL serverless) - Recommended
- AWS RDS
- Azure Database for PostgreSQL
- Google Cloud SQL
- Self-hosted PostgreSQL

**Configuration for Cloud:**

Update `backend/.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@neon-host/dbname
KAFKA_BOOTSTRAP_SERVERS=cloud-kafka-broker:29092
# ... other vars
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# API availability
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/ready

# Admin dashboard responsiveness
curl -H "X-Admin-User: admin" \
     -H "X-Admin-Pass: password" \
     http://localhost:8000/api/admin/dashboard
```

### Logs

```bash
# Backend logs
tail -f backend/logs/api.log

# Worker logs
tail -f backend/logs/worker.log

# Docker logs
docker-compose logs -f backend
docker-compose logs -f worker
```

### Common Issues

**Issue:** "Connection refused" on Kafka
- **Solution:** `docker-compose up -d` to start Kafka/ZooKeeper

**Issue:** "Database URL invalid"
- **Solution:** Verify DATABASE_URL in backend/.env with correct format

**Issue:** Admin dashboard returns 401
- **Solution:** Check ADMIN_USERNAME and ADMIN_PASSWORD in .env

**Issue:** Agent not responding to messages
- **Solution:** Verify GEMINI_API_KEY is set; check worker logs

---

## Contributing

### Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test locally
3. Run tests: `pytest tests/`
4. Format code: `black . && isort .`
5. Type check: `mypy backend/`
6. Commit with descriptive message
7. Push and create pull request

### Pull Request Guidelines

- Clear description of changes
- Link to related issues
- Screenshots for UI changes
- All tests passing
- Type checking clean

---

## License

Proprietary - CRM Digital FTE Hackathon Project

---

## Support

For issues, questions, or contributions:
1. Check [guide.md](./guide.md) for local testing instructions
2. Review [AGENTS.md](./AGENTS.md) for architecture details
3. View [specs/](./specs/) folder for technical specifications

**Key Documentation Files:**
- [AGENTS.md](./AGENTS.md) - Agent architecture and tools
- [guide.md](./guide.md) - Local testing and deployment guide
- [specs/customer-success-fte-spec.md](./specs/customer-success-fte-spec.md) - Complete feature specification
- [specs/deployment-guide-free.md](./specs/deployment-guide-free.md) - Deployment instructions

---

**Last Updated:** April 2026 | **Status:** Production Ready

#### Migrate the Relational Database 
```sh
alembic upgrade head
```

#### Launch FastAPI API Service
```sh
uvicorn main:app --reload --port 8000
```

#### Launch the Dedicated Background Worker
```sh
python -m workers.message_processor
```

### 3. Frontend Implementation
Open up a third window for the client React side:
```sh
cd frontend
npm run dev
```

Visit [`http://localhost:3000`](http://localhost:3000) using your local browser.

## Tech Stack
- Frontend: `Next.js`, `TailwindCSS`
- API Backend: `FastAPI`, `Uvicorn`
- State Control: `SQLAlchemy (async)`, `Alembic`, `NeonDB (Postgres)`
- Event Orchestrators: `Confluent Kafka` (Python bindings)
- Digital FTE Engine: `OpenAI Agents SDK`, `Gemini`

## Project Guides
- Local end-to-end validation: `specs/local-testing-guide.md`
- Free deployment (Render/Vercel/Neon/Confluent): `specs/deployment-guide-free.md`
- Skills definitions used by the agent: `specs/skills-manifest.md`
