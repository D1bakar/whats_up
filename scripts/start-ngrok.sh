#!/usr/bin/env bash
set -euo pipefail

# scripts/start-ngrok.sh
# Run ngrok, wait for the tunnel and print the public https URL with instructions.

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok is not installed. Download from https://ngrok.com/ and install it." >&2
  exit 1
fi

# Start ngrok in background
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "Started ngrok (PID=$NGROK_PID), waiting for tunnel..."

# Wait for ngrok API to appear
for i in {1..30}; do
  if curl --silent --fail http://127.0.0.1:4040/api/tunnels >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Try to extract the HTTPS public URL (prefer jq; fallback to python)
URL=""
if command -v jq >/dev/null 2>&1; then
  URL=$(curl --silent http://127.0.0.1:4040/api/tunnels | jq -r '.tunnels[] | select(.proto=="https") | .public_url' | head -n1)
else
  URL=$(curl --silent http://127.0.0.1:4040/api/tunnels | python -c "import sys, json; j=json.load(sys.stdin);\nurls=[t.get('public_url') for t in j.get('tunnels',[]) if t.get('proto')=='https'];\nprint(urls[0] if urls else '')")
fi

if [ -z "$URL" ]; then
  echo "Could not determine ngrok public URL. See /tmp/ngrok.log for details." >&2
  echo "Tail logs: tail -n +1 /tmp/ngrok.log" >&2
  exit 1
fi

cat <<EOF
ngrok public URL: $URL

Set your Meta webhook callback URL to:
  $URL/webhooks/whatsapp

Make sure your local .env contains the same verify token:
  WHATSAPPAPP_VERIFY_TOKEN=<YOUR_VERIFY_TOKEN>

To stop ngrok, press Ctrl-C or run:
  kill $NGROK_PID

Note: this script does NOT modify any repo files or replace secrets. Edit backend/.env locally to add tokens and secrets.
EOF

# wait for user to exit; keep ngrok running until script killed
wait $NGROK_PID
