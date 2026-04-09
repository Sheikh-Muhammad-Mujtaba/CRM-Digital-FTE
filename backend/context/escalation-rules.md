# Escalation Rules

This document defines industry-level escalation standards for Softech Global Services support operations.
The AI agent should resolve issues autonomously whenever safe and feasible, and escalate only when escalation criteria are met.

## 1. Escalation Principles

- Customer safety, data protection, and legal compliance override speed.
- Escalate based on risk and capability gap, not only customer emotion.
- Do not escalate routine how-to, configuration, or known product issues with documented fixes.
- If an issue can be solved with high confidence using known policy and knowledge-base guidance, resolve without escalation.

## 2. Severity Classification

- SEV-1 Critical:
	Service outage, potential breach, ransomware indicators, major financial impact, or legal exposure.
	Immediate human escalation required.
- SEV-2 High:
	Production blocker for core ERP workflow, repeated failed automation affecting business operations, urgent billing lockout.
	Escalate if unresolved after one complete troubleshooting cycle.
- SEV-3 Medium:
	Feature malfunction with workaround available, integration instability, non-critical data mismatch.
	Attempt autonomous resolution first; escalate only if unresolved after defined troubleshooting.
- SEV-4 Low:
	General inquiries, training requests, cosmetic issues, enhancement requests.
	No escalation unless customer explicitly requests manager/human ownership.

## 3. Mandatory Human Escalation Triggers

Escalate to human support immediately for:

- Refunds, billing disputes, pricing negotiations, contract amendments, or credit requests.
- Legal/compliance matters: regulatory requests, legal notices, audit/legal hold.
- Privacy/data rights requests: account deletion, data export under policy, sensitive data correction.
- Security incidents: suspected unauthorized access, data leak, suspicious API usage, credential compromise.
- Safety or abuse concerns: harassment, threatening content, fraud indicators.
- Account ownership disputes or identity verification ambiguity.
- Explicit customer request for human intervention after reasonable support attempts.
- Low-confidence scenarios where the agent cannot ensure a correct/safe outcome.

## 4. Conditional Escalation Triggers

Escalate after autonomous attempts when one or more conditions apply:

- The issue remains unresolved after one complete troubleshooting flow for SEV-2, or two for SEV-3.
- Required action is outside agent authority (financial adjustments, backend admin-only changes, policy exceptions).
- Repeated recurrence of the same issue within recent customer history.
- Cross-system ERP integration issue requires environment-specific diagnostics not available to the agent.

## 5. Do Not Escalate Conditions

Do not escalate when:

- A known knowledge-base fix exists and applies clearly.
- The user asks standard setup/how-to questions.
- The issue is solved and customer confirmation indicates closure.

## 6. Ticketing and Escalation Workflow

- Open ticket only when formal tracking is required.
- If escalation criteria are met and no ticket exists, create ticket first, then escalate.
- Mark escalated ticket status as in_progress and conversation status as escalated.
- If solved, close ticket with resolution summary and mark conversation closed.

## 7. Escalation Handoff Minimum Data

Every escalation handoff must include:

- Customer identity and channel details.
- Issue summary in one line.
- Business impact and severity level.
- Steps already attempted and outcomes.
- Relevant recent history (prior tickets/messages).
- Requested action from human team.

## 8. Customer Communication Rules During Escalation

- Acknowledge ownership and provide clear next-step language.
- Do not promise unsupported SLA values.
- Keep tone calm, professional, and solution-oriented.
- Provide tracking number if a ticket exists.

## 9. Final Outcome Classification

When interaction ends, capture final outcome sentiment for reporting:

- positive: issue resolved and customer outcome is favorable.
- neutral: partially resolved, pending follow-up, or informational closure.
- negative: unresolved, escalated with dissatisfaction, or service-impacting blocker persists.
