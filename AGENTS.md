# Autonomous CRM Digital FTE - Agent Architecture

This document completely outlines the AI Agent architecture (Digital FTE) that serves as the centerpiece of this autonomous CRM system.

## 1. Core Framework Foundation
The entire decision-making loop is implemented via the **Pydantic-AI** framework combined identically with the generic **Gemini-2.5-Flash** model. We elected this pathway because `pydantic-ai` offers fully-typed function calling structures via its dependency injection system, satisfying the requirements from the hackathon document while scaling significantly better than raw HTTP post implementations.

The orchestration root resides primarily at: `/backend/app/agent/core.py`.

## 2. Dependency Context Mapping
Every time a Kafka event hits the consumer pool, it constructs the current application runtime and parses the following payload via the Dataclass `AgentDependencies` located at `/backend/app/agent/deps.py`:

```python
@dataclass
class AgentDependencies:
    session: AsyncSession
    customer_id: str
    channel: str
    conversation_id: str
```
By utilizing this dependency layer:
- The Gemini Agent can execute backend Postgres operations universally across any function call **without** globally importing database credentials or risking connection leaks! 
- The `channel` context empowers prompt engineering heuristics to adjust the response style based heavily on if it was submitted via `whatsapp` vs `web`.

## 3. Dynamic Tools (Capabilities)
Our Digital FTE is uniquely equipped with 5 robust Python tools mapping directly to production database tables. Each tool enforces strict typings via Pydantic `BaseModel` schemas, fully satisfying expectations for OpenAI Agent SDK `@function_tool` structural precision.

### A. `search_knowledge_base`
**Logic Profile:** Takes a direct semantic NLP user string query. This tool operates against the Postgres `knowledge_base` utilizing natively integrated `pgvector` indexing calculations parsing cosine distances to locate resolutions explicitly listed in the corporate DB. If documentation exists regarding the customer's query, the AI analyzes it before sending final responses.

### B. `get_customer_history`
**Logic Profile:** Reaches directly into the SQL layer leveraging the `customer_id` parameter to pull down historical data strings relating strictly to previous resolved / open support `Tickets`. If it spots redundant questions, the AI will use this history explicitly to adjust recommendations.

### C. `create_ticket`
**Logic Profile:** In the event an inquiry demands a physical replacement, accounting change, or hits a roadblock that the Gemini model is restricted from altering, this tool is forcefully executed. It creates a brand-new trackable entity in the `tickets` table and updates its workflow status to `open`.

### D. `escalate_to_human`
**Logic Profile:** Operates concurrently (often combined natively via multi-tool execution capabilities within Gemini 2.5 Flash) with the `create_ticket` component. Explicitly stops automated responses, flagging the overall conversation ID layer to a dedicated UI status so actual Customer Success Members can natively override the AI loop context.

### E. `send_response`
**Logic Profile:** Bypasses manual string-returning in the system console. It explicitly writes the AI's final conclusion directly to the `messages` table assigning a `sender_type="agent"`. This allows external microservices to track response logs via webhook queues out securely to Gmail or Twilio WhatsApp channels seamlessly across boundaries.

## 4. Prompt Engineering Directives
The base system behavior dictates adherence exactly matching these instructions via `system_prompt`:
1. Search the Knowledge Base for strict corporate context before hallucinating answers.
2. Analyze ticket behaviors.
3. Automatically generate Escalation triggers if restricted contexts map back into your reasoning logic chain natively.
4. Adapt tone purely based on the channel context provided to you (shorter outputs for WhatsApp and SMS components, extremely professional structure for native E-mail or explicit Web Form tickets).
