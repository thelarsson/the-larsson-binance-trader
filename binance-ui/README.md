# Binance Trader UI

Web UI för att övervaka Binance Trading Bot - **READ-ONLY**, zero risk.

## Snabbstart

```bash
cd /home/johan/.openclaw/workspace/binance-ui

# Sätt miljövariabler
export BOT_LOG_PATH=/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/logs
export BOT_DATA_PATH=/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/data

# Starta servern
python3 src/api/server.py

# Öppna i webbläsare:
# http://localhost:5000/api/status
```

## API Endpoints

- `GET /health` - Server status
- `GET /api/status` - Bot status + balance
- `GET /api/positions` - Nuvarande positioner
- `GET /api/trades` - Historiska trades
- `GET /api/signals` - Senaste trading-signaler
- `GET /api/profit` - Approximat PnL
- `GET /api/logs/recent` - Senaste logg-rader

## Säkerhet

- ✅ READ-ONLY (kan aldrig påverka trading)
- ✅ Separat process (krasch påverkar inte bot)
- ✅ Isolerad i Docker möjligt
- ✅ Ingen skrivåtkomst till trader-filer

## Utveckling

### Bygga React frontend (ej gjort än):
```bash
cd src/web
npm install
npm start
```

### Köra i Docker:
```bash
docker-compose up -d
```

## Status

- ✅ API Backend: KLART
- ⚠️ React Frontend: EJ PÅBÖRJAT
- ⚠️ Docker: Grund färdig, ej testad

## Skapat

2026-04-11 - Brainstorm Saturday
