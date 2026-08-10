# Apple Salute → Echo (iPhone Shortcut)

Apple **non permette** alla Raspberry Pi di leggere Salute direttamente.  
La soluzione: un **Shortcut su iPhone** che invia i dati a Echo 1–2 volte al giorno.

## Prerequisiti

- Echo avviato e raggiungibile dalla rete locale (o con tunnel)
- `APPLE_HEALTH_SECRET` impostato nel `.env` (generato da `python3 scripts/onboard.py`)
- App **Shortcuts** su iPhone

## Endpoint

```
POST {ECHO_PUBLIC_URL}/integrations/apple-health
Content-Type: application/json

{
  "secret": "IL_TUO_APPLE_HEALTH_SECRET",
  "day": "2026-08-10",
  "steps": 8420,
  "exercise_minutes": 35,
  "active_energy_kcal": 420,
  "sleep_hours": 7.2,
  "workouts": [{"type": "Walking", "minutes": 30}]
}
```

Tutti i campi tranne `secret` sono opzionali.

## Shortcut consigliato (manuale)

1. Apri **Shortcuts** → **+** → nuova automazione
2. **Ora del giorno**: 08:00 e 20:00 (o dopo allenamento)
3. Aggiungi azioni:
   - **Find Health Samples** → Passi (Oggi)
   - **Find Health Samples** → Minuti esercizio (Oggi)
   - **Get Contents of URL**:
     - URL: `http://IP_RASPI:5000/integrations/apple-health`
     - Method: POST
     - Headers: `Content-Type: application/json`
     - Body JSON con i valori letti + `secret`

4. Concedi permessi Salute quando richiesto

## Cosa fa Echo con questi dati

- Durante i check-in vocali, Echo può dire: *"Vedo che oggi hai fatto X passi..."*
- Incrocia attività dichiarata vs dati Apple
- Aggiorna streak su obiettivi fitness/movimento

## Test rapido (da PC/Raspi)

```bash
curl -X POST http://localhost:5000/integrations/apple-health \
  -H 'Content-Type: application/json' \
  -d '{
    "secret": "IL_TUO_SECRET",
    "steps": 5000,
    "exercise_minutes": 20
  }'
```

Verifica:

```bash
curl http://localhost:5000/integrations/apple-health
```

## Note privacy

- I dati restano sul SQLite locale della Raspi
- Usa HTTPS o rete domestica; non esporre la porta 5000 su Internet senza protezione
