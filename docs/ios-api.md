# API Echo — pronta per app iOS futura

Base URL: `http://IP_RASPI:5000` (in produzione: HTTPS consigliato)

Tutte le risposte sono JSON. Nessun auth obbligatorio in rete locale; per app iOS aggiungere in futuro un token (`Authorization: Bearer ...`).

## Setup e stato

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/health` | Stato servizio, `configured`, `onboarding_complete` |
| GET | `/setup` | Pagina web configurazione chiavi |
| POST | `/setup/save` | Salva chiavi API |

```json
POST /setup/save
{
  "telegram_bot_token": "...",
  "deepseek_api_key": "...",
  "fish_api_key": "...",
  "fish_reference_id": "..."
}
```

## Profilo utente

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/profile` | Nome, orari check-in, preferenze |
| POST | `/profile` | Aggiorna profilo |

## Dati salute e diario

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/logs?limit=50` | Storico registrazioni |
| GET | `/context` | Summary + ultimi log |
| POST | `/log` | Inserimento manuale |

```json
POST /log
{
  "pasto": "Pasta e insalata",
  "mood_score": 7,
  "habits_done": ["Camminata"],
  "attivita_fisica": true,
  "minuti_attivita": 30,
  "note_salute": "Dormito 7 ore"
}
```

## Obiettivi e gamification

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/goals` | Obiettivi attivi + streak |
| GET | `/streaks` | Solo streak |
| POST | `/goals` | Nuovo obiettivo |

## Apple Salute

| Metodo | Path | Descrizione |
|--------|------|-------------|
| POST | `/integrations/apple-health` | Invio dati da iPhone |
| GET | `/integrations/apple-health` | Dati di oggi |

Ideale per app iOS nativa con HealthKit → stesso endpoint del Shortcut.

## Check-in

| Metodo | Path | Descrizione |
|--------|------|-------------|
| POST | `/checkin` | Avvia check-in vocale adesso |

```json
POST /checkin
{ "send": true }
```

## Chat (test / app)

| Metodo | Path | Descrizione |
|--------|------|-------------|
| POST | `/chat` | Messaggio testo → risposta Echo |

```json
POST /chat
{ "text": "Oggi ho camminato 30 minuti", "send": false }
```

## Modello dati principale (log)

| Campo | Tipo | Note |
|-------|------|------|
| data_ora | ISO8601 | Timestamp |
| pasto | string | |
| mood_score | 1-10 | |
| habits_done | array | |
| attivita_fisica | bool | |
| minuti_attivita | int | |
| note_salute | string | |

## Roadmap app iOS

1. HealthKit → `POST /integrations/apple-health`
2. UI obiettivi/streak → `GET /goals`
3. Chat in-app → `POST /chat` + TTS locale o Fish
4. Push locali agli orari check-in (stessi orari di `/profile`)

Telegram resta il canale principale finché l'app non è pronta.
