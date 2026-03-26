# CoinMetrics API Status Report

**Date**: 2026-03-23
**Test Target**: CoinMetrics Community API (no API key)

---

## 1. NUPL 403 Error - Root Cause

`coinmetrics_nupl` fails with 403 because it internally requires **CapRealUSD** (Realized Cap), which is now a **pro-only metric** on CoinMetrics Community API.

```
API 오류 403: Requested metric 'CapRealUSD' with frequency '1d' for asset 'btc'
is not available with supplied credentials.
```

NUPL = (Market Cap - Realized Cap) / Market Cap. Without CapRealUSD, NUPL cannot be calculated.

---

## 2. CoinMetrics Metric Availability (2026-03-23 Test Results)

### ACCESSIBLE (200 OK)

| Metric | Description | Category |
|--------|-------------|----------|
| **CapMrktCurUSD** | Market Cap USD | Valuation |
| **CapMVRVCur** | MVRV Ratio (Market/Realized) | Valuation |
| **AdrActCnt** | Active Addresses | Network Activity |
| **TxCnt** | Daily Transaction Count | Network Activity |
| **FlowInExNtv** | Exchange Inflow (native) | Exchange Flow |
| **FlowOutExNtv** | Exchange Outflow (native) | Exchange Flow |
| **SplyExNtv** | Exchange Supply (native) | Exchange Flow |
| **SplyCur** | Current Circulating Supply | Supply |

### BLOCKED (403 Forbidden - Pro Only)

| Metric | Description | Impact |
|--------|-------------|--------|
| **CapRealUSD** | Realized Cap USD | Blocks NUPL calculation |
| **SOPR** | Spent Output Profit Ratio | No free alternative |
| **NVTAdj** | NVT Ratio | No direct free alternative |
| **FeeTotUSD** | Total Fees USD | Blockchain.com has alternative |
| **TxTfrValAdjUSD** | Adjusted Transfer Value USD | No direct free alternative |
| **RevUSD** | Miner Revenue USD | Blockchain.com has alternative |
| **IssContNtv** | Daily Issuance (native) | Calculable from SplyCur delta |

### NOT SUPPORTED (400 Bad Parameter)

| Metric | Note |
|--------|------|
| **FlowNetExNtv** | Not a valid API metric. Must calculate: FlowInExNtv - FlowOutExNtv |

### PERMISSION DENIED (Tool-level, not API-level)

| Tool | Note |
|------|------|
| `coinmetrics_investment_snapshot` | Tool permission denied in current session |
| `coinmetrics_report_bundle` | Tool permission denied in current session |
| `blockchain_lth_proxy` | Tool permission denied in current session |

---

## 3. Alternative Sources for Blocked Metrics

### NUPL Alternative
- **Primary**: MVRV (CapMVRVCur) is accessible and is a close proxy. MVRV > 3 = overheated, < 1 = undervalued. Current MVRV: **1.25** (neutral-to-undervalued zone).
- **Workaround**: Since CapMVRVCur = CapMrktCurUSD / CapRealUSD, and both CapMVRVCur and CapMrktCurUSD are accessible, we can **back-calculate** CapRealUSD:
  ```
  CapRealUSD = CapMrktCurUSD / CapMVRVCur
  NUPL = 1 - (1 / CapMVRVCur)
  ```
  This is mathematically equivalent and requires NO pro API access.

### SOPR Alternative
- No free CoinMetrics source. Use **CryptoQuant** or **Glassnode** free tier if available.
- Partial proxy: Exchange flow direction (FlowInExNtv vs FlowOutExNtv) indicates sell/hold pressure similarly.

### NVT Alternative
- Can be partially reconstructed: CapMrktCurUSD is available. Transaction value (TxTfrValAdjUSD) is blocked, but TxCnt is available.
- **Blockchain.com** `estimated-transaction-volume-usd` can substitute for transfer value.

### Fee & Revenue Alternatives
- **Blockchain.com** provides: `transaction-fees-usd`, `miners-revenue` -- both accessible and free.
- `blockchain_macro_context` (tested OK) bundles hash rate, fees, txs, active addresses.

---

## 4. Blockchain.com as Backup Source (Tested OK)

`blockchain_macro_context` returned successfully with:
- Hash rate: 932 GH/s (7d avg)
- Daily fees: $188,002 (7d avg)
- Daily txs: 412,055 (7d avg)
- Active addresses: 472,314 (7d avg)
- BTC price: $68,732.72

This covers network health, miner economics, and adoption metrics that CoinMetrics blocks.

---

## 5. Recommended Next Steps

### Immediate Fix: NUPL Reconstruction (Priority 1)
Update `coinmetrics_nupl` tool to calculate NUPL from MVRV instead of fetching CapRealUSD directly:
```
NUPL = 1 - (1 / MVRV)
```
- When MVRV = 1.25 --> NUPL = 0.20 (20% unrealized profit)
- This uses only CapMVRVCur, which is free and accessible.

### MCP Server Code Fix Location
The NUPL tool in the CoinMetrics MCP server needs to be modified:
- **Current**: Fetches CapMrktCurUSD + CapRealUSD, computes NUPL = (MCap - RCap) / MCap
- **Fix**: Fetch CapMVRVCur, compute NUPL = 1 - (1/MVRV)
- Same mathematical result, zero pro-API dependency.

### Hybrid Data Strategy (Priority 2)
For metrics that remain blocked, route to Blockchain.com:
| Blocked CoinMetrics | Blockchain.com Alternative |
|---------------------|---------------------------|
| FeeTotUSD | transaction-fees-usd |
| RevUSD | miners-revenue |
| TxTfrValAdjUSD | estimated-transaction-volume-usd |

### Long-term (Priority 3)
- Monitor CoinMetrics Community API for further metric restrictions.
- Consider CoinMetrics Pro API key if exchange flow + SOPR + NVT are critical.
- CapMVRVCur availability should be monitored -- if this gets blocked, MVRV-based NUPL workaround breaks too.

---

## 6. Summary

| Capability | Status | Solution |
|-----------|--------|----------|
| NUPL | BLOCKED | Calculate from MVRV: `1 - 1/MVRV` |
| MVRV | OK | Direct from CoinMetrics |
| Exchange Flows | OK | Direct from CoinMetrics |
| Active Addresses | OK | CoinMetrics + Blockchain.com |
| Transactions | OK | CoinMetrics + Blockchain.com |
| SOPR | BLOCKED | No free alternative; use exchange flow as proxy |
| NVT | BLOCKED | Partial reconstruction via Blockchain.com tx volume |
| Fees/Revenue | BLOCKED | Use Blockchain.com |
| Network Health | OK | Blockchain.com macro_context |
