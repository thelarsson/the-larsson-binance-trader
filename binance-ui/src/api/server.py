#!/usr/bin/env python3
"""
Binance Trader UI - API Server
Read-only access to trading bot data
ZERO risk to trader operation
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
import threading
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Configuration - READ-ONLY paths
LOG_PATH = os.getenv('BOT_LOG_PATH', '/app/data/logs')
DATA_PATH = os.getenv('BOT_DATA_PATH', '/app/data/bot')

class LogParser:
    """Parse trading bot logs - read only"""
    
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.cache = {}
        self.last_update = 0
        
    def _read_log_file(self, filename: str) -> str:
        """Read log file (read-only)"""
        try:
            filepath = self.log_path / filename
            # If file doesn't exist, try alternative names
            if not filepath.exists():
                # Try common variations
                alternatives = [
                    'trader_restart.log',
                    'trader.log', 
                    'trader_continuous.log'
                ]
                for alt in alternatives:
                    alt_path = self.log_path / alt
                    if alt_path.exists():
                        filepath = alt_path
                        break
                else:
                    return ""
                
            # SECURITY: Read-only, never write
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            app.logger.error(f"Error reading {filename}: {e}")
            return ""
            
    def parse_trader_log(self, lines: int = 100) -> list:
        """Parse latest trader.py log entries"""
        content = self._read_log_file('trader.log')
        if not content:
            return []
            
        entries = []
        log_lines = content.split('\n')[-lines:]
        
        for line in log_lines:
            # Parse log format: 2026-04-11 10:22:05,850 [INFO] BTCUSDT: price=$72724.00 signal=HOLD
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[(\w+)\] (.*)', line)
            if match:
                timestamp, level, message = match.groups()
                
                # Parse trade signals
                signal_match = re.search(r'(\w+USDT):.*signal=(\w+)', message)
                if signal_match:
                    symbol, signal = signal_match.groups()
                    
                    # Parse price
                    price_match = re.search(r'price=\$([\d.]+)', message)
                    price = float(price_match.group(1)) if price_match else 0
                    
                    entries.append({
                        'timestamp': timestamp,
                        'level': level,
                        'symbol': symbol,
                        'signal': signal,
                        'price': price,
                        'message': message
                    })
                    
        return entries[-50:]  # Last 50 entries
        
    def parse_balance(self) -> dict:
        """Parse USDT balance from logs"""
        content = self._read_log_file('trader.log')
        
        # Find latest balance
        matches = re.findall(r'USDT balance: \$([\d.]+)', content)
        if matches:
            return {
                'usdt_balance': float(matches[-1]),
                'last_updated': datetime.now().isoformat()
            }
        return {'usdt_balance': 0, 'last_updated': None}
        
    def parse_positions(self) -> list:
        """Parse current positions from logs"""
        content = self._read_log_file('trader.log')
        positions = []
        
        # Find position entries
        pos_matches = re.findall(r'(\w+USDT):.*signal=(\w+).*avg_entry=\$([\d.]+)', content)
        seen = set()
        
        for symbol, signal, avg_entry in reversed(pos_matches):
            if symbol not in seen:
                seen.add(symbol)
                positions.append({
                    'symbol': symbol,
                    'signal': signal,
                    'avg_entry': float(avg_entry),
                    'current_price': 0  # Will be updated from latest price
                })
                
        return positions[:10]  # Top 10 positions
        
    def parse_trades(self, hours: int = 24) -> list:
        """Parse completed trades from all log files"""
        # Try both trader.log and trader_restart.log
        content = self._read_log_file('trader.log')
        if not content:
            content = self._read_log_file('trader_restart.log')
        
        trades = []
        
        # Format: 2026-04-05 00:00:19,281 [INFO] ORDER SELL: STOUSDT qty=367.5 -> FILLED
        # Simpler pattern without newlines
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*ORDER (BUY|SELL): (\w+) qty=([\d.]+) -> FILLED'
        
        for line in content.split('\n'):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                timestamp, side, symbol, qty = match.groups()
                trades.append({
                    'timestamp': timestamp,
                    'side': side.upper(),
                    'symbol': symbol,
                    'quantity': float(qty),
                    'status': 'FILLED'
                })
            
        return trades[-20:]  # Last 20

# Initialize parser
parser = LogParser(LOG_PATH)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'log_path_accessible': Path(LOG_PATH).exists()
    })

@app.route('/api/status')
def get_status():
    """Get current bot status"""
    balance = parser.parse_balance()
    recent_activity = parser.parse_trader_log(20)
    
    return jsonify({
        'status': 'active' if recent_activity else 'no_data',
        'usdt_balance': balance.get('usdt_balance', 0),
        'last_update': balance.get('last_updated'),
        'recent_signals': len([e for e in recent_activity if e.get('signal')]),
        'latest_activity': recent_activity[-1] if recent_activity else None,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/positions')
def get_positions():
    """Get current positions"""
    positions = parser.parse_positions()
    balance = parser.parse_balance()
    
    return jsonify({
        'positions': positions,
        'count': len(positions),
        'usdt_available': balance.get('usdt_balance', 0),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/trades')
def get_trades():
    """Get recent trades"""
    trades = parser.parse_trades(hours=24)
    
    return jsonify({
        'trades': trades,
        'count_24h': len(trades),
        'buy_count': len([t for t in trades if t['side'] == 'BUY']),
        'sell_count': len([t for t in trades if t['side'] == 'SELL']),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/signals')
def get_signals():
    """Get recent trading signals"""
    signals = parser.parse_trader_log(100)
    
    # Group by symbol
    by_symbol = {}
    for signal in signals:
        sym = signal.get('symbol')
        if sym:
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(signal)
            
    return jsonify({
        'signals': signals[-20:],  # Last 20
        'by_symbol': by_symbol,
        'signal_types': list(set(s['signal'] for s in signals if s.get('signal'))),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/profit')
def get_profit():
    """Calculate profit/loss (approximate from trades)"""
    trades = parser.parse_trades(hours=168)  # 7 days
    
    # Simple PnL calculation
    buy_volume = sum(t['quantity'] for t in trades if t['side'] == 'BUY')
    sell_volume = sum(t['quantity'] for t in trades if t['side'] == 'SELL')
    
    return jsonify({
        'period': '7d',
        'total_trades': len(trades),
        'buy_trades': len([t for t in trades if t['side'] == 'BUY']),
        'sell_trades': len([t for t in trades if t['side'] == 'SELL']),
        'buy_volume': buy_volume,
        'sell_volume': sell_volume,
        'net_volume': sell_volume - buy_volume,
        'note': 'Approximate - requires price data for accurate PnL',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/logs/recent')
def get_recent_logs():
    """Get recent log entries"""
    logs = parser.parse_trader_log(50)
    return jsonify({
        'logs': logs,
        'count': len(logs),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🚀 Binance Trader UI API Starting")
    print(f"   Log path: {LOG_PATH}")
    print(f"   Data path: {DATA_PATH}")
    print(f"   Mode: READ-ONLY (zero risk to trader)")
    print()
    
    # Run on localhost:5000
    app.run(host='0.0.0.0', port=5000, debug=False)
