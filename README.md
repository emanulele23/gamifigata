# Echo — Personal Life & Health Agent

Agente personale per **Raspberry Pi 5 (8GB)**: health & habit tracking via Telegram, con voce umana (Fish Audio), cervello LLM (DeepSeek) e orchestrazione **n8n** + SQLite locale.

Clona, compila `.env`, avvia Docker. Niente GPU.

## Architettura

```
Raspberry Pi 5
├── n8n (Docker)          → cron + Telegram trigger
├── echo-api (Docker)     → DeepSeek, Fish TTS/ASR, SQLite, /call
└── data/echo.db          → log cibo, mood, habits, note salute
         │
         ├── Telegram Bot (chat + note vocali)
         ├── DeepSeek API (ragionamento)
         └── Fish Audio API (TTS + trascrizione ASR)
```

### Perché non OpenAI Whisper?

Per uso personale **senza GPU**, la trascrizione gira su **Fish Audio ASR** (`/v1/asr`):

- stesso ordine di costo di Whisper (~$0.36/ora audio → centesimi/mese)
- **una sola API key** insieme al TTS
- zero carico CPU sul Pi

DeepSeek tiene basso il costo del LLM. SQLite è gratis e locale.

## Requisiti sulla Raspi

- Raspberry Pi OS 64-bit
- Docker + Docker Compose plugin
- Account/API:
  1. Telegram Bot token (`@BotFather`) + il tuo `chat_id`
  2. DeepSeek API key
  3. Fish Audio API key + `reference_id` della voce clonata
  4. *(opzionale, chiamate)* Telegram `api_id` / `api_hash` da [my.telegram.org](https://my.telegram.org) + secondo account userbot

## Quick start

```bash
git clone <URL_DI_QUESTA_REPO> echo
cd echo
cp .env.example .env
nano .env   # inserisci le chiavi

chmod +x scripts/setup.sh
./scripts/setup.sh
```

Oppure a mano:

```bash
docker compose up -d --build
```

Servizi:

| Servizio | URL |
|---|---|
| echo-api | `http://IP_RASPI:5000/health` |
| n8n | `http://IP_RASPI:5678` |

### Due modi di usare Echo

**A) Consigliato per partire subito — standalone bot**

Nel `.env`:

```env
STANDALONE_BOT=true
```

Poi `docker compose up -d --build`.  
`echo-api` fa polling Telegram, risponde con testo + nota vocale, e invia i promemoria agli orari in `REMINDER_TIMES`. n8n resta disponibile ma non è obbligatorio.

**B) Orchestrazione n8n**

1. Apri n8n su porta `5678` e completa il setup utente
2. Importa:
   - [`n8n/workflows/A_promemoria.json`](n8n/workflows/A_promemoria.json)
   - [`n8n/workflows/B_ricezione.json`](n8n/workflows/B_ricezione.json)
3. Nel workflow B collega le credenziali Telegram (stesso bot token)
4. Attiva i workflow
5. Lascia `STANDALONE_BOT=false` per evitare doppie risposte

> Nota: per evitare doppi promemoria, se usi i cron di n8n imposta `ENABLE_INTERNAL_REMINDERS=false` nel `.env`.

## Variabili `.env` essenziali

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...          # scrivi al bot, poi usa getUpdates o @userinfobot
DEEPSEEK_API_KEY=...
FISH_API_KEY=...
FISH_REFERENCE_ID=...         # voce clonata su fish.audio
REMINDER_TIMES=13:30,21:00
TZ=Europe/Rome
STANDALONE_BOT=true           # true = funziona senza configurare n8n
ENABLE_VOICE_CALLS=false
```

### Come trovare `TELEGRAM_CHAT_ID`

1. Avvia lo stack con almeno il bot token
2. Scrivi un messaggio al bot
3. Apri: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copia `message.chat.id`

## API echo-api (per n8n o test)

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/health` | stato |
| GET | `/context` | ultimi log + summary |
| POST | `/log` | salva tracking manuale |
| POST | `/chat` | testo → DeepSeek → TTS → (opz.) invio Telegram |
| POST | `/transcribe` | upload audio → Fish ASR |
| POST | `/handle-audio` | audio → ASR → LLM → TTS |
| POST | `/telegram/file` | `file_id` Telegram → pipeline completa |
| POST | `/remind` | genera promemoria e invia |
| POST | `/tts` | testo → file audio |
| POST | `/call` | userbot: consegna vocale / voice chat |

Esempio promemoria:

```bash
curl -X POST http://localhost:5000/remind \
  -H 'Content-Type: application/json' \
  -d '{"send": true, "try_call": false}'
```

## Database SQLite

File: `echo-api/data/echo.db`

| Campo | Tipo | Descrizione |
|---|---|---|
| data_ora | timestamp ISO | quando |
| pasto | testo | cibo |
| mood_score | 1–10 | umore |
| habits_done | JSON/lista | abitudini |
| note_salute | testo | sonno, sintomi, stanchezza |
| raw_text | testo | messaggio originale |
| source | testo | `chat` / `voice` / `api` |

Echo estrae i dati da un blocco `<data>{...}</data>` generato dal LLM.

## Fase 5 — Chiamate vocali (opzionale)

Le chiamate VoIP 1:1 “classiche” di Telegram non sono stabilmente supportate dalle librerie open-source. Echo usa un **userbot Pyrogram** che:

1. invia la nota vocale dal secondo account (affidabile)
2. se installi `py-tgcalls`, prova a riprodurre l’audio in una voice chat sul target

Setup:

```bash
# 1) Compila nel .env:
# TELEGRAM_API_ID=...
# TELEGRAM_API_HASH=...
# TELEGRAM_CALL_TARGET=@tuo_username_oppure_id
# ENABLE_VOICE_CALLS=true

# 2) Login interattivo (una tantum)
python3 -m venv .venv
source .venv/bin/activate
pip install pyrogram tgcrypto
python scripts/login_userbot.py

# 3) (opzionale) voice chat playback
# Entra nel container e: pip install -r requirements-calls.txt

docker compose up -d --build
```

Test:

```bash
curl -X POST http://localhost:5000/call \
  -H 'Content-Type: application/json' \
  -d '{"text": "Ehi, solo un check veloce. Come stai?"}'
```

## Costi stimati (uso personale)

| Voce | Stima |
|---|---|
| DeepSeek | pochi €/mese |
| Fish TTS + ASR | centesimi–pochi €/mese |
| SQLite / n8n self-host | 0 |
| OpenAI Whisper | **non usato** |

## Persona (system prompt)

Echo è un amico/accountability partner: italiano parlato, una domanda alla volta, validazione emotiva prima dei dati, blocco `<data>` per il tracking.

## Troubleshooting

- **`/health` down**: `docker compose logs -f echo-api`
- **Bot non risponde**: verifica token, `TELEGRAM_CHAT_ID`, e che non ci siano *due* consumer attivi (standalone + n8n) sullo stesso bot
- **TTS/ASR error**: controlla `FISH_API_KEY` e `FISH_REFERENCE_ID`
- **DeepSeek error**: controlla credito/API key su platform.deepseek.com
- **Permessi Docker**: aggiungi l’utente al gruppo `docker`, poi ri-login

## Struttura repo

```
├── docker-compose.yml
├── .env.example
├── scripts/setup.sh
├── scripts/login_userbot.py
├── echo-api/          # FastAPI + SQLite + Fish + DeepSeek + Pyrogram
└── n8n/workflows/     # JSON importabili
```
