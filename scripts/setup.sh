#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo ""
echo "  Echo — installazione guidata"
echo "  ────────────────────────────"
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "Installo Docker (serve una volta sola)..."
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  sudo usermod -aG docker "$USER" 2>/dev/null || true
  echo ""
  echo "Docker installato. Se è la prima volta, riavvia la sessione e rilancia questo script."
  exit 0
fi

mkdir -p echo-api/data

if [[ ! -f .env ]]; then
  cp .env.example .env 2>/dev/null || touch .env
fi

echo "Avvio Echo..."
docker compose up -d --build

IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")"

echo ""
echo "  Fatto!"
echo ""
echo "  Prossimo passo (dal telefono o PC, stessa rete Wi‑Fi):"
echo ""
echo "    http://${IP}:5000/setup"
echo ""
echo "  Inserisci le 3 chiavi API, poi apri Telegram e scrivi al tuo bot:"
echo ""
echo "    /start"
echo ""
echo "  Echo ti guiderà con domande semplici. Nient'altro da fare."
echo ""
