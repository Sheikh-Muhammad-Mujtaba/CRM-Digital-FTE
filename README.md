# CRM Digital FTE Factory

## Overview
The **CRM Digital FTE** (Full-Time Equivalent) system is an autonomous customer success platform modeled around Gemini 2.5 Flash and Pydantic-AI. It ingests messages from multiple channels (Web Forms, Twilio WhatsApp, Gmail) to process and automatically respond to user customer queries exactly like a human agent would, all while acting on data retrieved natively from a custom PostgreSQL Neon database schema.

## Features
- **Multi-channel Streaming Intake:** Event-driven Kafka stream decoupling data ingestion components from the actual AI processing logic limit.
- **SQLAlchemy 2.0 with Neon Postgres:** Using native, async `pgvector` models to index interactions, log tracking metrics on created support tickets, and build a unified Customer perspective.
- **Next.js Support Form:** A beautifully crafted, responsive, glassmorphism-styled UI powered by Tailwind CSS for high-performance frontend data intake.
- **Gemini Autonomous Routing:** End-to-end integration mapping logic onto Python tools, autonomously parsing intent, fetching prior ticket workflows natively via injected Database sessions, all seamlessly done without human intervention.

## System Architecture
The system consists of three massive architectural silos:
1. **Frontend App (`/frontend`)**
   - Built on Next.js App Router.
   - Pushes message payloads down synchronously into the Python API ingestion points.
2. **REST API Ingestion (`/backend/app/api`)**
   - FastAPI routers standardized to accept incoming multi-channel traffic mapping to localized Kafka Topics (`crm_intake`).
3. **Kafka Streaming Component (`/backend/app/streaming`)**
   - Robust persistent Kafka Consumer loop taking queued tasks without blocking horizontal API ingestion loads.
4. **Agent Orchestration Center (`/backend/app/agent`)**
   - `pydantic-ai` natively executing state-of-the-art zero-shot task completions against Gemini models while referencing dependencies parsed securely inside Postgres.

## Setup Instructions
### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (for local Apache Kafka simulation)
- A provisioned Neon Postgres Database.

### 1. Booting Up Kafka
Inside the root repository, spin up ZooKeeper & Kafka via Docker Compose by executing:
```sh
docker-compose up -d
```

### 2. Backend Bootstrapping
Activate the Python virtual environment under the directory `/backend` via:
```sh
cd backend
python -m venv venv
venv\Scripts\activate.bat   # Windows
# source venv/bin/activate  # macOS / Linux
pip install -r requirements_placeholder.txt  # As covered in setup.bat
```

> Ensure your `.env` is loaded cleanly before starting services!

#### Migrate the Relational Database 
```sh
alembic upgrade head
```

#### Launch External Fast-API Webhook Hub
```sh
uvicorn app.main:app --reload --port 8000
```

#### Launch the Dedicated Background Agent Processing Module
(Requires an active instance of backend services). Open a secondary terminal.
```sh
python -m app.streaming.consumer
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
- Digital FTE Engine: `Pydantic-AI`, `Gemini`

## Project Guides
- Local end-to-end validation: `specs/local-testing-guide.md`
- Free deployment (Render/Vercel/Neon/Confluent): `specs/deployment-guide-free.md`
- Skills definitions used by the agent: `specs/skills-manifest.md`
