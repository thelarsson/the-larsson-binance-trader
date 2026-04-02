# Changelog

Alla viktiga ändringar i detta projekt kommer att dokumenteras här.

Formatet är baserat på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.1.0] - 2026-04-02

### Tillagt
- **Weekly LLM Analysis System**: Automatisk veckoanalys med qwen2.5:14b som genererar PDF-rapporter
  - `scripts/weekly_llm_analyzer.py` - Huvudanalys-skript
  - `scripts/weekly_analysis.sh` - Shell-wrapper för cron
  - Cron-jobb: Varje fredag 17:00 UAE
  - Analyserar: Performance, strategi, risk, kodkvalitet
  - Skickar PDF till Telegram

- **Dynamisk PAIRS-uppdatering**: Automatisk uppdatering av trading pairs baserat på discovery engine
  - `update_dynamic_pairs.py` - Uppdaterar .env med top-scoring pairs
  - Min_score: 0.05, max_pairs: 8
  - Inkluderar alltid BTCUSDT som anchor

- **Crypto News Scraper förbättringar**:
  - `send_sentiment_report.py` - Skickar sentiment-rapport till Telegram
  - `send_discovery_report.py` - Skickar discovery-rapport till Telegram
  - `discovery_silent.py` - Tyst variant som inte skriver till OpenClaw chat
  - Cron-jobb: Varje timme för både sentiment och discovery

- **Morning Status Report**: Daglig systemrapport kl 08:00
  - Fedora systemstatus (CPU, RAM, disk, uptime)
  - Trading bot status och positioner
  - Discovery och Sentiment status
  - AgentMail sammanfattning

- **AgentMail Handler**: Automatisk email-hantering
  - Kör var 4:e timme
  - Hanterar mail från godkända avsändare (johan@the-larsson.com, johan.larsson@dafo-middle-east.com)
  - Auto-reply till andra avsändare eller forward till dig
  - Begränsat till 1 svar per thread
  - Raderar mail äldre än 30 dagar

- **Dokumentation**:
  - `DOCUMENTATION.md` - Svensk dokumentation
  - `DOCUMENTATION_EN.md` - Engelsk dokumentation
  - Professionella PDF-versioner genererade

### Ändrat
- **Sentiment rapport format**: Uppdaterad för att visa Key Headlines, Breakdown, och Trading Signal korrekt
- **Discovery tyst körning**: Alla cron-jobb omdirigerar stdout för att förhindra OpenClaw capture
- **Trading bot konfiguration**: 
  - TRADE_SIZE_PCT: 15% (för balanserad risk)
  - TAKE_PROFIT_PCT: 3% / STOP_LOSS_PCT: 2% (baserat på backtesting)

### Fixat
- Rättat JSON-parsning i send_sentiment_report.py för korrekt visning av breakdown-data
- AgentMail PATH-problem i cron (lagt till full PATH i run_crypto_silent.sh)
- Email-thread hantering för att förhindra dubbla svar

## [1.0.0] - 2026-03-25

### Tillagt
- Initial release av The Larsson Binance Trader
- Momentum-strategi med EMA crossover (EMA9/EMA20)
- Telegram integration för notifikationer
- Risk management: 2% stop-loss, 3% take-profit
- Max 2 positioner, 15% trade size
- Sentiment integration från crypto news
- Discovery engine för nya trading pairs
- Automatisk positionssynkronisering med Binance
