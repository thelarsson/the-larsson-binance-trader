#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# Check if Python 3.10+ is available
python3 --version || { echo "Python 3.10+ required"; exit 1; }

# Create virtual environment if needed
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install dependencies
pip install --quiet requests

echo "IG Trader setup complete."
echo "Next steps:"
echo "1. Edit .env and add your IG_ACCOUNT_ID and IG_PASSWORD"
echo "2. Switch IG_BASE_URL to live API when ready: https://api.ig.com/gateway/deal"
echo "3. Run: python3 scripts/trader.py"
