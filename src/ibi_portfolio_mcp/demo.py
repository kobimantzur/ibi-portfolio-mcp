"""Made-up portfolio for IBI_DEMO=1: try the server, record demos, no IBI account needed."""
from __future__ import annotations

from datetime import UTC, datetime

from .parse import orders_from_json, positions_from_json
from .scraper import Snapshot

# symbol, qty, cost price, last price, today's change %
_HOLDINGS = [
    ("VOO", 22, 455.10, 541.30, 0.4),
    ("AAPL", 40, 171.25, 228.90, -0.6),
    ("MSFT", 18, 362.40, 452.15, 0.9),
    ("NVDA", 35, 98.60, 141.75, 2.1),
    ("TEVA", 300, 14.20, 18.95, 1.3),
    ("AMZN", 25, 181.30, 172.40, -1.2),
    ("CHKP", 12, 168.00, 205.60, 0.2),
    ("INTC", 120, 31.80, 22.15, -0.8),
]


def _portfolio_json() -> dict:
    entries = []
    for sym, qty, cost, last, chg in _HOLDINGS:
        value, cost_value = qty * last, qty * cost
        entries.append({
            "symbol": sym, "preciseQuantity": qty, "precisePrice": cost, "preciseCostValue": round(cost_value, 2),
            "preciseValue": round(value, 2), "preciseDaysValue": round(value * chg / 100, 2),
            "preciseGain": round(value - cost_value, 2), "preciseGainPercent": round((value / cost_value - 1) * 100, 2),
            "quote": {"lastPrice": last, "changePercent": chg},
        })
    return {"entries": entries}


_ORDERS = {"orders": [
    {"ourRef": "D-1003", "symbol": "NVDA", "transType": "B", "translatedStatus": "Filled", "orderType": "Limit",
     "preciseQuantity": 10, "preciseExecQty": 10, "preciseLimitPx": 135.0, "preciseExecPx": 134.80,
     "createDate": "10/21/2026 10:02:11 EDT", "executedDate": "10/21/2026 10:02:13 EDT", "commission": 2.5,
     "tradeCurrency": "USD"},
    {"ourRef": "D-1002", "symbol": "INTC", "transType": "S", "translatedStatus": "Filled", "orderType": "Market",
     "preciseQuantity": 30, "preciseExecQty": 30, "preciseExecPx": 22.40, "profitLoss": -282.0,
     "createDate": "10/14/2026 15:41:50 EDT", "executedDate": "10/14/2026 15:41:51 EDT", "commission": 2.5,
     "tradeCurrency": "USD"},
    {"ourRef": "D-1001", "symbol": "TEVA", "transType": "B", "translatedStatus": "Cancelled", "orderType": "Limit",
     "preciseQuantity": 100, "preciseLimitPx": 17.0, "createDate": "10/08/2026 09:35:02 EDT", "tradeCurrency": "USD"},
]}


def demo_snapshot() -> Snapshot:
    return Snapshot(fetched_at=datetime.now(UTC), positions=positions_from_json(_portfolio_json()),
                    balances={"buying_power": 4820.35, "balance_usd": 4820.35}, orders=orders_from_json(_ORDERS),
                    source="demo")
