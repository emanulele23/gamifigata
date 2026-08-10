#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Manca .env — esegui prima: cp .env.example .env"
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "TELEGRAM_BOT_TOKEN vuoto nel .env"
  exit 1
fi

echo "1) Apri Telegram e scrivi QUALSIASI messaggio al tuo bot"
echo "2) Premi Invio qui quando hai inviato il messaggio"
read -r _

echo "Cerco chat_id..."
resp="$(curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates")"
chat_id="$(RESP="$resp" python3 - <<'PY'
import json, os
data = json.loads(os.environ["RESP"])
for upd in reversed(data.get("result") or []):
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    if "id" in chat:
        print(chat["id"])
        break
PY
)"

if [[ -z "$chat_id" ]]; then
  echo "Nessun messaggio trovato. Scrivi al bot e riprova."
  exit 1
fi

echo "Trovato TELEGRAM_CHAT_ID=${chat_id}"
if grep -q '^TELEGRAM_CHAT_ID=' .env; then
  sed -i "s/^TELEGRAM_CHAT_ID=.*/TELEGRAM_CHAT_ID=${chat_id}/" .env
else
  echo "TELEGRAM_CHAT_ID=${chat_id}" >> .env
fi
echo "Aggiornato .env"
echo
echo "Se lo stack è già avviato: docker compose up -d"
echo "Oppure, con stack acceso, puoi anche usare:"
echo "  curl http://localhost:5000/telegram/discover-chat"
