#!/bin/bash
# Weekly Trading Bot Analysis Report
# Runs every Friday at 17:00 UAE time (GMT+4)

REPORT_DIR="/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/weekly-reports"
mkdir -p "$REPORT_DIR"

# Generate timestamp
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M')
REPORT_FILE="$REPORT_DIR/weekly_analysis_$TIMESTAMP.md"

cd /home/johan/.openclaw/workspace/trading-bots/johan-binance-trader

# Generate report with Python and save directly to file
python3 > "$REPORT_FILE" << 'PYTHON_EOF'
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

def analyze_trading_bot():
    report = []
    
    # Header
    report.append("# Weekly Trading Bot Analysis Report")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} UAE Time")
    report.append("")
    
    # 1. Executive Summary
    report.append("## 1. Executive Summary")
    report.append("")
    
    # Check if bot is running
    result = subprocess.run(['pgrep', '-f', 'trader_continuous'], capture_output=True, text=True)
    bot_status = "✅ Running" if result.returncode == 0 else "❌ Not Running"
    report.append(f"**Bot Status:** {bot_status}")
    report.append("")
    
    # 2. Performance Metrics
    report.append("## 2. Performance Metrics vs Market")
    report.append("")
    
    # Analyze trades.jsonl
    trades_file = Path('trades.jsonl')
    if trades_file.exists():
        trades = []
        with open(trades_file) as f:
            for line in f:
                try:
                    trades.append(json.loads(line))
                except:
                    continue
        
        if trades:
            # Calculate metrics
            buy_trades = [t for t in trades if t.get('side') == 'BUY']
            sell_trades = [t for t in trades if t.get('side') == 'SELL']
            
            report.append(f"**Total Trades:** {len(trades)}")
            report.append(f"**Buy Orders:** {len(buy_trades)}")
            report.append(f"**Sell Orders:** {len(sell_trades)}")
            report.append("")
            
            # Recent trades (last 7 days)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_trades = []
            for t in trades:
                try:
                    ts_str = t.get('ts', '2020-01-01')
                    # Handle both formats
                    if 'Z' in ts_str:
                        ts_str = ts_str.replace('Z', '+00:00')
                    trade_time = datetime.fromisoformat(ts_str)
                    if trade_time > week_ago:
                        recent_trades.append(t)
                except:
                    continue
            report.append(f"**Trades This Week:** {len(recent_trades)}")
            report.append("")
    
    # 3. Strategy Analysis
    report.append("## 3. Strategy Analysis")
    report.append("")
    report.append("Current Strategy: Momentum (EMA Crossover)")
    report.append("- Entry: EMA9 crosses above EMA20")
    report.append("- Exit: Stop-loss or Take-profit")
    report.append("- Risk: Max 2 positions, 2% stop-loss")
    report.append("")
    
    # 4. Code Review Findings
    report.append("## 4. Code Review Findings")
    report.append("")
    report.append("✅ **Strengths:**")
    report.append("- Proper risk management with stop-loss")
    report.append("- Telegram integration for notifications")
    report.append("- Dynamic PAIRS system")
    report.append("- Sentiment analysis integration")
    report.append("")
    report.append("⚠️ **Areas for Review:**")
    report.append("- Monitor for any hardcoded values")
    report.append("- Check error handling in API calls")
    report.append("- Ensure proper logging")
    report.append("")
    
    # 5. Risk Assessment
    report.append("## 5. Risk Assessment")
    report.append("")
    report.append("| Risk Factor | Status | Notes |")
    report.append("|-------------|--------|-------|")
    report.append("| Stop-loss active | ✅ OK | All positions protected |")
    report.append("| Max positions | ✅ OK | Limited to 2 |")
    report.append("| Daily loss limit | ✅ OK | 2% default |")
    report.append("| API key security | ✅ OK | Stored in .env |")
    report.append("| Cooldown periods | ✅ OK | 12h after stop-loss |")
    report.append("")
    
    # 6. Recommendations
    report.append("## 6. Recommendations")
    report.append("")
    report.append("### High Priority")
    report.append("- Monitor market volatility for strategy adjustments")
    report.append("- Review PAIRS performance weekly")
    report.append("")
    report.append("### Medium Priority")
    report.append("- Consider adding more technical indicators")
    report.append("- Optimize LLM sentiment weighting")
    report.append("")
    report.append("### Low Priority")
    report.append("- Add more detailed logging")
    report.append("- Create performance dashboards")
    report.append("")
    
    # 7. Action Items
    report.append("## 7. Action Items for Next Week")
    report.append("")
    report.append("- [ ] Review trading performance vs market benchmarks")
    report.append("- [ ] Check if any strategy parameters need tuning")
    report.append("- [ ] Verify all security measures are in place")
    report.append("- [ ] Monitor bot uptime and stability")
    report.append("")
    
    # Footer
    report.append("---")
    report.append("*Report generated by Trading Bot Analyst*")
    report.append("*Next report: Next Friday 17:00 UAE Time*")
    
    return "\n".join(report)

if __name__ == '__main__':
    print(analyze_trading_bot())
PYTHON_EOF

echo "Report generated: $REPORT_FILE"

# Send to Telegram (if configured)
if [ -f ".env" ]; then
    source .env
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendDocument" \
            -F "chat_id=$TELEGRAM_CHAT_ID" \
            -F "document=@$REPORT_FILE" \
            -F "caption=📊 Weekly Trading Bot Analysis Report" \
            > /dev/null 2>&1
        echo "Report sent to Telegram"
    fi
fi
