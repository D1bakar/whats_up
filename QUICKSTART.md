# Quickstart — run the backend and connect a real WhatsApp phone

This quickstart shows the minimal safe steps to run the backend locally, expose it to the internet with ngrok, register the Meta (WhatsApp Cloud) webhook, and test inbound/outbound messaging.

Security first
- If you exposed any tokens publicly, rotate/revoke them now in the Meta/Facebook Developer Console. Do not paste secrets publicly.
- This quickstart does not include any secrets — put tokens and secrets into a local .env file only.

1) Prepare .env (locally)

Copy the repository template and edit locally (do NOT commit secrets):

```bash
cp .env.example .env
# Edit .env and fill these values locally (examples):
# WHATSAPPAPP_PROVIDER=meta
# META_WHATSAPP_ACCESS_TOKEN=<YOUR_NEW_META_ACCESS_TOKEN>
# META_WHATSAPP_PHONE_NUMBER_ID=<PHONE_NUMBER_ID>
# WHATSAPPAPP_VERIFY_TOKEN=<YOUR_VERIFY_TOKEN>
# WHATSAPPAPP_APP_SECRET=<YOUR_APP_SECRET>
# DATABASE_URL, REDIS_URL, AI keys, etc. — see .env.example
```

2) Start the services

Option A — Start the full dev stack (recommended for integration tests):

```bash
docker compose -f docker/docker-compose.dev.yml up --build
```

Option B — Run only the backend (faster iteration):

```bash
cd backend
# install deps per your environment (poetry/pip/requirements)
# example using pip (adjust to your workflow):
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3) Expose the backend to the internet (ngrok)

For Meta webhooks the callback URL must be publicly reachable via HTTPS. For local testing use ngrok:

```bash
ngrok http 8000
```

Copy the HTTPS URL ngrok prints (e.g. `https://abcd1234.ngrok.io`).

4) Register the webhook in Meta (Facebook) Developer Console

- Product: WhatsApp → Webhooks
- Callback URL: `https://<your-public-host>/webhooks/whatsapp` (for example `https://abcd1234.ngrok.io/webhooks/whatsapp`)
- Verify Token: the same string as `WHATSAPPAPP_VERIFY_TOKEN` in your local `.env`
- Subscribe to events: `messages`, `messages_deliveries`, `messages_reads`, etc.

Meta will perform a GET handshake (hub.mode=subscribe & hub.challenge & hub.verify_token). The app implements verification and will return the `hub.challenge` when the token matches.

5) Verify webhook (quick test)

From any machine run:

```bash
curl "https://<your-public-host>/webhooks/whatsapp?hub.mode=subscribe&hub.challenge=12345&hub.verify_token=<YOUR_VERIFY_TOKEN>"
```

Expected response: `12345` (HTTP 200) if the verify token matches.

6) Test inbound messages

- Send a message from your phone to the WhatsApp Business number configured in Meta (the `META_WHATSAPP_PHONE_NUMBER_ID` belongs to that number). The backend should receive webhook events at `/webhooks/whatsapp` and log them.
- Check backend logs (docker compose logs backend or your uvicorn output) for webhook receipts.

7) Test outbound messages (Graph API)

Use the Meta Graph API to send a test message (replace placeholders):

```bash
curl -X POST "https://graph.facebook.com/v17.0/<PHONE_NUMBER_ID>/messages" \
  -H "Authorization: Bearer <META_WHATSAPP_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "<RECIPIENT_PHONE_IN_E164>",
    "type": "text",
    "text": { "body": "Hello from test" }
  }'
```

If successful the response contains message id(s). If you get 4xx errors, rotate/regenerate the access token and ensure the app has permissions and the phone number is approved.

8) Simulate signed webhook POSTs locally (advanced)

Meta signs webhook POSTs with `X-Hub-Signature-256: sha256=<hex-hmac>` where HMAC = HMAC_SHA256(APP_SECRET, body).

Example to simulate a signed POST locally (replace `APP_SECRET` and `payload`):

```bash
payload='{"object":"whatsapp_business_account","entry":[]}'
APP_SECRET='<YOUR_APP_SECRET>'
# compute signature (requires openssl)
sig_hex=$(echo -n "$payload" | openssl dgst -sha256 -hmac "$APP_SECRET" | sed 's/^.* //')
sig_header="sha256=$sig_hex"

curl -v -X POST "https://<your-public-host>/webhooks/whatsapp" \
  -H "X-Hub-Signature-256: $sig_header" \
  -H "Content-Type: application/json" \
  -d "$payload"
```

9) Rotate/revoke tokens if they were exposed

If you exposed an access token in a public channel, revoke/regenerate it immediately in the Meta Developer Console. Treat tokens as secrets.

10) Want automation?

This repo includes a scripts/ directory and a Next.js frontend. If you want, add a helper script to start ngrok and print the callback URL — a companion script is provided in `scripts/start-ngrok.sh` on the `quickstart/ngrok-helper` branch.

If you want a PR with additional helpers (Makefile, GitHub Actions, CI-safe quickstart), reply to this PR or open an issue with desired changes.
