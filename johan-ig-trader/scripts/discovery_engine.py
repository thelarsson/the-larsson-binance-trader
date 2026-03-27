#!/usr/bin/env python3
"""
Discovery Engine for IG Trading Bot

Scans IG markets for trading opportunities based on combined technical and sentiment analysis.
Ranks opportunities by combined score and provides ranked list to trader.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

# Import sentiment and decision modules
try:
    from sentiment_integration import (
        get_sentiment_for_epic,
        get_all_market_sentiments,
        sentiment_to_trading_score,
    )
    from decision_engine import (
        DecisionEngine,
        TradingSignal,
        Signal,
        TechnicalAnalysis,
    )
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False


# Default IG epics to monitor
DEFAULT_EPICS = [
    "IX.D.DAX.IFG.IP",        # Germany 40 (DAX)
    "IX.D.SPTRD.IFE.IP",      # S&P 500
    "IX.D.NASDAQ.IFE.IP",     # NASDAQ 100
    "IX.D.DOW.IFE.IP",        # Dow Jones
    "CS.D.EURUSD.MINI.IP",    # EUR/USD
    "CS.D.GBPUSD.MINI.IP",    # GBP/USD
    "CS.D.GOLD.CFD.IP",       # Gold
    "CF.D.LCO.USD.IP",        # Brent Oil
]

# Epic metadata
EPIC_INFO = {
    "IX.D.DAX.IFG.IP": {"name": "Germany 40", "type": "index", "region": "Europe"},
    "IX.D.SPTRD.IFE.IP": {"name": "S&P 500", "type": "index", "region": "US"},
    "IX.D.NASDAQ.IFE.IP": {"name": "NASDAQ 100", "type": "index", "region": "US"},
    "IX.D.DOW.IFE.IP": {"name": "Dow Jones", "type": "index", "region": "US"},
    "CS.D.EURUSD.MINI.IP": {"name": "EUR/USD", "type": "forex", "region": "Global"},
    "CS.D.GBPUSD.MINI.IP": {"name": "GBP/USD", "type": "forex", "region": "Global"},
    "CS.D.GOLD.CFD.IP": {"name": "Gold", "type": "commodity", "region": "Global"},
    "CF.D.LCO.USD.IP": {"name": "Brent Oil", "type": "commodity", "region": "Global"},
}


@dataclass
class Opportunity:
    """Represents a trading opportunity."""
    epic: str
    name: str
    combined_score: float
    technical_score: float
    sentiment_score: float
    sentiment_confidence: float
    signal: str
    action: Optional[str]
    reason: str
    urgency: str  # "high", "medium", "low"


class DiscoveryEngine:
    """
    Scans multiple IG markets and ranks them by trading opportunity.
    
    Combines:
    - Technical analysis across multiple timeframes
    - News sentiment strength
    - Market correlation
    """
    
    def __init__(self, epics: List[str] = None, use_sentiment: bool = True):
        self.epics = epics or DEFAULT_EPICS
        self.use_sentiment = use_sentiment and SENTIMENT_AVAILABLE
        self.min_technical_score = 0.15  # Minimum technical strength
        self.min_sentiment_confidence = 0.3
        
    def _get_market_sentiment(self) -> Dict:
        """Get sentiment for all monitored markets."""
        if not self.use_sentiment:
            return {}
        return get_all_market_sentiments()
    
    def _calculate_opportunity_score(
        self, 
        technical_score: float, 
        sentiment_score: float,
        sentiment_confidence: float
    ) -> float:
        """
        Calculate combined opportunity score.
        
        Weights:
        - Technical: 60%
        - Sentiment: 40% (adjusted by confidence)
        """
        # Adjust sentiment weight based on confidence
        adjusted_sentiment = sentiment_score * sentiment_confidence
        
        # Combined score
        combined = technical_score * 0.6 + adjusted_sentiment * 0.4
        
        return combined
    
    def _determine_urgency(
        self, 
        combined_score: float, 
        sentiment_confidence: float,
        technical_score: float
    ) -> str:
        """Determine urgency level of opportunity."""
        if abs(combined_score) > 0.5 and sentiment_confidence > 0.5:
            return "high"
        elif abs(combined_score) > 0.3 or sentiment_confidence > 0.5:
            return "medium"
        return "low"
    
    def analyze_epic(
        self, 
        epic: str, 
        prices: List[Dict],
        sentiment_data: Optional[Dict] = None
    ) -> Optional[Opportunity]:
        """
        Analyze a single epic for trading opportunity.
        
        Args:
            epic: IG epic code
            prices: Price data from IG API
            sentiment_data: Pre-loaded sentiment data
            
        Returns:
            Opportunity if found, None otherwise
        """
        if not prices or len(prices) < 20:
            return None
        
        # Calculate technical indicators
        ta = TechnicalAnalysis()
        indicators = ta.calculate_indicators(prices)
        
        # Get sentiment
        if sentiment_data and epic in sentiment_data:
            sent = sentiment_data[epic]
            sentiment_score = sent.get("signal", 0)
            sentiment_confidence = sent.get("confidence", 0)
            sentiment_action = sent.get("action", "NEUTRAL")
        else:
            sentiment_score = 0
            sentiment_confidence = 0
            sentiment_action = "NEUTRAL"
        
        # Calculate technical score (simplified from decision_engine)
        ema_diff_pct = (indicators.ema_fast - indicators.ema_slow) / indicators.ema_slow if indicators.ema_slow else 0
        
        if ema_diff_pct > 0.005:
            tech_score = min(1.0, ema_diff_pct * 20)
        elif ema_diff_pct < -0.005:
            tech_score = max(-1.0, ema_diff_pct * 20)
        else:
            tech_score = ema_diff_pct * 50
        
        # RSI adjustment
        if indicators.rsi <= 30:
            tech_score = max(tech_score, 0.3)  # Oversold = bullish
        elif indicators.rsi >= 70:
            tech_score = min(tech_score, -0.3)  # Overbought = bearish
        
        # Calculate combined score
        combined = self._calculate_opportunity_score(
            tech_score, sentiment_score, sentiment_confidence
        )
        
        # Determine signal and action
        if combined >= 0.4:
            signal = "STRONG_BUY"
            action = "enter_long"
        elif combined >= 0.15:
            signal = "BUY"
            action = "consider_long"
        elif combined <= -0.4:
            signal = "STRONG_SELL"
            action = "exit_long"  # For CFDs, could also mean short
        elif combined <= -0.15:
            signal = "SELL"
            action = "consider_exit"
        else:
            signal = "NEUTRAL"
            action = None
        
        # Build reason
        reasons = []
        if abs(ema_diff_pct) > 0.005:
            reasons.append(f"EMA diff: {ema_diff_pct:+.2%}")
        if indicators.rsi <= 30 or indicators.rsi >= 70:
            reasons.append(f"RSI: {indicators.rsi:.1f}")
        if sentiment_action != "NEUTRAL":
            reasons.append(f"News: {sentiment_action}")
        
        reason = " | ".join(reasons) if reasons else "No clear signal"
        
        # Determine urgency
        urgency = self._determine_urgency(combined, sentiment_confidence, tech_score)
        
        # Only return opportunities with meaningful signals
        if abs(combined) < self.min_technical_score and sentiment_confidence < self.min_sentiment_confidence:
            return None
        
        info = EPIC_INFO.get(epic, {"name": epic, "type": "unknown", "region": "unknown"})
        
        return Opportunity(
            epic=epic,
            name=info["name"],
            combined_score=combined,
            technical_score=tech_score,
            sentiment_score=sentiment_score,
            sentiment_confidence=sentiment_confidence,
            signal=signal,
            action=action,
            reason=reason,
            urgency=urgency
        )
    
    def scan_markets(
        self, 
        price_fetcher_func,
        max_results: int = 5,
        min_urgency: str = "medium"
    ) -> List[Opportunity]:
        """
        Scan all configured markets for opportunities.
        
        Args:
            price_fetcher_func: Function(epic) -> List[Dict] to fetch prices
            max_results: Maximum number of opportunities to return
            min_urgency: Minimum urgency level to include
            
        Returns:
            List of Opportunity objects, sorted by combined score
        """
        opportunities = []
        sentiment_data = self._get_market_sentiment()
        
        urgency_levels = {"high": 3, "medium": 2, "low": 1}
        min_level = urgency_levels.get(min_urgency, 1)
        
        for epic in self.epics:
            try:
                prices = price_fetcher_func(epic)
                opp = self.analyze_epic(epic, prices, sentiment_data)
                
                if opp and urgency_levels.get(opp.urgency, 0) >= min_level:
                    opportunities.append(opp)
                    
            except Exception as e:
                print(f"Error analyzing {epic}: {e}")
                continue
        
        # Sort by absolute combined score (descending)
        opportunities.sort(key=lambda x: abs(x.combined_score), reverse=True)
        
        return opportunities[:max_results]
    
    def get_recommended_epics(
        self, 
        price_fetcher_func,
        top_n: int = 3
    ) -> List[str]:
        """
        Get list of recommended epics to trade.
        
        Args:
            price_fetcher_func: Function to fetch prices
            top_n: Number of epics to recommend
            
        Returns:
            List of epic codes
        """
        opportunities = self.scan_markets(price_fetcher_func, max_results=top_n)
        return [opp.epic for opp in opportunities if opp.action]
    
    def format_opportunity_report(self, opportunities: List[Opportunity]) -> str:
        """Format opportunities as human-readable report."""
        if not opportunities:
            return "No trading opportunities found."
        
        lines = [
            "=" * 70,
            "🔍 DISCOVERY ENGINE - TOP OPPORTUNITIES",
            "=" * 70,
            "",
        ]
        
        for i, opp in enumerate(opportunities, 1):
            urgency_emoji = {"high": "🔥", "medium": "⚡", "low": "📊"}.get(opp.urgency, "📊")
            
            lines.extend([
                f"{urgency_emoji} #{i}: {opp.name} ({opp.epic})",
                f"   Signal: {opp.signal}",
                f"   Combined: {opp.combined_score:+.3f} | Tech: {opp.technical_score:+.3f} | Sent: {opp.sentiment_score:+.3f}",
                f"   Sentiment Confidence: {opp.sentiment_confidence:.1%}",
                f"   Action: {opp.action or 'HOLD'}",
                f"   Urgency: {opp.urgency.upper()}",
                f"   Reason: {opp.reason}",
                "",
            ])
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def save_opportunities(self, opportunities: List[Opportunity], filepath: Optional[Path] = None):
        """Save opportunities to JSON file."""
        if filepath is None:
            SCRIPT_DIR = Path(__file__).parent
            filepath = SCRIPT_DIR.parent / "data" / "opportunities.json"
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(opportunities),
            "opportunities": [
                {
                    "epic": opp.epic,
                    "name": opp.name,
                    "combined_score": opp.combined_score,
                    "technical_score": opp.technical_score,
                    "sentiment_score": opp.sentiment_score,
                    "sentiment_confidence": opp.sentiment_confidence,
                    "signal": opp.signal,
                    "action": opp.action,
                    "reason": opp.reason,
                    "urgency": opp.urgency,
                }
                for opp in opportunities
            ]
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        return filepath


def demo():
    """Demo the discovery engine with mock data."""
    print("=" * 70)
    print("Discovery Engine Demo")
    print("=" * 70)
    print()
    print("This demonstrates the discovery engine's ranking capabilities.")
    print("In actual use, price_fetcher_func should call IG API.")
    print()
    
    engine = DiscoveryEngine()
    
    # Mock price fetcher for demo
    def mock_price_fetcher(epic):
        import random
        # Generate random price data for demo
        base_price = {
            "IX.D.DAX.IFG.IP": 18500,
            "IX.D.SPTRD.IFE.IP": 5800,
            "IX.D.NASDAQ.IFE.IP": 20500,
            "CS.D.EURUSD.MINI.IP": 1.08,
        }.get(epic, 100)
        
        prices = []
        for i in range(50):
            price = base_price * (1 + random.uniform(-0.02, 0.02))
            prices.append({
                "closePrice": {"bid": price}
            })
        return prices
    
    opportunities = engine.scan_markets(mock_price_fetcher, max_results=5)
    print(engine.format_opportunity_report(opportunities))
    
    return opportunities


if __name__ == "__main__":
    demo()