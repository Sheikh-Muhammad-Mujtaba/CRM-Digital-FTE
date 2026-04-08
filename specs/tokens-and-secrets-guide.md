# Gmail — minimal env variables (OAuth + Pub/Sub)

All Gmail access (read inbox, mark read, send replies) uses **one OAuth client** and **one refresh token**.

| Variable | Source |
|----------|--------|
| `GMAIL_CLIENT_ID` | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID |
| `GMAIL_CLIENT_SECRET` | Same OAuth client |
| `GMAIL_REFRESH_TOKEN` | One-time OAuth consent flow (scopes must include `gmail.readonly`, `gmail.modify`, `gmail.send`) |
| `GMAIL_PUBSUB_TOPIC` | Full Pub/Sub topic name for `users.watch`, e.g. `projects/PROJECT_ID/topics/TOPIC_NAME` |
| `GMAIL_WEBHOOK_SECRET` *(optional but recommended)* | A random string you choose to protect the webhook + watch endpoints |

**Inbound (recommended):**\n\n- Create a Pub/Sub topic\n- Grant Publisher to `gmail-api-push@system.gserviceaccount.com`\n- Create a push subscription to:\n  `POST /api/webhooks/gmail/pubsub?token=GMAIL_WEBHOOK_SECRET` (token optional)\n- Call `POST /api/gmail/watch?token=GMAIL_WEBHOOK_SECRET` to enable Gmail → Pub/Sub\n+\nWhen Pub/Sub pushes, the app pulls unread mail via the Gmail API and enqueues to Kafka.\n+\n**Inbound (fallback):** call `POST /api/gmail/sync` manually if you don't want Pub/Sub.

**Outbound:** web/email channel replies are sent with `users.messages.send` using the same credentials.

**WhatsApp:** `TWILIO_*` env vars (unchanged).
