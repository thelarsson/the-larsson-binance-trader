#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

TRADES = Path('/home/jlarsson/.openclaw/workspace/skills/binance-spot-trader/trades.jsonl')


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return None


def load_rows():
    if not TRADES.exists():
        return []
    rows = []
    for line in TRADES.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    rows = [r for r in load_rows() if r.get('result') == 'FILLED' and parse_ts(r.get('ts')) and parse_ts(r.get('ts')) >= cutoff]

    buys = [r for r in rows if r.get('side') == 'BUY']
    sells = [r for r in rows if r.get('side') == 'SELL']

    buy_notional = sum(float(r.get('qty', 0) or 0) * float(r.get('price', 0) or 0) for r in buys)
    sell_notional = sum(float(r.get('qty', 0) or 0) * float(r.get('price', 0) or 0) for r in sells)
    net = sell_notional - buy_notional

    stop_loss = sum(1 for r in sells if r.get('exit_reason') == 'STOP_LOSS')
    take_profit = sum(1 for r in sells if r.get('exit_reason') == 'TAKE_PROFIT')
    strategy_exit = sum(1 for r in sells if r.get('exit_reason') == 'SIGNAL')

    print('24H PROFIT/LOSS REPORT')
    print(f'Filled buys: {len(buys)} | Filled sells: {len(sells)}')
    print(f'Buy notional: ${buy_notional:.2f}')
    print(f'Sell notional: ${sell_notional:.2f}')
    print(f'Net realized flow: ${net:.2f}')
    print(f'Sell triggers: STOP_LOSS={stop_loss} TAKE_PROFIT={take_profit} STRATEGY_SIGNAL={strategy_exit}')

    if rows:
        print('Recent fills:')
        for r in rows[-10:]:
            side = r.get('side', '?')
            symbol = r.get('symbol', '?')
            qty = r.get('qty', '?')
            price = r.get('price', '?')
            reason = r.get('exit_reason', '')
            extra = f' trigger={reason}' if side == 'SELL' and reason else ''
            print(f'- {r.get("ts","")} {side} {symbol} qty={qty} price={price}{extra}')
    else:
        print('No filled trades in the last 24 hours.')


if __name__ == '__main__':
    main()
