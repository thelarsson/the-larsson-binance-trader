#!/usr/bin/env python3
"""
Auto-discovery integration for trader.py

This module:
1. Runs discovery scan periodically
2. Suggests new pairs to add to PAIRS
3. Updates environment dynamically

Add to trader.py:

```python
from auto_discovery import check_for_new_pairs, get_discovered_pairs

# In run() before trading loop:
new_pairs = check_for_new_pairs(PAIRS)
if new_pairs:
    log.info(f"🔍 Discovery: New opportunities found: {new_pairs}")
    # Optionally auto-add or just log
```
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# Import discovery engine
try:
    from discovery_engine import DiscoveryEngine, CoinOpportunity, format_discovery_report
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False

# Configuration
DISCOVERY_MIN_SCORE = float(os.getenv("DISCOVERY_MIN_SCORE", "0.3"))  # Minimum combined score
DISCOVERY_MAX_NEW = int(os.getenv("DISCOVERY_MAX_NEW", "3"))  # Max new pairs to suggest
DISCOVERY_AUTO_ADD = os.getenv("DISCOVERY_AUTO_ADD", "false").lower() == "true"
DISCOVERY_CACHE_HOURS = int(os.getenv("DISCOVERY_CACHE_HOURS", "1"))  # Cache duration

DISCOVERY_FILE = Path("/home/johan/.openclaw/workspace/crypto-news-scraper/discovery_report.json")


def get_cached_discovery() -> Optional[Dict]:
    """Get cached discovery report if fresh."""
    if not DISCOVERY_FILE.exists():
        return None
    
    try:
        with open(DISCOVERY_FILE) as f:
            data = json.load(f)
        
        # Check age
        ts_str = data.get("timestamp")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age < timedelta(hours=DISCOVERY_CACHE_HOURS):
                return data
        
        return None
    except Exception:
        return None


def run_discovery(current_pairs: List[str] = None, force: bool = False) -> Dict:
    """
    Run discovery scan.
    
    Args:
        current_pairs: Currently trading pairs
        force: Force fresh scan even if cached
        
    Returns:
        Discovery report dict
    """
    if not DISCOVERY_AVAILABLE:
        return {"error": "Discovery engine not available"}
    
    # Check cache first
    if not force:
        cached = get_cached_discovery()
        if cached:
            return cached
    
    # Run fresh discovery
    engine = DiscoveryEngine()
    try:
        opportunities = engine.discover(current_pairs)
        recommendations = engine.get_recommendations(
            opportunities,
            max_recommendations=10,
            exclude_current=False,
            current_pairs=current_pairs
        )
        
        # Build report
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_pairs": current_pairs or [],
            "opportunities": [
                {
                    "symbol": o.symbol,
                    "base_asset": o.base_asset,
                    "price": o.price,
                    "combined_score": o.combined_score,
                    "signal": o.signal,
                    "news_mentions": o.news_mentions,
                    "news_sentiment": o.news_sentiment,
                    "source": o.source,
                    "reason": o.reason
                }
                for o in opportunities[:20]  # Top 20
            ],
            "recommendations": [o.symbol for o in recommendations],
            "new_pairs_to_add": [
                o.symbol for o in recommendations 
                if o.signal in ["BUY", "STRONG_BUY"] 
                and o.combined_score >= DISCOVERY_MIN_SCORE
                and o.symbol not in (current_pairs or [])
            ]
        }
        
        # Save cache
        try:
            with open(DISCOVERY_FILE, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass  # Non-critical if cache fails
        
        return report
        
    finally:
        engine.close()


def check_for_new_pairs(current_pairs: List[str]) -> List[str]:
    """
    Check for new trading opportunities.
    
    Args:
        current_pairs: Currently trading pairs (from PAIRS env)
        
    Returns:
        List of suggested new pairs to add
    """
    if not DISCOVERY_AVAILABLE:
        return []
    
    report = run_discovery(current_pairs)
    
    if "error" in report:
        return []
    
    new_pairs = report.get("new_pairs_to_add", [])
    
    # Limit to max new pairs
    return new_pairs[:DISCOVERY_MAX_NEW]


def get_discovered_pairs(min_score: float = None) -> List[Dict]:
    """
    Get all discovered pairs with scores above threshold.
    
    Args:
        min_score: Minimum combined score (default from env)
        
    Returns:
        List of opportunity dicts
    """
    min_score = min_score or DISCOVERY_MIN_SCORE
    
    cached = get_cached_discovery()
    if not cached:
        return []
    
    return [
        opp for opp in cached.get("opportunities", [])
        if abs(opp.get("combined_score", 0)) >= min_score
    ]


def get_pair_opportunity(symbol: str) -> Optional[Dict]:
    """
    Get opportunity data for a specific pair.
    
    Args:
        symbol: Trading pair symbol
        
    Returns:
        Opportunity dict or None
    """
    cached = get_cached_discovery()
    if not cached:
        return None
    
    for opp in cached.get("opportunities", []):
        if opp.get("symbol") == symbol:
            return opp
    
    return None


def format_discovery_summary(report: Dict) -> str:
    """Format a brief discovery summary for logging."""
    if "error" in report:
        return f"Discovery error: {report['error']}"
    
    lines = [
        f"Discovery scan: {len(report.get('opportunities', []))} pairs analyzed",
    ]
    
    new_pairs = report.get("new_pairs_to_add", [])
    if new_pairs:
        lines.append(f"New opportunities: {', '.join(new_pairs)}")
    
    recommendations = report.get("recommendations", [])[:3]
    if recommendations:
        lines.append(f"Top picks: {', '.join(recommendations)}")
    
    return " | ".join(lines)


def auto_update_pairs(current_pairs: List[str]) -> List[str]:
    """
    Auto-update PAIRS list if enabled.
    
    Args:
        current_pairs: Currently trading pairs
        
    Returns:
        Updated pairs list (or original if not enabled)
    """
    if not DISCOVERY_AUTO_ADD:
        return current_pairs
    
    new_pairs = check_for_new_pairs(current_pairs)
    
    if not new_pairs:
        return current_pairs
    
    updated = list(current_pairs) + new_pairs
    
    # Optionally write to .env
    # This would require restarting the trader
    # For now, just return the updated list
    
    return updated


# CLI
if __name__ == "__main__":
    import sys
    
    current = sys.argv[1:] if len(sys.argv) > 1 else ["BTCUSDT", "ETHUSDT"]
    
    print(f"Current pairs: {current}")
    print()
    
    # Run discovery
    report = run_discovery(current)
    
    if "error" in report:
        print(f"Error: {report['error']}")
        sys.exit(1)
    
    print(format_discovery_summary(report))
    print()
    
    # Show new pairs
    new_pairs = report.get("new_pairs_to_add", [])
    if new_pairs:
        print("🆕 NEW PAIRS TO ADD:")
        for pair in new_pairs:
            print(f"   - {pair}")
        print()
        print(f"Add to PAIRS: {','.join(current + new_pairs)}")
    else:
        print("No new pairs to add.")
    
    # Show top opportunities
    print()
    print("📊 TOP OPPORTUNITIES:")
    for opp in report.get("opportunities", [])[:5]:
        score_emoji = "🟢" if opp["combined_score"] > 0.2 else "🔴" if opp["combined_score"] < -0.2 else "🟡"
        print(f"   {score_emoji} {opp['symbol']}: {opp['combined_score']:+.3f} ({opp['signal']})")
        if opp.get("news_mentions", 0) > 0:
            print(f"      News: {opp['news_mentions']}x {opp['news_sentiment']}")