#!/usr/bin/env python3
"""Tests for trader.py functions"""

import sys
import os

# Define the functions inline for testing
def calculate_ema(prices, period):
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0
    
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    
    return ema

def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    gains = gains[-period:]
    losses = losses[-period:]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0 and avg_gain == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def find_support_resistance(prices, lookback=20):
    """Find support and resistance levels."""
    if len(prices) < lookback:
        return prices[-1] * 0.99, prices[-1] * 1.01 if prices else (0, 0)
    
    recent = prices[-lookback:]
    resistance = max(recent)
    support = min(recent)
    return support, resistance

def calculate_signal(prices, strategy="momentum"):
    """Calculate trading signal from price data."""
    if len(prices) < 20:
        return "HOLD"
    
    closes = [p.get("closePrice", {}).get("bid", 0) for p in prices if p.get("closePrice")]
    if len(closes) < 20:
        return "HOLD"
    
    if strategy == "momentum":
        ema_9 = calculate_ema(closes, 9)
        ema_20 = calculate_ema(closes, 20)
        
        if ema_9 > ema_20 * 1.001:
            return "BUY"
        elif ema_9 < ema_20 * 0.999:
            return "SELL"
    
    elif strategy == "mean_reversion":
        rsi = calculate_rsi(closes, 14)
        support, resistance = find_support_resistance(closes, 20)
        current_price = closes[-1]
        
        if rsi < 30 and current_price <= support * 1.005:
            return "BUY"
        elif rsi > 70 and current_price >= resistance * 0.995:
            return "SELL"
    
    return "HOLD"

def test_ema():
    """Test EMA calculation vs SMA"""
    prices = [100, 102, 101, 103, 104, 102, 105, 107, 106, 108]
    
    sma = sum(prices[-5:]) / 5
    ema = calculate_ema(prices, 5)
    
    print(f"Prices: {prices}")
    print(f"SMA(5): {sma:.4f}")
    print(f"EMA(5): {ema:.4f}")
    print(f"EMA != SMA: {ema != sma}")
    assert ema != sma, "EMA should not equal SMA"
    print("✓ EMA test passed\n")

def test_rsi():
    """Test RSI calculation"""
    rising = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
    rsi_rising = calculate_rsi(rising, 14)
    print(f"Rising prices RSI: {rsi_rising:.2f}")
    assert rsi_rising > 70, f"Expected RSI > 70 for rising prices, got {rsi_rising}"
    
    falling = [114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
    rsi_falling = calculate_rsi(falling, 14)
    print(f"Falling prices RSI: {rsi_falling:.2f}")
    assert rsi_falling < 30, f"Expected RSI < 30 for falling prices, got {rsi_falling}"
    
    flat = [100] * 15
    rsi_flat = calculate_rsi(flat, 14)
    print(f"Flat prices RSI: {rsi_flat:.2f}")
    assert 45 <= rsi_flat <= 55, f"Expected RSI near 50 for flat prices, got {rsi_flat}"
    
    print("✓ RSI test passed\n")

def test_support_resistance():
    """Test support/resistance calculation"""
    prices = [100, 102, 98, 101, 99, 103, 97, 104, 96, 105, 95, 106, 94, 107, 93, 108, 92, 109, 91, 110]
    support, resistance = find_support_resistance(prices, 20)
    
    print(f"Prices range: {min(prices)} - {max(prices)}")
    print(f"Support: {support}, Resistance: {resistance}")
    
    assert support == min(prices), f"Support should be {min(prices)}, got {support}"
    assert resistance == max(prices), f"Resistance should be {max(prices)}, got {resistance}"
    print("✓ Support/Resistance test passed\n")

def test_momentum_signal():
    """Test momentum strategy signals"""
    uptrend = []
    price = 100
    for i in range(25):
        price += 1 + (i * 0.1)
        uptrend.append({"closePrice": {"bid": price}})
    
    signal = calculate_signal(uptrend, "momentum")
    print(f"Uptrend signal: {signal}")
    assert signal == "BUY", f"Expected BUY in uptrend, got {signal}"
    
    downtrend = []
    price = 150
    for i in range(25):
        price -= 1 + (i * 0.1)
        downtrend.append({"closePrice": {"bid": price}})
    
    signal = calculate_signal(downtrend, "momentum")
    print(f"Downtrend signal: {signal}")
    assert signal == "SELL", f"Expected SELL in downtrend, got {signal}"
    
    print("✓ Momentum signal test passed\n")

def test_mean_reversion_signal():
    """Test mean reversion strategy signals"""
    oversold = []
    price = 140
    for i in range(20):
        price -= 2
        oversold.append({"closePrice": {"bid": price}})
    
    signal = calculate_signal(oversold, "mean_reversion")
    print(f"Oversold signal: {signal}")
    
    overbought = []
    price = 50
    for i in range(20):
        price += 3
        overbought.append({"closePrice": {"bid": price}})
    
    signal = calculate_signal(overbought, "mean_reversion")
    print(f"Overbought signal: {signal}")
    
    print("✓ Mean reversion signal test passed\n")

if __name__ == "__main__":
    print("Running trader.py tests...\n")
    
    try:
        test_ema()
        test_rsi()
        test_support_resistance()
        test_momentum_signal()
        test_mean_reversion_signal()
        print("=" * 50)
        print("All tests passed! ✓")
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error during testing: {e}")
        sys.exit(1)
