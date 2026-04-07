---
description: Customer Success Digital FTE Skills Manifest
---

# Customer Success Digital FTE – Skills Manifest

This document outlines the specialized skills created for the autonomous CRM agent (Digital FTE) using the OpenAI Agents SDK environment as defined in Hackathon 5.

## Installed Skills

### 1. `search_knowledge_base`
**Description:** Semantic vector search across the corporate knowledge base.
**Action:** Connects to `pgvector` to identify and fetch company-approved resolution guidelines, manuals, and FAQs using cosine distance metrics. This ensures the Digital FTE does not hallucinate answers outside constraints.

### 2. `get_customer_history`
**Description:** Historical Context Resolver
**Action:** Lookups earlier open or closed tickets connected directly to the user's `customer_id`. It's used by the AI to detect ongoing issues, duplicate cases, and apply historical empathy to the interaction tone.

### 3. `create_ticket`
**Description:** System-of-Record (CRM) Mutation
**Action:** Logs a concrete `Ticket` entity into the postgres system for items the FTE is unauthorized to instantly resolve, explicitly requiring a trace.

### 4. `escalate_to_human`
**Description:** Manual Override Escalation
**Action:** Fires an interrupt forcing a status switch. Triggers an alert in the external queue, marking the `conversation_id` as necessitating manual Customer Success representative intervention. Halts standard AI loop processing.

### 5. `send_response`
**Description:** External Channel Dispatch Payload
**Action:** Prepares the correctly toned response directly into the `messages` log where the Kafka `fte.outbound` producer/consumer architecture natively routes it outward to Web, Twilio, or Gmail safely.

## Technical Configuration
The skills are fully type-enforced utilizing `Pydantic` `BaseModel` injection parameters. They are exposed simultaneously to the host `Agent` and via an independent **MCP Server** (`mcp_server.py`) for external auditing and modular compatibility tests.
