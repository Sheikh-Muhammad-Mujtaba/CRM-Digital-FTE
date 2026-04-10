---
name: ticket-lifecycle
description: "Use when creating, reusing, updating, or closing support tickets across channels. Enforces one active ticket per customer issue and channel-specific tracking IDs (WEB/WHA/EML). Triggers: create ticket, ticket status, close ticket, tracking ID, reopen logic."
---

# Ticket Lifecycle

## Purpose
Standardize service ticket behavior from intake to resolution.

## Core Policy
- Reuse existing active ticket when issue context matches.
- Keep at most one active service ticket per customer issue.
- Generate/maintain channel tracking IDs:
  - `WEB-xxxx-xxxx`
  - `WHA-xxxx-xxxx`
  - `EML-xxxx-xxxx`
- When issue is solved, set ticket status to `closed`.

## Workflow
1. Check for active ticket for customer and current issue context.
2. Reuse ticket if same issue; otherwise create a new one.
3. Attach tracking ID in channel format.
4. Persist meaningful status transitions (`open`, `in_progress`, `escalated`, `closed`).
5. On solved confirmation, close ticket and send final concise resolution note.

## Guardrails
- Do not create duplicate active tickets for repeated messages.
- Do not close unresolved escalated tickets.
- Keep internal status changes aligned with customer-visible messaging.

## Output Contract
- `ticket_action`: reused | created | updated | closed
- `ticket_id`: internal id
- `tracking_id`: channel-formatted id
- `status`: current ticket status
- `customer_message`: optional reply text
