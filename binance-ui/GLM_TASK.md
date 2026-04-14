# GLM Coding Task - Binance Trader UI Enhancement

## Assignment for GLM (Cloud Model)

You are working with me (Assistant) on improving the Binance Trader Dashboard UI.

## Current Status
- ✅ Backend API: Flask server running on localhost:5000
- ✅ Basic HTML/CSS UI: Working dashboard at localhost:8080
- ⚠️ Needs: Better styling, more features, responsive design

## Your Task
Improve the UI in `/home/johan/.openclaw/workspace/binance-ui/src/web/index.html`

## Requirements
1. **Better Styling:**
   - Modern dark theme with neon accents
   - Smooth animations/transitions
   - Professional crypto-dashboard look

2. **Additional Features:**
   - Real-time chart/graph for balance history
   - Better trade display with filtering
   - Price movement indicators (up/down arrows)
   - Profit/Loss visualization

3. **Responsive Design:**
   - Mobile-friendly
   - Flexible grid layout
   - Better typography

4. **Interactive Elements:**
   - Hover effects
   - Click to expand trade details
   - Refresh button

## Constraints
- ✅ Keep existing API endpoints
- ✅ Read-only (don't modify trading logic)
- ✅ Use vanilla HTML/CSS/JS (no frameworks needed)

## Output
Update `/home/johan/.openclaw/workspace/binance-ui/src/web/index.html` with improved UI.

## API Endpoints Available
- GET http://localhost:5000/api/status - Balance and status
- GET http://localhost:5000/api/trades - Trade history
- GET http://localhost:5000/api/positions - Current positions
- GET http://localhost:5000/api/signals - Trading signals

## Notes
- The Flask server must be running separately
- Test by opening http://localhost:8080 after updates
- Current balance: $538.80 USDT
