#!/usr/bin/env python3
"""
Auto Strategy Switcher - Production Version
Opt-out system: Switches automatically unless stopped

⚠️ WARNING: This affects REAL trades and REAL money
"""

import json
import httpx
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys
import os

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'trading-bot-tests'))
from intelligent_strategy_switcher_v2 import (
    IntelligentStrategySwitcher, 
    SwitchDecision,
    TEST_DIR
)

# Configuration
SCRIPT_DIR = Path(__file__).parent.parent
STATE_FILE = SCRIPT_DIR / '.strategy_switcher_state.json'
PENDING_FILE = SCRIPT_DIR / '.pending_strategy_switch.json'
NOTIFICATION_COOLDOWN = 300  # 5 min to respond (for 2x daily)

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


class ProductionStrategySwitcher:
    """
    Production-ready strategy switcher with opt-out mechanism
    """
    
    def __init__(self):
        self.switcher = IntelligentStrategySwitcher()
        self.telegram_token = self._load_telegram_token()
        self.telegram_chat_id = self._load_telegram_chat_id()
        self.current_strategy = self._load_current_strategy()
        
        # Safety thresholds
        self.MIN_IMPROVEMENT = 7.0  # 7%
        self.MAX_SWITCHES_PER_WEEK = 1
        self.VOLATILITY_MAX = 5.0  # 5%
        
    def _load_telegram_token(self) -> str:
        """Load from .env file"""
        env_file = SCRIPT_DIR / '.env'
        with open(env_file) as f:
            for line in f:
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    return line.split('=', 1)[1].strip()
        return ''
    
    def _load_telegram_chat_id(self) -> str:
        """Load from .env file"""
        env_file = SCRIPT_DIR / '.env'
        with open(env_file) as f:
            for line in f:
                if line.startswith('TELEGRAM_CHAT_ID='):
                    return line.split('=', 1)[1].strip()
        return ''
    
    def _load_current_strategy(self) -> str:
        """Load current strategy from state file"""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                data = json.load(f)
                return data.get('current_strategy', 'EMA_CROSSOVER')
        return 'EMA_CROSSOVER'
    
    def _save_current_strategy(self, strategy: str):
        """Save current strategy"""
        data = {
            'current_strategy': strategy,
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'switches_this_week': self._get_switches_this_week()
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _get_switches_this_week(self) -> int:
        """Count switches in last 7 days"""
        if not STATE_FILE.exists():
            return 0
        with open(STATE_FILE) as f:
            data = json.load(f)
            last_update = data.get('last_updated', '')
            if last_update:
                last_date = datetime.fromisoformat(last_update)
                days_ago = (datetime.now(timezone.utc) - last_date).days
                if days_ago < 7:
                    return data.get('switches_this_week', 0) + 1
        return 0
    
    def _can_switch(self) -> bool:
        """Check if allowed to switch"""
        switches = self._get_switches_this_week()
        if switches >= self.MAX_SWITCHES_PER_WEEK:
            logger.info(f"Max switches reached this week: {switches}")
            return False
        return True
    
    def _send_telegram_notification(self, message: str, urgent: bool = False):
        """Send notification to Telegram"""
        try:
            emoji = "🚨" if urgent else "📊"
            full_message = f"{emoji} *Auto Strategy Switcher*\n\n{message}"
            
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': full_message,
                'parse_mode': 'Markdown'
            }
            
            response = httpx.post(url, json=payload, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram: {response.text}")
            else:
                logger.info("Telegram notification sent")
                
        except Exception as e:
            logger.error(f"Error sending Telegram: {e}")
    
    def _create_pending_switch(self, target_strategy: str, reason: str, expected_improvement: float):
        """Create pending switch file"""
        data = {
            'proposed_strategy': target_strategy,
            'current_strategy': self.current_strategy,
            'reason': reason,
            'expected_improvement': expected_improvement,
            'proposed_time': datetime.now(timezone.utc).isoformat(),
            'execute_after': (datetime.now(timezone.utc) + timedelta(seconds=NOTIFICATION_COOLDOWN)).isoformat(),
            'status': 'pending'
        }
        
        with open(PENDING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Pending switch created: {self.current_strategy} → {target_strategy}")
    
    def _check_pending_switch(self) -> Optional[Dict]:
        """Check if there's a pending switch that should execute"""
        if not PENDING_FILE.exists():
            return None
        
        try:
            with open(PENDING_FILE) as f:
                data = json.load(f)
            
            if data.get('status') == 'aborted':
                logger.info("Pending switch was aborted")
                PENDING_FILE.unlink()
                return None
            
            execute_time = datetime.fromisoformat(data['execute_after'])
            if datetime.now(timezone.utc) >= execute_time:
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking pending: {e}")
            return None
    
    def _execute_strategy_switch(self, target_strategy: str):
        """Execute the actual strategy switch"""
        try:
            # Update .env file
            env_file = SCRIPT_DIR / '.env'
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Find and update STRATEGY line
            updated = False
            with open(env_file, 'w') as f:
                for line in lines:
                    if line.startswith('STRATEGY='):
                        f.write(f'STRATEGY={target_strategy.lower()}\n')
                        updated = True
                    else:
                        f.write(line)
                
                if not updated:
                    f.write(f'STRATEGY={target_strategy.lower()}\n')
            
            # Update state
            self._save_current_strategy(target_strategy)
            self.current_strategy = target_strategy
            
            # Remove pending file
            if PENDING_FILE.exists():
                PENDING_FILE.unlink()
            
            # Notify
            self._send_telegram_notification(
                f"✅ *STRATEGY SWITCHED*\n\n"
                f"New strategy: *{target_strategy}*\n"
                f"Activated at: {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n\n"
                f"Next analysis in 24h.",
                urgent=False
            )
            
            logger.info(f"Strategy switched to {target_strategy}")
            
        except Exception as e:
            logger.error(f"Failed to execute switch: {e}")
            self._send_telegram_notification(
                f"❌ *SWITCH FAILED*\n\nError: {e}\n\nManual intervention required.",
                urgent=True
            )
    
    def run_analysis(self):
        """Main analysis and decision loop"""
        logger.info("Starting strategy analysis...")
        
        # Check if pending switch should execute
        pending = self._check_pending_switch()
        if pending:
            logger.info(f"Executing pending switch to {pending['proposed_strategy']}")
            self._execute_strategy_switch(pending['proposed_strategy'])
            return
        
        # Check if we can switch
        if not self._can_switch():
            logger.info("Switch limit reached, skipping analysis")
            return
        
        # Run analysis for each pair
        pairs = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'NOMUSDT', 'STOUSDT']
        results = []
        
        for pair in pairs:
            try:
                recommendation = self.switcher.analyze_and_decide(
                    symbol=pair,
                    current_strategy=self.current_strategy
                )
                results.append({
                    'pair': pair,
                    'decision': recommendation.decision.value,
                    'target': recommendation.target_strategy,
                    'improvement': recommendation.expected_improvement
                })
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
        
        # Count recommendations
        switch_count = sum(1 for r in results if r['decision'] == 'switch')
        stay_count = len(results) - switch_count
        
        logger.info(f"Analysis complete: {switch_count} recommend switch, {stay_count} recommend stay")
        
        # Decision logic: Switch if majority says switch AND improvement > threshold
        if switch_count > len(pairs) / 2:
            # Get average improvement
            avg_improvement = sum(r['improvement'] for r in results if r['decision'] == 'switch') / switch_count
            
            if avg_improvement >= self.MIN_IMPROVEMENT:
                # Get most recommended strategy
                from collections import Counter
                targets = [r['target'] for r in results if r['target']]
                if targets:
                    best_strategy = Counter(targets).most_common(1)[0][0]
                    
                    # Create pending switch
                    self._create_pending_switch(
                        target_strategy=best_strategy,
                        reason=f"Majority of pairs ({switch_count}/{len(pairs)}) recommend switch",
                        expected_improvement=avg_improvement
                    )
                    
                    # Send notification
                    execute_time = (datetime.now(timezone.utc) + timedelta(seconds=NOTIFICATION_COOLDOWN))
                    self._send_telegram_notification(
                        f"🚨 *STRATEGY SWITCH PENDING*\n\n"
                        f"Current: *{self.current_strategy}*\n"
                        f"Proposed: *{best_strategy}*\n"
                        f"Expected improvement: *{avg_improvement:.2f}%*\n\n"
                        f"⚠️ Switch will execute automatically at: *{execute_time.strftime('%H:%M UTC')}*\n\n"
                        f"To ABORT, reply: */abort_switch*\n"
                        f"To CONFIRM early, reply: */confirm_switch*\n\n"
                        f"If no response: switch executes automatically.",
                        urgent=True
                    )
                    
                    logger.info(f"Pending switch created: {best_strategy}")
                else:
                    logger.info("No clear target strategy")
            else:
                logger.info(f"Improvement {avg_improvement:.2f}% below threshold {self.MIN_IMPROVEMENT}%")
        else:
            logger.info("Majority recommends staying, no action taken")
    
    def abort_pending_switch(self):
        """Abort a pending switch"""
        if PENDING_FILE.exists():
            with open(PENDING_FILE, 'w') as f:
                json.dump({'status': 'aborted'}, f)
            
            self._send_telegram_notification(
                "✅ *SWITCH ABORTED*\n\nStrategy switch cancelled. Current strategy remains active.",
                urgent=False
            )
            logger.info("Pending switch aborted")
            return True
        return False
    
    def confirm_early(self):
        """Confirm and execute pending switch immediately"""
        pending = self._check_pending_switch()
        if pending:
            self._execute_strategy_switch(pending['proposed_strategy'])
            return True
        return False


def main():
    """Run the auto strategy switcher"""
    print("🤖 Auto Strategy Switcher - Production")
    print("⚠️  This will affect REAL trades")
    print()
    
    switcher = ProductionStrategySwitcher()
    switcher.run_analysis()


if __name__ == '__main__':
    main()
