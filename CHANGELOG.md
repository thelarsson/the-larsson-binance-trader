# Changelog

Alla viktiga ändringar i detta projekt kommer att dokumenteras här.

Formatet är baserat på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.2.1] - 2026-04-06

### Tillagt
- **Execute Function för Auto Strategy Switcher**:
  - Byte sker automatiskt efter 5 minuter om inte `/abort_switch` körs
  - Sparar pending switch till `.pending_strategy_switch.json`
  - Uppdaterar `.env` filen vid byte (STRATEGY=variabel)
  - Sparar state i `.strategy_switcher_state.json`
  - Hanterar abort via `/abort_switch` kommando
  - Skickar "Strategy switched" bekräftelse till Telegram

### Ändrat
- **Switch limit**: Från 1/vecka till **1/3 dagar** för ökad flexibilitet
  - Mer responsiv vid marknadsändringar
  - Kostnad: ~0.045% per byte (0.3% av 15% position)
  - Realistisk årlig kostnad: ~2.7% vid ~60 byten/år
  - Fortfarande skydd mot övertrading

### Säkerhet
- Max 1 byte per 3 dagar (justerbart)
- Minst 7% förbättring krävs för byte
- 5 minuters opt-out fönster
- Stop-loss skyddar varje trade individuellt (-2%)

## [1.2.0] - 2026-04-03

### Tillagt (MAJOR FEATURE)
- **Auto Strategy Switcher**: Automatisk strategi-växling baserad på marknadsanalys
  - `scripts/auto_strategy_switcher.py` - Produktions-klar strategi-väljare
  - Analyserar BTC, ETH, SOL, CTSI dagligen kl 08:00 UTC
  - Jämför EMA Crossover, MACD, och RSI strategier
  - Växlar automatiskt till bäst presterande strategi (om du inte stoppar)
  - Telegram integration: `/strategy_status`, `/abort_switch`, `/confirm_switch`
  - Säkerhetsgränser: Max 1 byte/vecka, minst 7% förbättring krävs
  - Opt-out system: Byter automatiskt om du inte svarar inom 1 timme
  - Ingen cooldown efter strategi-byte
  
- **Test-miljö för strategi-analys**:
  - `intelligent_strategy_switcher_v2.py` - Komplett analys-system
  - `adaptive_strategy_engine.py` - Marknadsfaser och strategi-urval
  - Backtestar med transaktionskostnader (0.1% fee + 0.05% spread)
  - Caching av API-anrop för prestanda
  - Felhantering och loggning till fil
  
- **Test-resultat (180 dagars backtest)**:
  - BTC: EMA +8.64% (vinnare)
  - ETH: MACD +7.72% (vinnare)  
  - SOL: EMA +3.27% (vinnare)
  - CTSI: MACD +18.91% (vinnare)
  
### Ändrat
- **Telegram Bot**: Nya kommandon för strategi-hantering
  - `/strategy_status` - Visa nuvarande strategi och pending byten
  - `/abort_switch` - Avbryt planerat byte
  - `/confirm_switch` - Utför byte omedelbart
  
### Tekniska förbättringar
- Async HTTP requests för Binance API-anrop
- Caching (5-min TTL) för att minska API-anrop
- Omfattande felhantering med specifika exceptions
- Loggning till fil (`auto_strategy_switcher.log`)
- Separerade klasser för bättre testbarhet

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
