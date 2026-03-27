#!/usr/bin/env python3
"""
IG News Scraper - Financial News Sentiment Analysis for IG Markets

Scrapes financial news from multiple sources and generates sentiment signals
for DAX, S&P 500, NASDAQ, EUR/USD, and commodities.

Uses agent-browser for headless scraping.
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import time

# Configuration
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Output files
SENTIMENT_FILE = DATA_DIR / "news_sentiment.json"
REPORT_FILE = DATA_DIR / "news_sentiment_report.json"

# IG Market keywords and their associated epics
MARKET_KEYWORDS = {
    "DAX": ["DAX", "Germany 40", "German stocks", "Deutsche Börse", "XETRA"],
    "SP500": ["S&P 500", "SPX", "S&P", "US stocks", "Wall Street", "Dow", "S&P500"],
    "NASDAQ": ["NASDAQ", "NASDAQ 100", "tech stocks", "NDX", "QQQ", "technology"],
    "EURUSD": ["EUR/USD", "EURUSD", "Euro dollar", "EUR USD", "Euro", "ECB", "Fed"],
    "GOLD": ["Gold", "XAU/USD", "XAUUSD", "precious metals", "bullion"],
    "OIL": ["Oil", "Brent", "WTI", "Crude", "petroleum", "energy"],
}

# Epic mapping for IG
EPIC_MAP = {
    "DAX": "IX.D.DAX.IFG.IP",
    "SP500": "IX.D.SPTRD.IFE.IP",
    "NASDAQ": "IX.D.NASDAQ.IFE.IP",
    "EURUSD": "CS.D.EURUSD.MINI.IP",
    "GOLD": "CS.D.GOLD.CFD.IP",
    "OIL": "CF.D.LCO.USD.IP",
}

# Bullish keywords for financial markets
BULLISH_KEYWORDS = [
    "rally", "surge", "strong", "breakout", "support", "bullish", "buy", "demand",
    "gain", "rise", "climb", "jump", "soar", "upside", "recovery", "rebound",
    "higher", "upward", "optimistic", "positive", "beat", "exceed", "growth",
    "expansion", "upbeat", "bull run", "momentum", "buying", "accumulation",
]

# Bearish keywords for financial markets
BEARISH_KEYWORDS = [
    "sell-off", "correction", "bearish", "resistance", "weak", "recession", "cut rates",
    "fall", "drop", "decline", "crash", "plunge", "tumble", "slide", "downside",
    "lower", "downward", "pessimistic", "negative", "miss", "below", "contraction",
    "downturn", "bear market", "selling", "distribution", "volatility", "fear",
    "inflation", "deflation", "stagflation", "unemployment", "crisis", "risk-off",
]

# IG-specific contextual keywords
CONTEXT_KEYWORDS = [
    "ECB", "Fed", "inflation", "GDP", "earnings", "geopolitical",
    "interest rates", "monetary policy", "fiscal policy", "unemployment",
    "PMI", "manufacturing", "services", "retail sales", "consumer confidence",
    "trade war", "sanctions", "brexit", "EU", "US", "China", "Japan",
]


@dataclass
class NewsArticle:
    """Represents a scraped news article."""
    title: str
    summary: str
    source: str
    timestamp: str
    url: str = ""


def run_agent_browser_command(cmd: List[str], timeout: int = 30) -> Optional[Dict]:
    """Run agent-browser command and return JSON output."""
    try:
        full_cmd = ["agent-browser"] + cmd
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            print(f"agent-browser error: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print(f"Command timed out: {' '.join(cmd)}")
        return None
    except Exception as e:
        print(f"Error running agent-browser: {e}")
        return None


def scrape_investing_com() -> List[NewsArticle]:
    """Scrape financial news from Investing.com."""
    articles = []
    
    # Navigate to Investing.com indices section
    urls = [
        "https://www.investing.com/indices/",
        "https://www.investing.com/currencies/",
        "https://www.investing.com/commodities/",
    ]
    
    for url in urls:
        try:
            print(f"Scraping: {url}")
            
            # Open page
            subprocess.run(["agent-browser", "open", url], capture_output=True, timeout=30)
            time.sleep(2)
            
            # Get snapshot
            result = subprocess.run(
                ["agent-browser", "snapshot", "-i", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                continue
            
            data = json.loads(result.stdout)
            snapshot_text = data.get("data", {}).get("snapshot", "")
            
            # Parse news headlines from the snapshot
            # Investing.com typically has headlines in links or headings
            lines = snapshot_text.split("\n")
            
            current_article = None
            for line in lines:
                # Look for headlines (usually contain market keywords)
                line_lower = line.lower()
                has_market_keyword = any(
                    kw.lower() in line_lower 
                    for kws in MARKET_KEYWORDS.values() 
                    for kw in kws
                )
                
                if has_market_keyword and len(line) > 30:
                    article = NewsArticle(
                        title=line.strip(),
                        summary="",
                        source="investing.com",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        url=url
                    )
                    articles.append(article)
                    
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    
    print(f"Scraped {len(articles)} articles from Investing.com")
    return articles[:20]  # Limit to top 20


def scrape_yahoo_finance() -> List[NewsArticle]:
    """Scrape financial news from Yahoo Finance."""
    articles = []
    
    urls = [
        "https://finance.yahoo.com/topic/stock-market-news/",
        "https://finance.yahoo.com/topic/earnings/",
        "https://finance.yahoo.com/currencies/",
        "https://finance.yahoo.com/commodities/",
    ]
    
    for url in urls:
        try:
            print(f"Scraping: {url}")
            
            subprocess.run(["agent-browser", "open", url], capture_output=True, timeout=30)
            time.sleep(2)
            
            result = subprocess.run(
                ["agent-browser", "snapshot", "-i", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                continue
            
            data = json.loads(result.stdout)
            snapshot_text = data.get("data", {}).get("snapshot", "")
            
            # Parse headlines
            lines = snapshot_text.split("\n")
            for line in lines:
                line_lower = line.lower()
                has_market_keyword = any(
                    kw.lower() in line_lower 
                    for kws in MARKET_KEYWORDS.values() 
                    for kw in kws
                )
                
                if has_market_keyword and len(line) > 30 and len(line) < 200:
                    article = NewsArticle(
                        title=line.strip(),
                        summary="",
                        source="yahoo_finance",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        url=url
                    )
                    articles.append(article)
                    
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    
    print(f"Scraped {len(articles)} articles from Yahoo Finance")
    return articles[:20]


def scrape_marketwatch() -> List[NewsArticle]:
    """Scrape financial news from MarketWatch."""
    articles = []
    
    urls = [
        "https://www.marketwatch.com/investing",
        "https://www.marketwatch.com/economy-politics",
        "https://www.marketwatch.com/currencies",
    ]
    
    for url in urls:
        try:
            print(f"Scraping: {url}")
            
            subprocess.run(["agent-browser", "open", url], capture_output=True, timeout=30)
            time.sleep(2)
            
            result = subprocess.run(
                ["agent-browser", "snapshot", "-i", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                continue
            
            data = json.loads(result.stdout)
            snapshot_text = data.get("data", {}).get("snapshot", "")
            
            lines = snapshot_text.split("\n")
            for line in lines:
                line_lower = line.lower()
                has_market_keyword = any(
                    kw.lower() in line_lower 
                    for kws in MARKET_KEYWORDS.values() 
                    for kw in kws
                )
                
                if has_market_keyword and len(line) > 30:
                    article = NewsArticle(
                        title=line.strip(),
                        summary="",
                        source="marketwatch",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        url=url
                    )
                    articles.append(article)
                    
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    
    print(f"Scraped {len(articles)} articles from MarketWatch")
    return articles[:20]


def analyze_sentiment(articles: List[NewsArticle]) -> Dict:
    """
    Analyze sentiment of articles.
    
    Returns dict with:
    - overall_signal: -1 to 1
    - confidence: 0 to 1
    - market_signals: dict of signals per market
    - key_signals: list of key signals found
    """
    if not articles:
        return {
            "signal": 0,
            "confidence": 0,
            "action": "NEUTRAL",
            "key_signals": [],
            "articles_analyzed": 0,
            "market_signals": {},
        }
    
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    key_signals_found = []
    
    # Market-specific tracking
    market_articles = {market: {"bullish": 0, "bearish": 0, "neutral": 0, "mentions": 0} 
                       for market in MARKET_KEYWORDS.keys()}
    
    for article in articles:
        title_lower = article.title.lower()
        
        # Check which markets this article mentions
        markets_mentioned = []
        for market, keywords in MARKET_KEYWORDS.items():
            if any(kw.lower() in title_lower for kw in keywords):
                markets_mentioned.append(market)
                market_articles[market]["mentions"] += 1
        
        # Count sentiment keywords
        bull_score = 0
        bear_score = 0
        
        for kw in BULLISH_KEYWORDS:
            if kw.lower() in title_lower:
                bull_score += 1
                if kw not in key_signals_found:
                    key_signals_found.append(kw)
        
        for kw in BEARISH_KEYWORDS:
            if kw.lower() in title_lower:
                bear_score += 1
                if kw not in key_signals_found:
                    key_signals_found.append(kw)
        
        # Classify article sentiment
        if bull_score > bear_score:
            bullish_count += 1
            for market in markets_mentioned:
                market_articles[market]["bullish"] += 1
        elif bear_score > bull_score:
            bearish_count += 1
            for market in markets_mentioned:
                market_articles[market]["bearish"] += 1
        else:
            neutral_count += 1
            for market in markets_mentioned:
                market_articles[market]["neutral"] += 1
    
    total_classified = bullish_count + bearish_count
    total = len(articles)
    
    # Calculate overall signal (-1 to 1)
    if total_classified > 0:
        bullish_pct = bullish_count / total_classified
        bearish_pct = bearish_count / total_classified
        signal = bullish_pct - bearish_pct  # Range: -1 to 1
    else:
        signal = 0
    
    # Confidence based on article count and classification rate
    classified_ratio = total_classified / total if total > 0 else 0
    confidence = min(1.0, (total / 50) * 0.5 + classified_ratio * 0.5)
    
    # Determine action
    if signal > 0.3:
        action = "BULLISH"
    elif signal < -0.3:
        action = "BEARISH"
    else:
        action = "NEUTRAL"
    
    # Calculate market-specific signals
    market_signals = {}
    for market, data in market_articles.items():
        if data["mentions"] > 0:
            market_total = data["bullish"] + data["bearish"]
            if market_total > 0:
                market_signal = (data["bullish"] - data["bearish"]) / market_total
                market_signals[market] = {
                    "signal": round(market_signal, 3),
                    "epic": EPIC_MAP.get(market, ""),
                    "bullish": data["bullish"],
                    "bearish": data["bearish"],
                    "mentions": data["mentions"],
                    "action": "BULLISH" if market_signal > 0.2 else "BEARISH" if market_signal < -0.2 else "NEUTRAL",
                }
    
    return {
        "signal": round(signal, 3),
        "confidence": round(confidence, 2),
        "action": action,
        "key_signals": key_signals_found[:10],
        "articles_analyzed": total,
        "breakdown": {
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": neutral_count,
        },
        "market_signals": market_signals,
    }


def generate_report(articles: List[NewsArticle], sentiment: Dict) -> Dict:
    """Generate detailed sentiment report."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_sentiment": sentiment["action"],
            "strength": abs(sentiment["signal"]),
            "confidence": sentiment["confidence"],
            "articles_total": sentiment["articles_analyzed"],
            "breakdown": sentiment["breakdown"],
            "top_signals": sentiment["key_signals"],
        },
        "market_analysis": sentiment["market_signals"],
        "recent_headlines": [
            {"title": a.title, "source": a.source, "ts": a.timestamp}
            for a in articles[:10]
        ],
    }


def save_sentiment_files(sentiment: Dict, report: Dict):
    """Save sentiment data to files."""
    # Save trading signal
    with open(SENTIMENT_FILE, "w") as f:
        json.dump(sentiment, f, indent=2)
    print(f"Saved sentiment signal to {SENTIMENT_FILE}")
    
    # Save full report
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved report to {REPORT_FILE}")


def main():
    """Main scraping routine."""
    print("=" * 60)
    print("📰 IG Markets News Scraper")
    print("=" * 60)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    all_articles = []
    
    # Scrape from multiple sources
    print("🔍 Scraping news sources...")
    
    try:
        articles = scrape_investing_com()
        all_articles.extend(articles)
    except Exception as e:
        print(f"Investing.com scraping failed: {e}")
    
    try:
        articles = scrape_yahoo_finance()
        all_articles.extend(articles)
    except Exception as e:
        print(f"Yahoo Finance scraping failed: {e}")
    
    try:
        articles = scrape_marketwatch()
        all_articles.extend(articles)
    except Exception as e:
        print(f"MarketWatch scraping failed: {e}")
    
    print()
    print(f"📊 Total articles collected: {len(all_articles)}")
    
    if not all_articles:
        print("❌ No articles found. Using fallback data.")
        # Create neutral sentiment as fallback
        sentiment = {
            "signal": 0,
            "confidence": 0,
            "action": "NEUTRAL",
            "key_signals": [],
            "articles_analyzed": 0,
            "breakdown": {"bullish": 0, "bearish": 0, "neutral": 0},
            "market_signals": {},
        }
        report = generate_report([], sentiment)
    else:
        # Analyze sentiment
        print("🧠 Analyzing sentiment...")
        sentiment = analyze_sentiment(all_articles)
        report = generate_report(all_articles, sentiment)
    
    # Save results
    save_sentiment_files(sentiment, report)
    
    # Print summary
    print()
    print("=" * 60)
    print("📈 SENTIMENT ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Signal: {sentiment['signal']:+.3f}")
    print(f"Action: {sentiment['action']}")
    print(f"Confidence: {sentiment['confidence']:.1%}")
    print(f"Articles analyzed: {sentiment['articles_analyzed']}")
    print(f"Key signals: {', '.join(sentiment['key_signals'][:5])}")
    print()
    print("Market-specific signals:")
    for market, data in sentiment.get("market_signals", {}).items():
        print(f"  {market}: {data['signal']:+.3f} ({data['action']}) - Epic: {data['epic']}")
    print()
    
    # Close browser session
    try:
        subprocess.run(["agent-browser", "close"], capture_output=True, timeout=10)
    except:
        pass
    
    print("✅ Scraping complete!")
    return sentiment


if __name__ == "__main__":
    main()