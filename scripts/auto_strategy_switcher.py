#!/usr/bin/env python3
"""
Auto Strategy Switcher - WITH EXECUTE FUNCTION
Production Version with Execute Function - IMPLEMENTED
"""

import json
import httpx
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import statistics

# Configuration
SCRIPT_DIR = Path(__file__).parent.parent
STATE_FILE = SCRIPT_DIR / '.strategy_switcher_state.json'
PENDING_FILE = SCRIPT_DIR / '.pending_strategy_switch.json'
ABORT_FILE = SCRIPT_DIR / '.abort_switch_requested'
NOTIFICATION_COOLDOWN = 300  # 5 min to respond

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - AutoSwitcher - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(SCRIPT_DIR / 'auto_strategy_switcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AutoStrategySwitcher')

# Binance API
BINANCE_API = "https://api.binance.com"


class TechnicalIndicators:
    """Technical indicators for analysis"""
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return prices
        multiplier = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]
        for price in prices[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return [prices[0]] * (period - 1) + ema
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        rsi_values = [50.0] * len(prices)
        for i in range(period, len(deltas)):
            gains = [d for d in deltas[i-period+1:i+1] if d > 0]
            losses = [-d for d in deltas[i-period+1:i+1] if d < 0]
            avg_gain = sum(gains) / period if gains else 0
            avg_loss = sum(losses) / period if losses else 0.0001
            rs = avg_gain / avg_loss
            rsi_values[i+1] = 100 - (100 / (1 + rs))
        return rsi_values


class MarketAnalyzer:
    """Analyzes market conditions"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def analyze_conditions(self, data: List[Dict]) -> Dict:
        if len(data) < 50:
            return {'error': 'Insufficient data'}
        prices = [d['close'] for d in data]
        gains = [max(0, prices[-i] - prices[-i-1]) for i in range(1, min(15, len(prices)))]
        losses = [max(0, prices[-i-1] - prices[-i]) for i in range(1, min(15, len(prices)))]
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0.0001
        trend_strength = avg_gain / avg_loss
        ranges = [d['high'] - d['low'] for d in data[-20:]]
        avg_range = sum(ranges) / len(ranges)
        avg_price = sum(prices[-20:]) / 20
        volatility = (avg_range / avg_price) * 100
        rsi_values = self.indicators.calculate_rsi(prices)
        return {
            'trend_strength': trend_strength,
            'volatility': volatility,
            'rsi': rsi_values[-1],
            'current_price': prices[-1]
        }


class StrategyBacktester:
    """Backtests strategies"""
    
    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.indicators = TechnicalIndicators()
    
    def backtest_ema_crossover(self, data: List[Dict]):
        prices = [d['close'] for d in data]
        if len(prices) < 30:
            return {'name': 'EMA_CROSSOVER', 'return_pct': 0, 'trades': 0, 'win_rate': 0}
        ema_fast = self.indicators.calculate_ema(prices, 9)
        ema_slow = self.indicators.calculate_ema(prices, 20)
        capital = self.initial_capital
        position = 0
        trades = 0
        wins = 0
        for i in range(1, len(prices)):
            price = prices[i]
            if ema_fast[i-1] <= ema_slow[i-1] and ema_fast[i] > ema_slow[i]:
                if position == 0:
                    position = capital / price
                    capital = 0
            elif position > 0:
                capital = position * price
                position = 0
                trades += 1
                if price > prices[i-1]:
                    wins += 1
        final = capital if position == 0 else position * prices[-1]
        return {
            'name': 'EMA_CROSSOVER',
            'return_pct': (final - self.initial_capital) / self.initial_capital * 100,
            'trades': trades,
            'win_rate': (wins / trades * 100) if trades > 0 else 0
        }
    
    def backtest_rsi_strategy(self, data: List[Dict]):
        prices = [d['close'] for d in data]
        if len(prices) < 20:
            return {'name': 'RSI_STRATEGY', 'return_pct': 0, 'trades': 0, 'win_rate': 0}
        rsi = self.indicators.calculate_rsi(prices, 14)
        capital = self.initial_capital
        position = 0
        trades = 0
        wins = 0
        for i in range(15, len(prices)):
            price = prices[i]
            if rsi[i] < 40 and position == 0:  # Lowered from 30
                position = capital / price
                capital = 0
            elif position > 0:
                capital = position * price
                position = 0
                trades += 1
                if price > prices[i-1]:
                    wins += 1
        final = capital if position == 0 else position * prices[-1]
        return {
            'name': 'RSI_STRATEGY',
            'return_pct': (final - self.initial_capital) / self.initial_capital * 100,
            'trades': trades,
            'win_rate': (wins / trades * 100) if trades > 0 else 0
        }


class AutoStrategySwitcher:
    """Main auto strategy switcher WITH EXECUTE"""
    
    def __init__(self):
        self.analyzer = MarketAnalyzer()
        self.backtester = StrategyBacktester()
        self.telegram_token = self._load_telegram_token()
        self.telegram_chat_id = self._load_telegram_chat_id()
        self.current_strategy = self._load_current_strategy()
        self.MIN_IMPROVEMENT = 3.0  # Lowered from 7.0 to allow more frequent switches
        self.MAX_SWITCHES_PER_3_DAYS = 1
    
    def _load_telegram_token(self) -> str:
        env_file = SCRIPT_DIR / '.env'
        with open(env_file) as f:
            for line in f:
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    return line.split('=', 1)[1].strip()
        return ''
    
    def _load_telegram_chat_id(self) -> str:
        env_file = SCRIPT_DIR / '.env'
        with open(env_file) as f:
            for line in f:
                if line.startswith('TELEGRAM_CHAT_ID='):
                    return line.split('=', 1)[1].strip()
        return ''
    
    def _load_current_strategy(self) -> str:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                data = json.load(f)
                return data.get('current_strategy', 'EMA_CROSSOVER')
        return 'EMA_CROSSOVER'
    
    def _save_state(self, strategy: str):
        """Save current strategy state"""
        data = {
            'current_strategy': strategy,
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'switches_last_3_days': self._get_switches_last_3_days() + 1
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"State saved: {strategy}")
    
    def _get_switches_last_3_days(self) -> int:
        if not STATE_FILE.exists():
            return 0
        with open(STATE_FILE) as f:
            data = json.load(f)
            last_update = data.get('last_updated', '')
            if last_update:
                last_date = datetime.fromisoformat(last_update)
                days_ago = (datetime.now(timezone.utc) - last_date).days
                if days_ago < 7:
                    return data.get('switches_last_3_days', 0)
        return 0
    
    def _can_switch(self) -> bool:
        switches = self._get_switches_last_3_days()
        if switches >= self.MAX_SWITCHES_PER_3_DAYS:
            logger.info(f"Max switches reached: {switches}")
            return False
        return True
    
    def _save_pending_switch(self, target_strategy: str, improvement: float):
        """Save pending switch to file"""
        data = {
            'proposed_strategy': target_strategy,
            'current_strategy': self.current_strategy,
            'execute_after': (datetime.now(timezone.utc) + timedelta(seconds=NOTIFICATION_COOLDOWN)).isoformat(),
            'status': 'pending',
            'expected_improvement': improvement
        }
        with open(PENDING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Pending switch saved: {target_strategy}")
    
    def _check_pending_switch(self) -> Optional[Dict]:
        """Check if there's a pending switch that should execute"""
        if not PENDING_FILE.exists():
            return None
        try:
            with open(PENDING_FILE) as f:
                data = json.load(f)
            
            if data.get('status') == 'aborted':
                PENDING_FILE.unlink()
                return None
            
            execute_time = datetime.fromisoformat(data['execute_after'])
            if datetime.now(timezone.utc) >= execute_time:
                return data
            return None
        except Exception as e:
            logger.error(f"Error checking pending: {e}")
            return None
    
    def _check_abort(self) -> bool:
        """Check if abort was requested"""
        if ABORT_FILE.exists():
            ABORT_FILE.unlink()
            return True
        return False
    
    def _execute_switch(self, target_strategy: str):
        """Execute the actual strategy switch"""
        try:
            # Update .env file
            env_file = SCRIPT_DIR / '.env'
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            updated = False
            with open(env_file, 'w') as f:
                for line in lines:
                    if line.startswith('STRATEGY='):
                        f.write(f'STRATEGY={target_strategy.lower().replace("_strategy", "")}\n')
                        updated = True
                        logger.info(f"Updated .env: STRATEGY={target_strategy}")
                    else:
                        f.write(line)
            
            # Save state
            self._save_state(target_strategy)
            self.current_strategy = target_strategy
            
            # Remove pending file
            if PENDING_FILE.exists():
                PENDING_FILE.unlink()
            
            # Send confirmation
            self._send_telegram(
                f"✅ *STRATEGY SWITCHED*\n\n"
                f"New strategy: *{target_strategy}*\n"
                f"Activated at: {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n"
                f"Next analysis in 12 hours."
            )
            
            logger.info(f"Switch executed: {target_strategy}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute switch: {e}")
            self._send_telegram(f"❌ *SWITCH FAILED*\n\nError: {e}")
            return False
    
    def _send_telegram(self, message: str):
        """Send Telegram notification"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {'chat_id': self.telegram_chat_id, 'text': message, 'parse_mode': 'Markdown'}
            httpx.post(url, json=payload, timeout=30)
        except Exception as e:
            logger.error(f"Telegram error: {e}")
    
    def _fetch_data(self, symbol: str = 'BTCUSDT', limit: int = 500) -> List[Dict]:
        try:
            url = f"{BINANCE_API}/api/v3/klines"
            params = {'symbol': symbol, 'interval': '1h', 'limit': limit}
            response = httpx.get(url, params=params, timeout=30)
            data = response.json()
            candles = []
            for d in data:
                candles.append({
                    'timestamp': datetime.fromtimestamp(d[0] / 1000, tz=timezone.utc),
                    'open': float(d[1]), 'high': float(d[2]),
                    'low': float(d[3]), 'close': float(d[4]),
                    'volume': float(d[5])
                })
            return candles
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return []
    
    def run_analysis(self):
        """Main analysis with EXECUTE logic"""
        logger.info("Starting strategy analysis...")
        
        # STEP 1: Check for pending switches first
        pending = self._check_pending_switch()
        if pending:
            logger.info(f"Found pending switch to {pending['proposed_strategy']}")
            
            # Check for abort
            if self._check_abort():
                logger.info("Switch aborted by user")
                pending['status'] = 'aborted'
                with open(PENDING_FILE, 'w') as f:
                    json.dump(pending, f)
                self._send_telegram("❌ Switch aborted by user. Current strategy remains.")
                return
            
            # Execute the switch
            if self._execute_switch(pending['proposed_strategy']):
                logger.info("Switch executed successfully")
            return
        
        # STEP 2: Check if we can switch
        if not self._can_switch():
            from datetime import datetime
            now = datetime.now(timezone.utc)
            # Next analysis at 08:00 or 20:00 UTC
            if now.hour < 8:
                next_analysis = "08:00 UTC today"
            elif now.hour < 20:
                next_analysis = "20:00 UTC today"
            else:
                next_analysis = "08:00 UTC tomorrow"
            self._send_telegram(
                "📊 *Strategy Analysis*\n\n"
                f"Current: *{self.current_strategy}*\n"
                "Status: Max switches reached (1 per 3 days)\n"
                f"Next analysis: {next_analysis}"
            )
            return
        
        # STEP 3: Run new analysis - Use PAIRS from .env
        # Load PAIRS from environment or .env file
        env_pairs = os.getenv('PAIRS', 'BTCUSDT,ETHUSDT')
        pairs = [p.strip() for p in env_pairs.split(',') if p.strip()][:5]  # Limit to 5 pairs for performance
        
        if not pairs:
            pairs = ['BTCUSDT', 'ETHUSDT']  # Fallback
        
        logger.info(f"Analyzing {len(pairs)} pairs: {', '.join(pairs[:3])}{'...' if len(pairs) > 3 else ''}")
        results = []
        
        for pair in pairs:
            data = self._fetch_data(pair, limit=500)
            if not data:
                continue
            ema = self.backtester.backtest_ema_crossover(data)
            rsi = self.backtester.backtest_rsi_strategy(data)
            results.append({'pair': pair, 'ema': ema, 'rsi': rsi})
        
        # Calculate totals
        ema_total = sum(r['ema']['return_pct'] for r in results)
        rsi_total = sum(r['rsi']['return_pct'] for r in results)
        
        # Determine best
        best_strategy = 'EMA_CROSSOVER'
        best_return = ema_total
        if rsi_total > best_return:
            best_strategy = 'RSI_STRATEGY'
            best_return = rsi_total
        
        improvement = best_return - ema_total if self.current_strategy == 'EMA_CROSSOVER' else 0
        
        # STEP 4: Decide and act
        if improvement >= self.MIN_IMPROVEMENT and best_strategy != self.current_strategy:
            # Save pending and notify
            self._save_pending_switch(best_strategy, improvement)
            self._send_telegram(
                f"🚨 *STRATEGY SWITCH PENDING*\n\n"
                f"Current: *{self.current_strategy}*\n"
                f"Proposed: *{best_strategy}*\n"
                f"Expected: *{improvement:.2f}%*\n\n"
                f"⚠️ Auto-switch in 5 minutes!\n"
                f"Reply */abort_switch* to cancel"
            )
        else:
            self._send_telegram(
                f"📊 *Strategy Analysis*\n\n"
                f"Current: *{self.current_strategy}*\n"
                f"Status: *STAY*\n\n"
                f"EMA: {ema_total:+.2f}%\n"
                f"RSI: {rsi_total:+.2f}%\n\n"
                f"Improvement too small. Next: 12h."
            )
        
        logger.info(f"Analysis complete. Best: {best_strategy}")


def main():
    switcher = AutoStrategySwitcher()
    switcher.run_analysis()


if __name__ == '__main__':
    main()
