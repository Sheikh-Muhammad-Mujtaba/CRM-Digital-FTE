# Digital FTE Factory: Customer Success Spec

## 1. Persona & Tone Alignment
- **Name**: Digital Support FTE
- **Primary Function**: Triaging tier-1 technical support requests and logging required CRM workflow objects automatically.
- **Tone Profile**: 
  - *Email/Web*: Highly professional, empathetic, formatted comprehensively.
  - *WhatsApp/Twilio*: Direct, concise, informal, fast resolution orientation.

## 2. Trigger Events & Kafka Pathways
- `gmail-pubsub` -> Routes directly to `fte.inbound` topic.
- `twilio-webhook` -> Pushes payload to `/api/intake/whatsapp`.
- `web-support` -> Pushes NextJS form payload to `/api/intake/web`.
- Resulting pipeline evaluates context via OpenAI API interface configured explicitly toward `Gemini-2.5-flash`.

## 3. Tool Utilization (MCP / Function Calls)
1. **Search Context (`search_knowledge_base`)**: Primary mandate, executed prior to raw LLM speculation. Operates using standard Euclidean/Cosine pgvector evaluations.
2. **Retrieve Context (`get_customer_history`)**: Mandatory execution to avoid duplicate resolution paths based on known customer identity strings.
3. **Escalation Path (`create_ticket` & `escalate_to_human`)**: Dual action triggered simultaneously when restrictions map back an unauthorized action demand (e.g., billing alterations).
4. **Resolution Response (`send_response`)**: Writes to postgres logging and signals consumer loops to broadcast actual dispatch outputs globally.

## 4. Success Thresholds
- Sub-400ms time-to-first-byte (TTFB) inside Kafka routing queues.
- 99.9% uptime validation tracked via Datadog / Prometheus endpoints inside Kubernetes clusters.
- Zero schema validation issues leveraging strict Pydantic parsing.
