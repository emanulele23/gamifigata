# Echo — 3 passi, poi funziona da solo

Echo è un assistente su **Telegram** che ti scrive **2-3 volte al giorno**, ti fa **una domanda semplice** (umore, cibo, movimento) e **salva tutto per te**. Rispondi a voce o a testo. Niente app da aprire ogni giorno.

## Installazione (Raspberry Pi)

```bash
git clone https://github.com/emanulele23/gamifigata.git echo
cd echo
./scripts/setup.sh
```

Lo script avvia Echo e ti mostra un indirizzo tipo:

**http://192.168.x.x:5000/setup**

Apri quel link **dal telefono** (stessa Wi‑Fi), incolla le 3 chiavi API, salva.

## Configurazione su Telegram

1. Crea un bot con [@BotFather](https://t.me/BotFather) → copia il **token**
2. Registrati su [DeepSeek](https://platform.deepseek.com) → **API key**
3. Registrati su [Fish Audio](https://fish.audio) → **API key** + voce clonata

Poi apri Telegram, cerca il tuo bot e scrivi:

```
/start
```

Echo ti chiede il nome, cosa vuoi migliorare, ti propone obiettivi. **Fine.**

## Cosa succede ogni giorno

| Ora | Echo ti chiede |
|-----|----------------|
| ~9:00 | Come hai dormito, come ti senti |
| ~14:00 | Cosa hai mangiato, ti sei mosso |
| ~21:00 | Com'è andata la giornata |

Rispondi con un **messaggio vocale** o testo. Echo capisce, salva, e ti tiene la **streak** sugli obiettivi.

Comandi utili su Telegram:
- `/stato` — riepilogo
- `/obiettivi` — obiettivi e streak

## Apple Salute (opzionale)

L'iPhone può mandare passi e minuti di esercizio a Echo con un **Shortcut**. Guida: [docs/apple-health-shortcut.md](docs/apple-health-shortcut.md).

In futuro potrai usare la stessa API da un'**app iOS** — vedi [docs/ios-api.md](docs/ios-api.md).

## Domande frequenti

**Devo usare n8n, Pyrogram o SSH?**  
No. È tutto opzionale per utenti avanzati. Il percorso normale è: setup → pagina web → Telegram `/start`.

**Quanto costa?**  
DeepSeek + Fish Audio: pochi euro al mese per uso personale.

**I miei dati dove stanno?**  
Sul SQLite della tua Raspberry Pi, in casa tua.

## Struttura semplice

```
./scripts/setup.sh     ← unico comando installazione
http://IP:5000/setup   ← inserisci chiavi API
Telegram /start        ← configurazione personale
```
