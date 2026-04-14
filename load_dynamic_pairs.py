#!/usr/bin/env python3
"""
Dynamic PAIRS loader for Binance Trader
Loads pairs from discovery system and updates .env
"""

import os
from pathlib import Path

def load_dynamic_pairs():
    """Load dynamic pairs from discovery system"""
    try:
        dynamic_file = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/dynamic_PAIRS.txt')
        if dynamic_file.exists():
            with open(dynamic_file, 'r') as f:
                content = f.read().strip()
                if content:
                    return [p.strip() for p in content.split(',') if p.strip()]
    except Exception as e:
        print(f"Warning: Could not load dynamic pairs: {e}")
    return []

def update_pairs_in_env():
    """Update PAIRS in .env file with dynamic pairs"""
    env_file = Path('.env')
    
    # Load current pairs from .env
    current_pairs = os.getenv("PAIRS", "BTCUSDT").split(",")
    
    # Load dynamic pairs
    dynamic_pairs = load_dynamic_pairs()
    
    # Combine (remove duplicates, keep order)
    all_pairs = []
    seen = set()
    for pair in current_pairs + dynamic_pairs:
        if pair and pair not in seen:
            all_pairs.append(pair)
            seen.add(pair)
    
    # Limit to 20 pairs
    final_pairs = all_pairs[:20]
    
    # Update .env file
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Replace PAIRS line
        new_pairs_line = f"PAIRS={','.join(final_pairs)}"
        if 'PAIRS=' in content:
            import re
            content = re.sub(r'PAIRS=.*', new_pairs_line, content)
        else:
            content += f"\n{new_pairs_line}\n"
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print(f"✅ Updated .env with {len(final_pairs)} pairs: {','.join(final_pairs)}")
        return True
    
    return False

if __name__ == '__main__':
    update_pairs_in_env()
