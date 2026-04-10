# Autonomous CRM Digital FTE - Agent Architecture

This document describes the current AI Agent architecture and operational rules used by the CRM Digital FTE system.

## 1. Core Stack
- Agent framework: OpenAI Agents SDK
- Model provider: Gemini via OpenAI-compatible endpoint
- Runtime orchestration:
    - API app: `/backend/api/main.py`
    - Worker loop: `/backend/workers/message_processor.py`
    - Agent definition: `/backend/agent/customer_success_agent.py`
    - Prompt construction: `/backend/agent/prompts.py`

## 2. Dependency Injection Contract
Per inbound event, the worker builds `AgentDependencies` from `/backend/agent/deps.py`:

```python
@dataclass
class AgentDependencies:
        session: AsyncSession
        customer_id: str
        channel: str
        conversation_id: str
        customer_email: Optional[str] = None
        customer_phone: Optional[str] = None
        customer_name: Optional[str] = None
```

This contract enables tools to:
- perform DB operations safely through shared async session,
- dispatch outbound messages through channel-specific identity (email/phone),
- adapt tone by channel.

## 3. Inbound Channel Contract
- Web intake: `POST /api/intake/web`
- WhatsApp (Twilio canonical endpoint): `POST /api/intake/twilio`
- Gmail direct intake: `POST /api/intake/gmail`
- Gmail Pub/Sub push: `POST /api/webhooks/gmail/pubsub`

All events are normalized then published to Kafka intake topic for worker processing.

## 4. Tool Capabilities
Tools are defined in `/backend/agent/tools.py`.

1. `search_knowledge_base`
- Semantic retrieval against `knowledge_base` via pgvector + embeddings.
- Uses lightweight embedding cache to reduce repeated API calls.

2. `get_customer_history`
- Pulls linked cross-conversation customer history (tickets + recent messages).

3. `create_ticket`
- Enforces one active service ticket per customer (reuses active ticket when appropriate).
- Returns channel-specific tracking format:
    - `WEB-xxxx-xxxx`
    - `WHA-xxxx-xxxx`
    - `EML-xxxx-xxxx`

4. `escalate_to_human`
- Marks conversation as escalated and records escalation event.
- Escalated conversations are human-owned until handoff back.

5. `send_response`
- Persists final agent response and sentiment marker.
- Closes ticket as `closed` when solved.
- Dispatches outbound reply through channel adapters.

## 5. Human Escalation Governance
- While conversation status is `escalated`, worker stores inbound customer messages but skips agent run.
- Admin can hand off back to agent with instruction via:
    - `POST /api/admin/tickets/{ticket_id}/handoff-to-agent`
- Handoff instruction is injected into the next agent turn as `HUMAN_TO_AGENT:` context.

## 6. Prompt and API Call Policy
Prompt rules in `/backend/agent/prompts.py` enforce:
- direct-answer-first behavior when confidence is high,
- minimal tool call strategy to reduce rate-limit pressure,
- retrieval tools only when needed for certainty or safety,
- strict email policy (non-support/promotional/service-platform emails ignored by ingestion layer).

## 7. Admin Data Management
Admin operations include:
- ticket status updates,
- conversation log filtering,
- bulk deletion of full conversation graph (messages + linked tickets + conversation row).

Relevant route file: `/backend/api/routers/admin.py`.
