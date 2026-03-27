#!/usr/bin/env python3
"""
Currency Discovery Engine
Combines news sentiment with market scanning to discover trading opportunities.

Features:
- Extracts coin tickers from news headlines
- Fetches top coins by volume from Binance
- Runs technical analysis on each
- Combines news sentiment + technical analysis
- Ranks opportunities and suggests new pairs
"""

import json
import re
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import Counter

# Import existing modules
try:
    from decision_engine import DecisionEngine, Signal, TechnicalAnalysis
    from sentiment_integration import get_sentiment_report
    DECISION_ENGINE_AVAILABLE = True
except ImportError:
    DECISION_ENGINE_AVAILABLE = False

# Configuration
TOP_COINS_LIMIT = int(50)  # How many top coins to scan
MIN_VOLUME_USDT = 10_000_000  # Minimum 24h volume to consider
MIN_SIGNAL_STRENGTH = 0.2  # Minimum signal strength to recommend
EXCLUDED_COINS = {"USDT", "BUSD", "USDC", "DAI", "TUSD", "FDUSD"}  # Stablecoins to exclude
KNOWN_PAIRS = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", 
               "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT", "TONUSDT"}


@dataclass
class CoinOpportunity:
    """Represents a trading opportunity."""
    symbol: str
    base_asset: str
    price: float
    price_change_24h: float
    volume_24h: float
    technical_score: float
    sentiment_score: float
    combined_score: float
    signal: str
    news_mentions: int
    news_sentiment: str
    source: str  # "news", "volume", "both"
    reason: str


class BinanceScanner:
    """Scan Binance for top trading pairs."""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self):
        self.client = httpx.Client(timeout=15)
    
    def get_top_by_volume(self, limit: int = 50, quote_asset: str = "USDT") -> List[Dict]:
        """Get top trading pairs by 24h volume."""
        try:
            r = self.client.get(f"{self.BASE_URL}/api/v3/ticker/24hr")
            r.raise_for_status()
            data = r.json()
            
            # Filter to USDT pairs with sufficient volume
            pairs = []
            for ticker in data:
                symbol = ticker.get("symbol", "")
                if not symbol.endswith(quote_asset):
                    continue
                
                base = symbol.replace(quote_asset, "")
                if base in EXCLUDED_COINS:
                    continue
                
                volume = float(ticker.get("quoteVolume", 0))
                if volume < MIN_VOLUME_USDT:
                    continue
                
                pairs.append({
                    "symbol": symbol,
                    "base_asset": base,
                    "price": float(ticker.get("lastPrice", 0)),
                    "price_change": float(ticker.get("priceChangePercent", 0)),
                    "volume": volume,
                    "count": int(ticker.get("count", 0))
                })
            
            # Sort by volume
            pairs.sort(key=lambda x: x["volume"], reverse=True)
            return pairs[:limit]
            
        except Exception as e:
            print(f"Error fetching top pairs: {e}")
            return []
    
    def get_exchange_info(self) -> Dict:
        """Get exchange info for all symbols."""
        try:
            r = self.client.get(f"{self.BASE_URL}/api/v3/exchangeInfo")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"Error fetching exchange info: {e}")
            return {}
    
    def close(self):
        self.client.close()


class NewsCoinExtractor:
    """Extract coin mentions from news sentiment reports."""
    
    # Common crypto tickers and names
    COIN_PATTERNS = {
        "BTC": ["bitcoin", "btc"],
        "ETH": ["ethereum", "ether", "eth"],
        "SOL": ["solana", "sol"],
        "XRP": ["ripple", "xrp"],
        "BNB": ["binance coin", "bnb"],
        "ADA": ["cardano", "ada"],
        "DOGE": ["dogecoin", "doge"],
        "AVAX": ["avalanche", "avax"],
        "LINK": ["chainlink", "link"],
        "DOT": ["polkadot", "dot"],
        "MATIC": ["polygon", "matic"],
        "TON": ["toncoin", "ton"],
        "SHIB": ["shiba inu", "shib"],
        "LTC": ["litecoin", "ltc"],
        "ATOM": ["cosmos", "atom"],
        "UNI": ["uniswap", "uni"],
        "NEAR": ["near protocol", "near"],
        "APT": ["aptos", "apt"],
        "ARB": ["arbitrum", "arb"],
        "OP": ["optimism", "op"],
        "INJ": ["injective", "inj"],
        "TIA": ["celestia", "tia"],
        "SEI": ["sei"],
        "SUI": ["sui"],
        "FET": ["fetch.ai", "fetai", "fet"],
        "TAO": ["bittensor", "tao"],
        "HYPE": ["hyperliquid", "hype"],
        "CRV": ["curve", "crv"],
        "XMR": ["monero", "xmr"],
        "CRO": ["cronos", "cro"],
    }
    
    def extract_coins(self, headlines: List[str]) -> Dict[str, Dict]:
        """Extract coin mentions from headlines with sentiment context."""
        mentions = {}
        
        for headline in headlines:
            headline_lower = headline.lower()
            
            for ticker, patterns in self.COIN_PATTERNS.items():
                for pattern in patterns:
                    # Use word boundary matching
                    if re.search(rf'\b{re.escape(pattern)}\b', headline_lower):
                        if ticker not in mentions:
                            mentions[ticker] = {
                                "count": 0,
                                "headlines": [],
                                "sentiments": []
                            }
                        mentions[ticker]["count"] += 1
                        mentions[ticker]["headlines"].append(headline[:100])
                        
                        # Detect sentiment from headline
                        bullish_words = ["surge", "rally", "gain", "rise", "bullish", "breakout", 
                                        "bottom", "rebound", "buy", "accumulate"]
                        bearish_words = ["crash", "dump", "sell", "bearish", "decline", 
                                        "drop", "fall", "plunge", "hacked"]
                        
                        sentiment = "NEUTRAL"
                        if any(w in headline_lower for w in bullish_words):
                            sentiment = "BULLISH"
                        elif any(w in headline_lower for w in bearish_words):
                            sentiment = "BEARISH"
                        
                        mentions[ticker]["sentiments"].append(sentiment)
        
        return mentions
    
    def get_news_mentions(self) -> Dict[str, Dict]:
        """Get coin mentions from latest news sentiment report."""
        if not DECISION_ENGINE_AVAILABLE:
            return {}
        
        report = get_sentiment_report(max_age_hours=6)
        if not report:
            return {}
        
        articles = report.get("articles", [])
        headlines = [a.get("headline", "") for a in articles]
        
        return self.extract_coins(headlines)


class DiscoveryEngine:
    """
    Main discovery engine combining news and market scanning.
    
    Scans for:
    1. Top coins by volume with technical analysis
    2. Coins mentioned in news with sentiment
    3. Cross-references to find best opportunities
    """
    
    def __init__(self):
        self.scanner = BinanceScanner()
        self.news_extractor = NewsCoinExtractor()
        self.ta = TechnicalAnalysis() if DECISION_ENGINE_AVAILABLE else None
    
    def discover(self, current_pairs: List[str] = None) -> List[CoinOpportunity]:
        """
        Run full discovery scan.
        
        Args:
            current_pairs: List of currently trading pairs (to mark as "new")
            
        Returns:
            List of CoinOpportunity sorted by combined_score
        """
        current_pairs = set(current_pairs or KNOWN_PAIRS)
        opportunities = []
        
        # 1. Get top coins by volume
        print("📊 Scanning top coins by volume...")
        top_pairs = self.scanner.get_top_by_volume(TOP_COINS_LIMIT)
        print(f"   Found {len(top_pairs)} pairs with volume > ${MIN_VOLUME_USDT:,.0f}")
        
        # 2. Get news mentions
        print("📰 Extracting coin mentions from news...")
        news_mentions = self.news_extractor.get_news_mentions()
        print(f"   Found {len(news_mentions)} coins in news")
        
        # 3. Analyze each top pair
        print("🔍 Analyzing opportunities...")
        for pair_data in top_pairs:
            symbol = pair_data["symbol"]
            base_asset = pair_data["base_asset"]
            
            # Skip if we can't analyze
            if not DECISION_ENGINE_AVAILABLE or not self.ta:
                # Use volume ranking as proxy
                opp = CoinOpportunity(
                    symbol=symbol,
                    base_asset=base_asset,
                    price=pair_data["price"],
                    price_change_24h=pair_data["price_change"],
                    volume_24h=pair_data["volume"],
                    technical_score=0,
                    sentiment_score=0,
                    combined_score=pair_data["volume"] / 1e9,  # Normalize by billions
                    signal="SCAN",
                    news_mentions=news_mentions.get(base_asset, {}).get("count", 0),
                    news_sentiment=news_mentions.get(base_asset, {}).get("sentiments", ["NEUTRAL"])[0] if base_asset in news_mentions else "NEUTRAL",
                    source="volume" if base_asset not in news_mentions else "both",
                    reason=f"Top {len(opportunities)+1} by volume"
                )
                opportunities.append(opp)
                continue
            
            # Run technical analysis
            try:
                engine = DecisionEngine(symbol)
                signal = engine.analyze("1h")
                engine.close()
                
                technical_score = signal.technical_score
                signal_name = signal.signal.name
                
            except Exception as e:
                technical_score = 0
                signal_name = "ERROR"
            
            # Get news sentiment
            news_data = news_mentions.get(base_asset, {"count": 0, "sentiments": ["NEUTRAL"]})
            news_count = news_data["count"]
            news_sentiments = news_data.get("sentiments", ["NEUTRAL"])
            
            # Calculate news sentiment score (-1 to 1)
            sentiment_map = {"BULLISH": 1, "BEARISH": -1, "NEUTRAL": 0}
            news_sentiment_values = [sentiment_map.get(s, 0) for s in news_sentiments]
            sentiment_score = sum(news_sentiment_values) / max(1, len(news_sentiment_values)) if news_sentiment_values else 0
            
            # Combine scores (60% technical, 40% sentiment if news exists)
            if news_count > 0:
                combined_score = technical_score * 0.6 + sentiment_score * 0.4
                source = "both"
            else:
                combined_score = technical_score
                source = "volume"
            
            # Determine if new opportunity
            is_new = symbol not in current_pairs
            
            # Build reason
            reasons = []
            if signal_name in ["BUY", "STRONG_BUY"]:
                reasons.append(f"Technical: {signal_name}")
            if news_count > 0:
                dominant_sentiment = Counter(news_sentiments).most_common(1)[0][0]
                reasons.append(f"News: {news_count}x {dominant_sentiment}")
            if is_new:
                reasons.append("🆕 NEW PAIR")
            if pair_data["volume"] > 100_000_000:
                reasons.append(f"High volume: ${pair_data['volume']/1e9:.1f}B")
            
            reason = " | ".join(reasons) if reasons else f"Volume rank #{len(opportunities)+1}"
            
            opp = CoinOpportunity(
                symbol=symbol,
                base_asset=base_asset,
                price=pair_data["price"],
                price_change_24h=pair_data["price_change"],
                volume_24h=pair_data["volume"],
                technical_score=technical_score,
                sentiment_score=sentiment_score,
                combined_score=combined_score,
                signal=signal_name,
                news_mentions=news_count,
                news_sentiment=Counter(news_sentiments).most_common(1)[0][0] if news_sentiments else "NEUTRAL",
                source=source,
                reason=reason
            )
            opportunities.append(opp)
        
        # Sort by combined score (descending)
        opportunities.sort(key=lambda x: x.combined_score, reverse=True)
        
        return opportunities
    
    def get_recommendations(self, opportunities: List[CoinOpportunity], 
                           max_recommendations: int = 10,
                           exclude_current: bool = False,
                           current_pairs: List[str] = None) -> List[CoinOpportunity]:
        """
        Get top recommendations.
        
        Args:
            opportunities: List of all opportunities
            max_recommendations: Max number to return
            exclude_current: Exclude pairs already being traded
            current_pairs: List of current trading pairs
            
        Returns:
            Filtered list of top opportunities
        """
        current_set = set(current_pairs or KNOWN_PAIRS)
        
        filtered = []
        for opp in opportunities:
            # Skip if below threshold
            if abs(opp.combined_score) < MIN_SIGNAL_STRENGTH:
                continue
            
            # Skip if excluding current and this is current
            if exclude_current and opp.symbol in current_set:
                continue
            
            filtered.append(opp)
            
            if len(filtered) >= max_recommendations:
                break
        
        return filtered
    
    def close(self):
        self.scanner.close()


def format_discovery_report(opportunities: List[CoinOpportunity], 
                            recommendations: List[CoinOpportunity],
                            current_pairs: List[str] = None) -> str:
    """Format discovery results as readable report."""
    current_set = set(current_pairs or KNOWN_PAIRS)
    
    lines = [
        "=" * 70,
        "🔍 CURRENCY DISCOVERY REPORT",
        f"   Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 70,
        "",
        f"📊 Scanned: {len(opportunities)} pairs",
        f"📰 Current pairs: {', '.join(current_set) if current_set else 'None'}",
        "",
        "─" * 70,
        "🎯 TOP RECOMMENDATIONS",
        "─" * 70,
    ]
    
    if not recommendations:
        lines.append("   No strong opportunities found at this time.")
    else:
        for i, opp in enumerate(recommendations, 1):
            new_flag = "🆕" if opp.symbol not in current_set else "  "
            signal_emoji = {"STRONG_BUY": "🟢🟢", "BUY": "🟢", "NEUTRAL": "🟡", 
                           "SELL": "🔴", "STRONG_SELL": "🔴🔴", "ERROR": "⚪"}.get(opp.signal, "⚪")
            
            lines.append(f"{i}. {new_flag} {opp.symbol} {signal_emoji}")
            lines.append(f"      Price: ${opp.price:,.4f} ({opp.price_change_24h:+.2f}%)")
            lines.append(f"      Score: {opp.combined_score:+.3f} | Tech: {opp.technical_score:+.3f} | Sent: {opp.sentiment_score:+.3f}")
            lines.append(f"      News: {opp.news_mentions}x mentions ({opp.news_sentiment})")
            lines.append(f"      Reason: {opp.reason}")
            lines.append("")
    
    # News highlights
    lines.extend([
        "─" * 70,
        "📰 NEWS HIGHLIGHTS",
        "─" * 70,
    ])
    
    news_coins = [o for o in opportunities if o.news_mentions > 0]
    news_coins.sort(key=lambda x: x.news_mentions, reverse=True)
    
    if not news_coins:
        lines.append("   No coins mentioned in recent news.")
    else:
        for opp in news_coins[:5]:
            new_flag = "🆕" if opp.symbol not in current_set else "  "
            lines.append(f"   {new_flag} {opp.base_asset}: {opp.news_mentions}x ({opp.news_sentiment}) - {opp.reason}")
    
    # Volume leaders
    lines.extend([
        "",
        "─" * 70,
        "📈 VOLUME LEADERS",
        "─" * 70,
    ])
    
    volume_leaders = sorted(opportunities, key=lambda x: x.volume_24h, reverse=True)[:5]
    for opp in volume_leaders:
        new_flag = "🆕" if opp.symbol not in current_set else "  "
        lines.append(f"   {new_flag} {opp.symbol}: ${opp.volume_24h/1e9:.2f}B ({opp.price_change_24h:+.2f}%)")
    
    # Actionable items
    lines.extend([
        "",
        "─" * 70,
        "⚡ ACTIONABLE ITEMS",
        "─" * 70,
    ])
    
    new_buys = [o for o in recommendations if o.signal in ["BUY", "STRONG_BUY"] and o.symbol not in current_set]
    if new_buys:
        pairs_to_add = [o.symbol for o in new_buys[:3]]
        lines.append(f"   Add to PAIRS: {', '.join(pairs_to_add)}")
    else:
        lines.append("   No new pairs to add based on current signals.")
    
    strong_signals = [o for o in recommendations if o.combined_score > 0.3]
    if strong_signals:
        lines.append(f"   Strong buy signals: {', '.join([o.symbol for o in strong_signals])}")
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


# Main execution
if __name__ == "__main__":
    import sys
    
    # Parse current pairs from env or args
    current_pairs = sys.argv[1:] if len(sys.argv) > 1 else list(KNOWN_PAIRS)
    
    print(f"\n🔍 Discovering opportunities...\n")
    print(f"   Current pairs: {', '.join(current_pairs)}\n")
    
    engine = DiscoveryEngine()
    try:
        opportunities = engine.discover(current_pairs)
        recommendations = engine.get_recommendations(
            opportunities, 
            max_recommendations=10,
            exclude_current=False,
            current_pairs=current_pairs
        )
        
        report = format_discovery_report(opportunities, recommendations, current_pairs)
        print(report)
        
        # Save to JSON
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_pairs": current_pairs,
            "opportunities": [
                {
                    "symbol": o.symbol,
                    "base_asset": o.base_asset,
                    "price": o.price,
                    "price_change_24h": o.price_change_24h,
                    "volume_24h": o.volume_24h,
                    "technical_score": o.technical_score,
                    "sentiment_score": o.sentiment_score,
                    "combined_score": o.combined_score,
                    "signal": o.signal,
                    "news_mentions": o.news_mentions,
                    "news_sentiment": o.news_sentiment,
                    "source": o.source,
                    "reason": o.reason
                }
                for o in opportunities
            ],
            "recommendations": [o.symbol for o in recommendations],
            "new_pairs_to_add": [o.symbol for o in recommendations if o.signal in ["BUY", "STRONG_BUY"] and o.symbol not in current_pairs]
        }
        
        output_path = Path(__file__).parent / "discovery_report.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Report saved to {output_path}")
        
    finally:
        engine.close()