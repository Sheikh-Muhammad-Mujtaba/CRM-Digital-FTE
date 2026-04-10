---
name: admin-data-ops
description: "Use when performing admin-side support data operations: status edits, filtered conversation logs, and bulk deletion of full conversation graphs (messages, tickets, conversation row). Triggers: admin manage data, bulk delete, ticket status patch, conversation cleanup."
---

# Admin Data Ops

## Purpose
Provide a safe playbook for manual admin actions in support operations.

## Supported Operations
- Update ticket status manually.
- Filter conversation logs for review.
- Bulk delete selected conversations and linked data.

## Destructive Action Policy
For each selected conversation, delete the full graph:
1. Linked messages.
2. Linked tickets.
3. Conversation row.

Never perform partial deletes that leave orphan records.

## Workflow
1. Validate admin intent and scope (single vs bulk).
2. Preview affected records using filters where possible.
3. Execute operation atomically per conversation.
4. Return per-item success/failure summary.
5. Refresh UI state so buttons and selections reset correctly.

## Safety Checks
- Require explicit selection for bulk delete.
- Log operation outcomes for auditability.
- Fail fast on invalid IDs with clear error detail.

## Output Contract
- `operation`: status_update | bulk_delete | single_delete
- `requested_count`: number
- `processed_count`: number
- `failed_items`: list
- `summary`: short human-readable result
