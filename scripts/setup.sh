#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Echo setup (Raspberry Pi 5)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker non trovato. Installazione..."
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  sudo usermod -aG docker "$USER" || true
  echo "Docker installato. Se è la prima volta, esci e rientra nella sessione (o riavvia) così il gruppo docker è attivo."
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERRORE: 'docker compose' non disponibile. Aggiorna Docker."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Creato .env da .env.example — aprilo e inserisci le API key."
  echo "  nano .env"
  exit 0
fi

missing=0
for key in TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID DEEPSEEK_API_KEY FISH_API_KEY; do
  val="$(grep -E "^${key}=" .env | head -n1 | cut -d= -f2- || true)"
  if [[ -z "${val}" ]]; then
    echo "Manca ${key} in .env"
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  echo "Compila .env e riesegui: ./scripts/setup.sh"
  exit 1
fi

mkdir -p echo-api/data n8n_data
echo "==> Avvio stack (n8n + echo-api)"
docker compose up -d --build

echo
echo "Pronto."
echo "  echo-api health: http://$(hostname -I | awk '{print $1}'):5000/health"
echo "  n8n UI:          http://$(hostname -I | awk '{print $1}'):5678"
echo
echo "Importa i workflow da n8n/workflows/ nella UI n8n,"
echo "oppure imposta STANDALONE_BOT=true in .env per usare solo echo-api."
