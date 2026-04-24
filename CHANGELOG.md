# Changelog

Alla viktiga ändringar i Binance Trading Bot dokumenteras här.

## [2026-04-24] - RSI Strategy Implementation & Bug Fixes

### Tillagt
- **RSI-strategi** (`rsi_signal()`) - Köp vid RSI < 30, Sälj vid RSI > 70
- **`/signals` kommando** - Visar realtids-signaler (BUY/SELL/HOLD) för alla 20 pairs
- **Auto-reset switch counter** - Nollställs automatiskt efter 3 dagar
- **Fil-lås i notify_telegram.py** - Förhindrar duplicerade notiser

### Fixat
- **Improvement calculation bug** - Beräknade 0% istället för faktisk skillnad mellan strategier
- **RSI case i trader.py** - La till `elif STRATEGY == "rsi"` som saknades
- **Dubbla discovery-notiser** - Tog bort `send_discovery_report.py`
- **Dubbla trade-notiser** - Lade till deduplicering baserat på trade ID
- **Position sync** - Synkar lokal state vid misslyckade SELL
- **`.env` parse-fel** - `DISCOVERY_MIN_SCORE=0.3#` → separerade kommentar

### Ändrat
- **Strategi**: EMA → RSI (baserat på analys: RSI +8.77% vs EMA +0.52%)
- **Nästa analys-visning**: "Tomorrow" → "08:00 UTC today" / "20:00 UTC today"
- **`/signals`**: Visar nu alla 20 pairs (tidigare begränsat till 10)

### Tekniskt
- Commits: `0bc7554`, `0ad21aa`, `d25dc35`, `f65e09d`, `4b815e6`
- API-nycklar uppdaterade för ny IP-adress
- Cron-jobb verifierade efter systemomstart

## [2026-04-23] - System Recovery & Stabilisering

### Fixat
- **Zombie-processer** - Städade upp 14+ gamla `trader_continuous.sh` processer
- **Nätverksanslutning** - Återställde efter `dnf upgrade && reboot`
- **Telegram bot** - Startade om efter avbrott

## [2026-04-19 till 2026-04-22] - Initial Setup & Bug Fixes

### Tillagt
- **EMA-strategi** (`ema_signal()`) - EMA 9/20 crossover med HTF-filter
- **Decision Engine thresholds** - Sänkta till 0.0 för mer aggressiv trading
- **Auto Strategy Switcher** - 2 analyser per dag (08:00, 20:00 UTC)
- **Discovery notiser** - `notify_telegram.py` med deduplicering

### Fixat
- **Strategy state sync** - Synkade state-fil till EMA efter manuell ändring
- **Cron-jobb** - Återställde automatisk körning

## Kommande
- Övervaka RSI-strategins prestanda (win rate, P&L)
- Justera trösklar vid behov (nuvarande: RSI < 30 BUY, > 70 SELL)
- Evaluera om strategibyte ska göras mer sällan
