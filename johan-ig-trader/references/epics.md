# IG Markets Epic Codes Reference

## Indices

| Epic | Description |
|------|-------------|
| `IX.D.DAX.IFG.IP` | Germany 40 (DAX) |
| `IX.D.SPTRD.IFE.IP` | S&P 500 |
| `IX.D.NASDAQ.IFE.IP` | NASDAQ 100 |
| `IX.D.DOW.IFE.IP` | Wall Street (Dow Jones) |
| `IX.D.FTSE.IFE.IP` | UK 100 (FTSE) |
| `IX.D.CAC.IFE.IP` | France 40 (CAC) |
| `IX.D.EURO.IFE.IP` | EU Stocks 50 |
| `IX.D.NIKKEI.IFE.IP` | Japan 225 (Nikkei) |
| `IX.D.HSENG.IFE.IP` | Hong Kong HS50 |

## Forex Majors

| Epic | Description |
|------|-------------|
| `CS.D.EURUSD.MINI.IP` | EUR/USD Mini |
| `CS.D.GBPUSD.MINI.IP` | GBP/USD Mini |
| `CS.D.USDJPY.MINI.IP` | USD/JPY Mini |
| `CS.D.AUDUSD.MINI.IP` | AUD/USD Mini |
| `CS.D.USDCAD.MINI.IP` | USD/CAD Mini |
| `CS.D.USDCHF.MINI.IP` | USD/CHF Mini |

## Forex Standard (larger contract size)

| Epic | Description |
|------|-------------|
| `CS.D.EURUSD.CFD.IP` | EUR/USD Standard |
| `CS.D.GBPUSD.CFD.IP` | GBP/USD Standard |

## Commodities

| Epic | Description |
|------|-------------|
| `CO.D.CFDS.IFE.IP` | Crude Oil |
| `CO.D.CFDG.IFE.IP` | Brent Oil |
| `MT.D.GOLD.IFE.IP` | Gold |
| `MT.D.SILVER.IFE.IP` | Silver |

## Cryptocurrencies

| Epic | Description |
|------|-------------|
| `CS.D.BITCOIN.CFD.IP` | Bitcoin |
| `CS.D.ETHUSD.CFD.IP` | Ethereum |

## Minimum Trade Sizes

| Instrument Type | Minimum Size |
|-----------------|--------------|
| Forex Mini | 0.5 |
| Forex Standard | 1.0 |
| Indices | 1.0 |
| Commodities | 1.0 |
| Cryptocurrencies | 0.05 |

## Finding Epics

To find epic codes:
1. Log into IG Web Platform
2. Search for the instrument
3. Epic is shown in market details or URL

Or use the API:
```
GET /markets?searchTerm=EURUSD
```
