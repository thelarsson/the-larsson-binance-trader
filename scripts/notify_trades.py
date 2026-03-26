#!/usr/bin/env python3
import json
from pathlib import Path

BASE = Path('/home/jlarsson/.openclaw/workspace/skills/binance-spot-trader')
TRADES = BASE / 'trades.jsonl'
STATE = BASE / 'notify-state.json'
OUTBOX = BASE / 'notify-outbox.txt'


def load_state():
    if not STATE.exists():
        return {"last_line": 0}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"last_line": 0}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def main():
    state = load_state()
    last_line = int(state.get('last_line', 0) or 0)

    if not TRADES.exists():
        save_state({"last_line": 0})
        return

    lines = TRADES.read_text().splitlines()
    new = lines[last_line:]
    messages = []

    for line in new:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get('result') != 'FILLED':
            continue

        side = row.get('side', 'UNKNOWN')
        symbol = row.get('symbol', '?')
        qty = row.get('qty', '?')
        price = row.get('price', '?')
        ts = row.get('ts', '')

        if side == 'BUY':
            messages.append(f"BUY filled: {symbol} qty={qty} price={price} ts={ts}")
        elif side == 'SELL':
            reason = row.get('exit_reason') or 'UNKNOWN'
            if reason == 'STOP_LOSS':
                messages.append(f"SELL filled: {symbol} qty={qty} price={price} ts={ts} | trigger=STOP_LOSS")
            elif reason == 'TAKE_PROFIT':
                messages.append(f"SELL filled: {symbol} qty={qty} price={price} ts={ts} | trigger=TAKE_PROFIT")
            elif reason == 'SIGNAL':
                messages.append(f"SELL filled: {symbol} qty={qty} price={price} ts={ts} | trigger=STRATEGY_SIGNAL (not stop loss)")
            else:
                messages.append(f"SELL filled: {symbol} qty={qty} price={price} ts={ts} | trigger={reason}")

    if messages:
        with OUTBOX.open('a') as f:
            for msg in messages:
                f.write(msg + '\n')

    save_state({"last_line": len(lines)})


if __name__ == '__main__':
    main()
