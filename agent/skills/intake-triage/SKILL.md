---
name: intake-triage
description: "Use when triaging inbound support messages from web, WhatsApp, or Gmail; classify support vs non-support; choose whether to ignore, answer, create a ticket, or escalate. Triggers: triage, classify email, support intent, intake filtering, non-support suppression."
---

# Intake Triage

## Purpose
Apply consistent intake policy before agent response or ticket actions:
- Process only service-related support requests.
- Ignore promotional/system/non-support emails.
- Minimize unnecessary tool/API calls.

## Inputs to Gather
- Channel: web, whatsapp, or email.
- Customer identity: id, email/phone, known history if available.
- Message text and recent thread context.
- Signals of urgency, frustration, billing/access outage, or legal/security risk.

## Workflow
1. Confirm whether the message is support-related.
2. If non-support (marketing/newsletter/system/no-reply), do not open ticket and do not trigger reply.
3. If support-related and clear answer is known, respond directly and briefly.
4. If support-related but uncertain, retrieve only minimal required knowledge/history.
5. If customer asks for human or high-risk pattern appears, prepare escalation path.
6. Keep output channel-appropriate and action-oriented.

## Decision Rules
- Prefer direct answer first when confidence is high.
- Use retrieval tools only when certainty or safety requires it.
- Never create multiple active tickets for the same customer issue.
- For Gmail, enforce strict support-only processing.

## Output Contract
Return a compact decision block:
- `classification`: support | non-support
- `action`: ignore | respond | create_ticket | escalate
- `reason`: one sentence
- `suggested_response`: optional customer-facing reply
