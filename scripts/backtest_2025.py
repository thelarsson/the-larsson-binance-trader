#!/usr/bin/env python3
import csv
import io
import math
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

BASE_DIR = Path('/home/jlarsson/.openclaw/workspace/skills/binance-spot-trader')
CACHE_DIR = BASE_DIR / 'data_cache'
CACHE_DIR.mkdir(exist_ok=True)

PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','LINKUSDT','AVAXUSDT']
INITIAL_USDT = 129.5456
TRADE_SIZE_PCT = 10.0
MAX_POSITIONS = 2
STOP_LOSS_PCT = 2.0
TAKE_PROFIT_PCT = 3.0
COOLDOWN_HOURS = 12.0
MAX_DAILY_LOSS_PCT = 2.0
MAX_TRADES_PER_PAIR_PER_DAY = 2
USDT_RESERVE_PCT = 40.0
INTERVAL = '5m'
YEAR = 2025
FEE_RATE = 0.001  # illustrative only, not in base backtest

MONTHS = [f'{m:02d}' for m in range(1, 13)]

@dataclass
class Candle:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float


def ema(prices, period):
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e


def momentum_signal(klines):
    prices = [k.c for k in klines]
    ema20 = ema(prices, 20)
    current = prices[-1]
    avg_vol = sum(k.v for k in klines[-20:]) / 20
    vol_spike = klines[-1].v > avg_vol * 1.5
    if current > ema20 and vol_spike:
        return 'BUY'
    if current < ema20:
        return 'SELL'
    return 'HOLD'


def dt_from_ms(ms):
    # Binance vision monthly spot kline files currently use microsecond timestamps.
    return datetime.fromtimestamp(ms / 1_000_000, tz=timezone.utc)


def cache_path(symbol, month):
    return CACHE_DIR / f'{symbol}-{INTERVAL}-{YEAR}-{month}.csv'


def fetch_month(symbol, month):
    out = cache_path(symbol, month)
    if out.exists():
        return out
    url = f'https://data.binance.vision/data/spot/monthly/klines/{symbol}/{INTERVAL}/{symbol}-{INTERVAL}-{YEAR}-{month}.zip'
    print(f'Downloading {symbol} {YEAR}-{month}...', flush=True)
    with urlopen(url, timeout=60) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = zf.namelist()[0]
        data = zf.read(name)
    out.write_bytes(data)
    return out


def load_symbol(symbol):
    print(f'Loading {symbol}...', flush=True)
    candles = []
    for month in MONTHS:
        csv_path = fetch_month(symbol, month)
        with open(csv_path, 'r', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                try:
                    open_time = int(row[0])
                except ValueError:
                    continue
                candles.append(Candle(
                    t=open_time,
                    o=float(row[1]),
                    h=float(row[2]),
                    l=float(row[3]),
                    c=float(row[4]),
                    v=float(row[5]),
                ))
    candles.sort(key=lambda x: x.t)
    return candles


def get_position_state(trades, symbol):
    qty = 0.0
    cost = 0.0
    for row in trades:
        if row['symbol'] != symbol or row['result'] != 'FILLED':
            continue
        side = row['side']
        trade_qty = float(row['qty'])
        trade_price = float(row['price'])
        if side == 'BUY':
            qty += trade_qty
            cost += trade_qty * trade_price
        elif side == 'SELL':
            sell_qty = min(qty, trade_qty)
            avg_price = (cost / qty) if qty > 0 else 0
            cost -= sell_qty * avg_price
            qty -= sell_qty
            if qty <= 1e-12:
                qty = 0.0
                cost = 0.0
    avg_entry = (cost / qty) if qty > 0 else None
    return {'qty': qty, 'cost': cost, 'avg_entry': avg_entry}


def current_open_symbols(trades):
    return {symbol for symbol in PAIRS if get_position_state(trades, symbol)['qty'] > 0}


def trades_today(trades, now_dt, symbol=None):
    day = now_dt.date()
    rows = []
    for row in trades:
        ts = row['dt']
        if ts.date() != day:
            continue
        if row['result'] != 'FILLED':
            continue
        if symbol and row['symbol'] != symbol:
            continue
        rows.append(row)
    return rows


def realized_pnl_today(trades, now_dt):
    pnl = 0.0
    for row in trades_today(trades, now_dt):
        qty = float(row['qty'])
        price = float(row['price'])
        if row['side'] == 'SELL':
            pnl += qty * price
        elif row['side'] == 'BUY':
            pnl -= qty * price
    return pnl


def in_cooldown(trades, symbol, now_dt):
    cutoff = now_dt - timedelta(hours=COOLDOWN_HOURS)
    for row in reversed(trades):
        if row['symbol'] != symbol:
            continue
        ts = row['dt']
        if ts < cutoff:
            break
        if row['side'] == 'SELL' and row.get('exit_reason') == 'STOP_LOSS':
            return True, ts
    return False, None


def spot_value(portfolio, prices):
    total = portfolio['USDT']
    for sym, qty in portfolio.items():
        if sym == 'USDT' or qty <= 0:
            continue
        total += qty * prices[sym + 'USDT']
    return total


def place_order(trades, portfolio, symbol, side, quantity, price, now_dt, extra=None):
    base = symbol.replace('USDT', '')
    quantity = float(f'{quantity:.6f}')
    if quantity <= 0:
        return False
    if side == 'BUY':
        notional = quantity * price
        if portfolio['USDT'] + 1e-12 < notional:
            return False
        portfolio['USDT'] -= notional
        portfolio[base] += quantity
    else:
        if portfolio[base] <= 0:
            return False
        quantity = min(quantity, portfolio[base])
        quantity = float(f'{quantity:.6f}')
        notional = quantity * price
        portfolio[base] -= quantity
        if portfolio[base] < 1e-12:
            portfolio[base] = 0.0
        portfolio['USDT'] += notional
    row = {
        'ts': now_dt.isoformat(),
        'dt': now_dt,
        'symbol': symbol,
        'side': side,
        'qty': quantity,
        'result': 'FILLED',
        'price': price,
    }
    if extra:
        row.update(extra)
    trades.append(row)
    return True


def run_backtest():
    series = {symbol: load_symbol(symbol) for symbol in PAIRS}
    min_len = min(len(v) for v in series.values())
    # align on common timestamps just in case
    common_ts = sorted(set(c.t for c in series[PAIRS[0]]))
    for symbol in PAIRS[1:]:
        common_ts = sorted(set(common_ts).intersection({c.t for c in series[symbol]}))
    idx_map = {symbol: {c.t: i for i, c in enumerate(series[symbol])} for symbol in PAIRS}

    portfolio = defaultdict(float)
    portfolio['USDT'] = INITIAL_USDT
    trades = []
    skipped_balance = 0
    signal_counts = defaultdict(int)

    for ts in common_ts:
        now_dt = dt_from_ms(ts)
        prices = {symbol: series[symbol][idx_map[symbol][ts]].c for symbol in PAIRS}
        equity_start = spot_value(portfolio, prices)
        balance = portfolio['USDT']
        pnl_today = realized_pnl_today(trades, now_dt)
        daily_threshold = balance * (MAX_DAILY_LOSS_PCT / 100.0)
        if pnl_today <= -daily_threshold:
            continue
        reserve_usdt = balance * (USDT_RESERVE_PCT / 100.0)

        for symbol in PAIRS:
            i = idx_map[symbol][ts]
            if i < 49:
                continue
            klines = series[symbol][i-49:i+1]
            signal = momentum_signal(klines)
            current_price = klines[-1].c
            position = get_position_state(trades, symbol)
            avg_entry = position['avg_entry']
            risk_event = None
            if avg_entry and position['qty'] > 0:
                stop_price = avg_entry * (1 - STOP_LOSS_PCT / 100.0)
                take_profit_price = avg_entry * (1 + TAKE_PROFIT_PCT / 100.0)
                if current_price <= stop_price:
                    risk_event = 'STOP_LOSS'
                elif current_price >= take_profit_price:
                    risk_event = 'TAKE_PROFIT'

            if risk_event in {'STOP_LOSS', 'TAKE_PROFIT'}:
                held = portfolio[symbol.replace('USDT', '')]
                if held * current_price > 10:
                    signal_counts[f'SELL_{risk_event}'] += 1
                    place_order(trades, portfolio, symbol, 'SELL', held, current_price, now_dt, {'exit_reason': risk_event})
                continue

            if signal == 'BUY':
                open_symbols = current_open_symbols(trades)
                if symbol in open_symbols:
                    continue
                if len(open_symbols) >= MAX_POSITIONS:
                    continue
                cooldown, _ = in_cooldown(trades, symbol, now_dt)
                if cooldown:
                    continue
                pair_trades_today = len(trades_today(trades, now_dt, symbol))
                if pair_trades_today >= MAX_TRADES_PER_PAIR_PER_DAY:
                    continue
                trade_usdt = balance * (TRADE_SIZE_PCT / 100.0)
                available_usdt = max(0.0, balance - reserve_usdt)
                trade_usdt = min(trade_usdt, available_usdt)
                qty = trade_usdt / current_price if current_price > 0 else 0
                if trade_usdt >= 10:
                    ok = place_order(trades, portfolio, symbol, 'BUY', qty, current_price, now_dt, {'entry_strategy': 'momentum'})
                    if ok:
                        signal_counts['BUY'] += 1
                    else:
                        skipped_balance += 1
                continue

            if signal == 'SELL':
                held = portfolio[symbol.replace('USDT', '')]
                if held * current_price > 10:
                    signal_counts['SELL_SIGNAL'] += 1
                    place_order(trades, portfolio, symbol, 'SELL', held, current_price, now_dt, {'exit_reason': 'SIGNAL'})

    final_prices = {symbol: series[symbol][-1].c for symbol in PAIRS}
    end_equity = spot_value(portfolio, final_prices)
    buys = [t for t in trades if t['side'] == 'BUY']
    sells = [t for t in trades if t['side'] == 'SELL']
    gross_buy = sum(t['qty'] * t['price'] for t in buys)
    gross_sell = sum(t['qty'] * t['price'] for t in sells)
    est_fees = (gross_buy + gross_sell) * FEE_RATE
    return {
        'trades': trades,
        'end_equity': end_equity,
        'net_pl': end_equity - INITIAL_USDT,
        'return_pct': (end_equity / INITIAL_USDT - 1) * 100.0,
        'buy_count': len(buys),
        'sell_count': len(sells),
        'signal_counts': dict(signal_counts),
        'portfolio': dict(portfolio),
        'final_prices': final_prices,
        'gross_buy': gross_buy,
        'gross_sell': gross_sell,
        'est_fees_0p1pct': est_fees,
        'skipped_balance': skipped_balance,
    }


if __name__ == '__main__':
    result = run_backtest()
    print('RESULT')
    for k, v in result.items():
        if k == 'trades':
            print(f'{k}={len(v)} rows')
        else:
            print(f'{k}={v}')
