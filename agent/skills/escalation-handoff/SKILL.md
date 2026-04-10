---
name: escalation-handoff
description: "Use when a conversation must move between AI and human support. Handles escalation ownership, pause-agent behavior, and handoff-back instructions. Triggers: escalate, handoff to human, handoff to agent, human-owned ticket, escalation governance."
---

# Escalation Handoff

## Purpose
Enforce safe and predictable human-in-the-loop workflow:
- Escalated conversations are human-owned.
- Agent should not continue automated replies while escalated.
- Human can hand off back with explicit instruction.

## Escalate Criteria
- Explicit customer request for a human.
- Legal/compliance threats or account security concerns.
- Repeated failed attempts to solve.
- High-impact outage or payment-critical blocker.

## Workflow
1. Confirm escalation trigger and summarize why escalation is needed.
2. Mark conversation/ticket as escalated.
3. Send clear acknowledgment to customer with expected next step.
4. While escalated, store inbound messages but skip autonomous agent run.
5. On handoff-back, inject `HUMAN_TO_AGENT` instruction into next turn.
6. Resume agent ownership only after explicit admin handoff.

## Communication Rules
- Never imply issue is resolved during escalation.
- Use calm, specific language with ownership and timeline framing.
- Preserve critical context so the customer does not repeat details.

## Output Contract
- `escalation_needed`: true | false
- `escalation_reason`: short text
- `customer_message`: acknowledgment text
- `handoff_note`: structured internal note for human/agent transition
