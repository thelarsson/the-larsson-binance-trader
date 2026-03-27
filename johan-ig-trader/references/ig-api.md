# IG Markets REST API Reference

## Base URLs

- **Demo**: `https://demo-api.ig.com/gateway/deal`
- **Live**: `https://api.ig.com/gateway/deal`

## Authentication

### Create Session (POST /session)

Request headers:
```
Content-Type: application/json
X-IG-API-KEY: <your-api-key>
```

Request body:
```json
{
  "identifier": "<account-id>",
  "password": "<password>"
}
```

Response headers:
- `X-SECURITY-TOKEN` - Security token for subsequent requests
- `CST` - Client session token

**Note**: Tokens expire after approximately 10 minutes. Refresh by calling `/session` again.

## Key Endpoints

### Accounts

- **GET /accounts** - Get account balances and details

### Markets

- **GET /markets/{epic}** - Get market data for an instrument
- **GET /markets?searchTerm={query}** - Search markets

### Prices

- **GET /prices/{epic}?resolution={res}&max={count}** - Get price history
  - Resolutions: `MINUTE`, `MINUTE_5`, `MINUTE_15`, `MINUTE_30`, `HOUR`, `DAY`, `WEEK`, `MONTH`
  - Max: 1-1000 (default 20)

### Positions

- **GET /positions** - List open positions
- **POST /positions** - Open a new position
- **POST /positions/otc** - Close/amend a position

### Orders

- **GET /workingorders** - List working orders
- **POST /workingorders** - Create working order

## Position Operations

### Opening a Position (POST /positions)

```json
{
  "epic": "IX.D.DAX.IFG.IP",
  "direction": "BUY",
  "size": 1.0,
  "orderType": "MARKET",
  "currencyCode": "USD",
  "stopLevel": 14500.0,
  "limitLevel": 15500.0,
  "guaranteedStop": false,
  "forceOpen": true
}
```

Fields:
- `epic` - Instrument epic code
- `direction` - BUY or SELL
- `size` - Position size
- `orderType` - MARKET, LIMIT, or QUOTE
- `currencyCode` - Account currency
- `stopLevel` - Stop loss price level (optional)
- `limitLevel` - Take profit price level (optional)
- `guaranteedStop` - Use guaranteed stop loss (costs extra)
- `forceOpen` - Allow opening when same-direction position exists

### Closing a Position (POST /positions/otc)

```json
{
  "dealId": "DIAAA0000001ABC",
  "direction": "SELL",
  "size": 1.0,
  "orderType": "MARKET"
}
```

**Important**: 
- Use opposite direction of open position
- Use the `/positions/otc` endpoint, not DELETE /positions
- `dealId` comes from the open position

## Error Handling

Common error codes:
- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (expired/invalid tokens)
- `404` - Resource not found
- `500` - Server error

## Rate Limits

- 60 requests per minute for most endpoints
- 10 requests per minute for price history

## References

- [IG API Documentation](https://labs.ig.com/rest-trading-reference-guide)
- [IG API Forum](https://labs.ig.com/community)
