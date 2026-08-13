# WhatsApp / Meta Setup

Guide for connecting this platform to the Meta WhatsApp Cloud API. **By default the project uses `WHATSAPP_PROVIDER=mock` and makes no real API calls.**

## Prerequisites

1. [Meta Developer App](https://developers.facebook.com/) with **WhatsApp** product enabled
2. WhatsApp Business Account (WABA) and a registered phone number
3. System User access token with `whatsapp_business_messaging` permission
4. Public HTTPS webhook URL (use [ngrok](https://ngrok.com/) or Cloudflare Tunnel in development)
5. Webhook field subscriptions: `messages`, `statuses`

## Environment variables

Copy placeholders from `.env.example` into local `.env` — **never commit real values**:

| Variable | Purpose |
|----------|---------|
| `WHATSAPP_PROVIDER` | Set to `meta` for production API |
| `WHATSAPP_VERIFY_TOKEN` | Must match the token configured in Meta webhook settings |
| `WHATSAPP_APP_SECRET` | HMAC signature validation for POST webhooks |
| `META_WHATSAPP_ACCESS_TOKEN` | Graph API bearer token |
| `META_WHATSAPP_PHONE_NUMBER_ID` | Business phone number ID from Meta |
| `META_WHATSAPP_BUSINESS_ACCOUNT_ID` | WABA ID (optional metadata) |
| `META_WHATSAPP_API_VERSION` | Graph API version (default `v21.0`) |

## Webhook URL

Configure in Meta Developer Console:

```
GET/POST https://<your-domain>/webhooks/whatsapp
```

### Verification (GET)

Meta sends `hub.mode`, `hub.verify_token`, and `hub.challenge`. The API returns the challenge when the verify token matches `WHATSAPP_VERIFY_TOKEN`.

### Event delivery (POST)

When `WHATSAPP_APP_SECRET` is set, requests must include a valid `X-Hub-Signature-256` header.

## Local testing without Meta

Use the mock provider (default):

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000

curl -X POST http://localhost:8000/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/whatsapp/text_message.json
```

Run the test suite for full coverage:

```bash
uv run pytest -v
```

## Switching to Meta

1. Set `WHATSAPP_PROVIDER=meta` in `.env`.
2. Provide valid `META_WHATSAPP_ACCESS_TOKEN` and `META_WHATSAPP_PHONE_NUMBER_ID`.
3. Configure webhook URL and verify token in Meta Developer Console.
4. Set `WHATSAPP_APP_SECRET` before exposing the endpoint publicly.
5. Restart the API.

No code changes are required — the provider is selected at runtime.

## References

- [Cloud API overview](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Webhooks setup](https://developers.facebook.com/docs/graph-api/webhooks/getting-started)
- [Send messages](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages)
