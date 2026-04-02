#!/usr/bin/env python3
"""
Weekly Trading Bot Performance Analyzer with LLM
Uses qwen2.5:14b for intelligent analysis
"""

import json
import subprocess
import httpx
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
import statistics

# Configuration
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b"
REPORT_DIR = Path("/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/weekly-reports")
REPORT_DIR.mkdir(exist_ok=True)

def load_env():
    """Load environment variables from .env"""
    env_vars = {}
    env_file = Path("/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    try:
                        k, v = line.strip().split('=', 1)
                        env_vars[k] = v
                    except:
                        pass
    return env_vars

def query_llm(prompt: str, timeout: int = 120) -> str:
    """Query qwen2.5:14b via Ollama"""
    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 8192
                }
            },
            timeout=timeout
        )
        response.raise_for_status()
        return response.json().get("response", "No response from LLM")
    except Exception as e:
        return f"LLM Error: {str(e)}"

def analyze_trades() -> Dict:
    """Analyze trading history"""
    trades_file = Path("/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trades.jsonl")
    
    if not trades_file.exists():
        return {"error": "No trades file found"}
    
    trades = []
    with open(trades_file) as f:
        for line in f:
            try:
                trades.append(json.loads(line.strip()))
            except:
                continue
    
    if not trades:
        return {"error": "No trades recorded"}
    
    # Week analysis
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_trades = [
        t for t in trades 
        if datetime.fromisoformat(t.get('ts', '2020-01-01').replace('Z', '+00:00')) > week_ago
    ]
    
    # Calculate metrics
    buys = [t for t in recent_trades if t.get('side') == 'BUY']
    sells = [t for t in recent_trades if t.get('side') == 'SELL']
    
    # P&L calculation (simplified)
    pnl = 0
    for sell in sells:
        qty = sell.get('qty', 0)
        price = sell.get('price', 0)
        # Find matching buy
        for buy in buys:
            if buy.get('symbol') == sell.get('symbol'):
                buy_price = buy.get('price', 0)
                pnl += (price - buy_price) * qty
                break
    
    return {
        "total_trades": len(trades),
        "weekly_trades": len(recent_trades),
        "weekly_buys": len(buys),
        "weekly_sells": len(sells),
        "estimated_pnl": round(pnl, 2),
        "symbols_traded": list(set(t.get('symbol', '') for t in recent_trades))
    }

def analyze_strategy() -> Dict:
    """Analyze strategy effectiveness"""
    # Read trader log for strategy signals
    log_file = Path("/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trader.log")
    
    signals = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}
    errors = []
    
    if log_file.exists():
        with open(log_file) as f:
            for line in f:
                if 'signal=' in line:
                    if 'BUY' in line:
                        signals["BUY"] += 1
                    elif 'SELL' in line:
                        signals["SELL"] += 1
                    elif 'NEUTRAL' in line:
                        signals["NEUTRAL"] += 1
                if 'ERROR' in line or 'error' in line.lower():
                    errors.append(line.strip()[-100:])  # Last 100 chars
    
    return {
        "signals": signals,
        "recent_errors": errors[-5:] if errors else [],
        "strategy": "momentum",
        "indicators": ["EMA9", "EMA20", "RSI", "Bollinger"]
    }

def check_bot_health() -> Dict:
    """Check if bot is running properly"""
    # Check processes
    result = subprocess.run(['pgrep', '-f', 'trader_continuous'], 
                          capture_output=True, text=True)
    trading_running = result.returncode == 0 and result.stdout.strip()
    
    result = subprocess.run(['pgrep', '-f', 'telegram_bot'], 
                          capture_output=True, text=True)
    telegram_running = result.returncode == 0 and result.stdout.strip()
    
    # Check uptime
    uptime = "Unknown"
    if trading_running:
        pid = result.stdout.strip().split('\n')[0]
        result = subprocess.run(['ps', '-p', pid, '-o', 'etime='], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            uptime = result.stdout.strip()
    
    return {
        "trading_bot": "✅ Running" if trading_running else "❌ Not Running",
        "telegram_bot": "✅ Running" if telegram_running else "❌ Not Running",
        "uptime": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def get_market_data() -> Dict:
    """Get current market data for comparison"""
    try:
        # Get BTC price for benchmark
        r = httpx.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "btc_price": float(data.get('lastPrice', 0)),
                "btc_change_24h": float(data.get('priceChangePercent', 0)),
                "btc_volume": float(data.get('quoteVolume', 0))
            }
    except:
        pass
    return {"error": "Could not fetch market data"}

def generate_llm_prompt(trade_data: Dict, strategy_data: Dict, 
                       health_data: Dict, market_data: Dict) -> str:
    """Generate prompt for LLM analysis"""
    
    prompt = f"""You are an expert cryptocurrency trading analyst. Review this trading bot's weekly performance and provide strategic insights.

## Trading Bot Weekly Performance Report

### Week: {datetime.now().strftime('%Y-%m-%d')}

### Trading Statistics
- Total Trades (All Time): {trade_data.get('total_trades', 'N/A')}
- Trades This Week: {trade_data.get('weekly_trades', 'N/A')}
- Buy Orders: {trade_data.get('weekly_buys', 'N/A')}
- Sell Orders: {trade_data.get('weekly_sells', 'N/A')}
- Estimated P&L: ${trade_data.get('estimated_pnl', 'N/A')}
- Symbols Traded: {', '.join(trade_data.get('symbols_traded', []))}

### Strategy Performance
- Strategy: {strategy_data.get('strategy', 'N/A')}
- Indicators Used: {', '.join(strategy_data.get('indicators', []))}
- Signal Distribution: {strategy_data.get('signals', {})}
- Recent Errors: {len(strategy_data.get('recent_errors', []))}

### Bot Health
- Trading Bot: {health_data.get('trading_bot', 'N/A')}
- Telegram Bot: {health_data.get('telegram_bot', 'N/A')}
- Uptime: {health_data.get('uptime', 'N/A')}

### Market Context
{json.dumps(market_data, indent=2)}

### Your Task
Please provide a comprehensive analysis covering:

1. **Performance Assessment**: How did the bot perform this week vs market benchmarks?

2. **Strategy Effectiveness**: Is the momentum strategy working? Any patterns?

3. **Risk Management**: Are stop-losses and position limits being respected?

4. **Technical Observations**: Any bugs, issues, or optimization opportunities?

5. **Strategic Recommendations**: What should be adjusted? (PAIRS, thresholds, strategy?)

6. **Code Quality**: Any potential improvements to the codebase?

7. **Action Items**: Priority list for next week

Format your response as a professional trading analysis report. Be specific, data-driven, and actionable."""
    
    return prompt

def generate_report(llm_analysis: str, trade_data: Dict, strategy_data: Dict,
                   health_data: Dict, market_data: Dict) -> str:
    """Generate final markdown report"""
    
    report = f"""# 📊 Weekly Trading Bot Analysis Report

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UAE Time  
**Analyzed by:** qwen2.5:14b LLM  
**Period:** Last 7 days

---

## 📈 Executive Summary

| Metric | Value |
|--------|-------|
| Bot Status | {health_data.get('trading_bot', 'Unknown')} |
| Uptime | {health_data.get('uptime', 'Unknown')} |
| Weekly Trades | {trade_data.get('weekly_trades', 0)} |
| Estimated P&L | ${trade_data.get('estimated_pnl', 0)} |
| Active Symbols | {len(trade_data.get('symbols_traded', []))} |

---

## 🤖 LLM Analysis

{llm_analysis}

---

## 📋 Technical Details

### Trading Activity
```
Total Trades: {trade_data.get('total_trades', 'N/A')}
This Week: {trade_data.get('weekly_trades', 'N/A')}
Buys: {trade_data.get('weekly_buys', 'N/A')}
Sells: {trade_data.get('weekly_sells', 'N/A')}
```

### Strategy Configuration
- **Primary Strategy:** {strategy_data.get('strategy', 'N/A')}
- **Indicators:** {', '.join(strategy_data.get('indicators', []))}
- **Signal Distribution:** {strategy_data.get('signals', {})}

### System Health
- Trading Bot: {health_data.get('trading_bot', 'N/A')}
- Telegram Bot: {health_data.get('telegram_bot', 'N/A')}
- Last Check: {health_data.get('timestamp', 'N/A')}

---

## 💡 Recommendations Summary

*See LLM analysis above for detailed recommendations*

---

## 📅 Next Report

**Scheduled:** Next Friday 17:00 UAE Time

---

*This report was automatically generated by the Trading Bot Analysis System*  
*Model: qwen2.5:14b running locally on RTX 4070 Super*
"""
    
    return report

def send_to_telegram(report: str, env_vars: Dict, pdf_path: Optional[Path] = None):
    """Send report to Telegram as PDF"""
    token = env_vars.get('TELEGRAM_BOT_TOKEN')
    chat_id = env_vars.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("⚠️ Telegram credentials not found")
        return False
    
    # Save markdown report to file
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
    report_file = REPORT_DIR / f"weekly_analysis_{timestamp}.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    # Generate PDF
    print("📄 Converting to PDF...")
    pdf_file = REPORT_DIR / f"weekly_analysis_{timestamp}.pdf"
    
    try:
        # Use LibreOffice to convert MD to PDF
        result = subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'pdf',
            '--outdir', str(REPORT_DIR), str(report_file)
        ], capture_output=True, text=True, timeout=60)
        
        # Check if PDF was created
        if result.returncode == 0 and pdf_file.exists():
            pdf_path = pdf_file
        else:
            # Fallback: try pandoc
            result = subprocess.run([
                'pandoc', str(report_file), '-o', str(pdf_file),
                '--pdf-engine=pdflatex'
            ], capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and pdf_file.exists():
                pdf_path = pdf_file
            else:
                print("⚠️ PDF generation failed, sending as text")
                pdf_path = None
    except Exception as e:
        print(f"⚠️ PDF generation error: {e}")
        pdf_path = None
    
    # Send to Telegram
    try:
        if pdf_path and pdf_path.exists():
            # Send as document
            with open(pdf_path, 'rb') as f:
                files = {'document': ('Weekly_Trading_Analysis.pdf', f, 'application/pdf')}
                data = {
                    'chat_id': chat_id,
                    'caption': f'📊 Weekly Trading Bot Analysis\nGenerated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC\nModel: qwen2.5:14b'
                }
                response = httpx.post(
                    f"https://api.telegram.org/bot{token}/sendDocument",
                    data=data,
                    files=files,
                    timeout=60
                )
        else:
            # Fallback to text (truncated)
            text_report = report[:4000] + "\n\n[Full report saved locally]"
            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text_report,
                    "parse_mode": "Markdown"
                },
                timeout=30
            )
        
        response.raise_for_status()
        print(f"✅ Report sent to Telegram")
        return True
    except Exception as e:
        print(f"❌ Failed to send Telegram: {e}")
        return False

def main():
    """Main analysis routine"""
    print("=" * 60)
    print("🤖 Weekly Trading Bot Analysis - LLM Powered")
    print("=" * 60)
    print(f"Model: {OLLAMA_MODEL}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("")
    
    # Load environment
    env_vars = load_env()
    print("✅ Environment loaded")
    
    # Gather data
    print("📊 Analyzing trades...")
    trade_data = analyze_trades()
    
    print("📈 Analyzing strategy...")
    strategy_data = analyze_strategy()
    
    print("🔍 Checking bot health...")
    health_data = check_bot_health()
    
    print("📡 Fetching market data...")
    market_data = get_market_data()
    
    # Generate LLM prompt
    print("🤖 Preparing LLM analysis...")
    prompt = generate_llm_prompt(trade_data, strategy_data, health_data, market_data)
    
    # Query LLM
    print(f"⏳ Querying {OLLAMA_MODEL}... (this may take 1-2 minutes)")
    llm_analysis = query_llm(prompt)
    
    if llm_analysis.startswith("LLM Error"):
        print(f"❌ {llm_analysis}")
        llm_analysis = "LLM analysis failed. See technical details below."
    else:
        print("✅ LLM analysis complete")
    
    # Generate report
    print("📝 Generating report...")
    report = generate_report(llm_analysis, trade_data, strategy_data, 
                             health_data, market_data)
    
    # Send to Telegram
    print("📤 Sending to Telegram (as PDF)...")
    success = send_to_telegram(report, env_vars)
    
    # Save locally
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
    report_file = REPORT_DIR / f"weekly_analysis_{timestamp}.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print("")
    print("=" * 60)
    print(f"✅ Analysis complete!")
    print(f"📄 Report saved: {report_file}")
    if success:
        print("📤 Sent to Telegram: @TheLarssonBot")
    print("=" * 60)

if __name__ == '__main__':
    main()
