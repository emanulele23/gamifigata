# Echo — Assistente vocale proattivo per salute e crescita

Echo **ti chiama 2-3 volte al giorno** (Telegram), ti fa **domande mirate** con voce naturale, **compila i dati per te** e tiene traccia di obiettivi, streak e Apple Salute — **senza aprire un’app ogni volta**.

Pensato per **Raspberry Pi 5**: `git clone` → onboarding guidato → Docker.

## Cosa fa (in pratica)

| Momento | Echo ti chiede… | Salva |
|---|---|---|
| Mattina (~9:00) | Come hai dormito, come ti senti | umore, sonno |
| Pranzo (~14:00) | Cosa hai mangiato, ti sei mosso | pasto, attività |
| Sera (~21:00) | Giornata, umore, micro-vittorie | mood, habits, note |

- **Voce umana** (Fish Audio) + **cervello** (DeepSeek)
- **Gamification**: obiettivi personali, streak, celebrazioni brevi
- **Apple Salute**: iPhone invia passi/esercizio via Shortcut (vedi [docs/apple-health-shortcut.md](docs/apple-health-shortcut.md))
- **Zero sforzo manuale**: rispondi a voce o in chat, Echo estrae i dati

## Prima installazione (consigliato)

```bash
git clone https://github.com/emanulele23/gamifigata.git echo
cd echo
git checkout cursor/echo-personal-agent-4b35

python3 scripts/onboard.py   # wizard: nome, API key, obiettivi, orari, Apple Salute
./scripts/setup.sh           # oppure: make up
```

Il wizard ti chiede:
- Nome e fuso orario
- Token Telegram, API DeepSeek e Fish Audio
- Orari check-in (default 09:00, 14:00, 21:00)
- Se vuoi **chiamate/notifiche vocali**
- Chi sei e cosa vuoi migliorare → Echo propone **micro-obiettivi** con l’AI
- Collegamento **Apple Salute** (opzionale)

## Dopo l’avvio

```bash
make health      # stato + onboarding
make checkin     # simula un check-in vocale adesso
make logs
```

Scrivi al bot su Telegram: risponde con testo + nota vocale.

### Chiamate vocali (Fase 5)

Con `ENABLE_VOICE_CALLS=true`, agli check-in Echo tenta una **consegna vocale via userbot Telegram** (nota vocale + opz. voice chat). Setup:

```bash
python3 scripts/login_userbot.py
docker compose up -d --build
```

## Apple Salute

La Raspi **non accede** direttamente a Salute. Un **Shortcut iPhone** manda passi e minuti esercizio a Echo. Guida: [docs/apple-health-shortcut.md](docs/apple-health-shortcut.md).

## Architettura

```
iPhone (Shortcut Salute) ──POST──► echo-api ──► SQLite
Telegram ◄── check-in vocali ── echo-api ──► DeepSeek + Fish Audio
n8n (opzionale) ── cron ──► echo-api
```

## API utili

| Endpoint | Descrizione |
|---|---|
| `POST /checkin` | check-in vocale immediato |
| `GET /profile` | profilo e orari |
| `GET /goals` | obiettivi + streak |
| `POST /integrations/apple-health` | dati da iPhone |
| `GET /health` | stato sistema |

## Costi

- DeepSeek + Fish Audio: pochi €/mese uso personale
- Fish ASR per trascrizione (no Whisper/OpenAI, no GPU)
- SQLite e n8n self-host: gratis

## n8n (opzionale)

Importa `n8n/workflows/A_promemoria.json`, `B_ricezione.json`, `C_chiamata.json`.  
Se usi n8n per i cron, imposta `ENABLE_INTERNAL_REMINDERS=false`.

## Struttura

```
scripts/onboard.py      # wizard prima installazione
scripts/setup.sh        # avvio Docker
echo-api/               # backend FastAPI
docs/apple-health-shortcut.md
n8n/workflows/
```
