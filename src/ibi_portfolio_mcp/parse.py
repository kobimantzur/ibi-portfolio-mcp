"""Pure functions that turn what the IBI web app shows into plain dicts. No network, easy to test."""
from __future__ import annotations

import re
from datetime import datetime

POSITION_COLUMNS = ["symbol", "qty", "last_price", "change_pct", "cost_price", "market_value",
                    "total_cost", "todays_pl", "unrealized_pl", "unrealized_pl_pct"]
BALANCE_LABELS = (("buying_power", "Buying Power"), ("balance_usd", "Balance USD"), ("balance_ils", "Balance ILS"),
                  ("account_value_ils", "Account Value"), ("portfolio_value", "Portfolio Value"),
                  ("portfolio_cost", "Portfolio Cost"))
_IBI_DT = "%m/%d/%Y %H:%M:%S"


def positions_from_json(portfolio: object) -> list[dict]:
    """Map the app's /api/user/portfolio/full entries onto plain position rows."""
    if not isinstance(portfolio, dict) or not isinstance(portfolio.get("entries"), list):
        return []
    out = []
    for e in portfolio["entries"]:
        try:
            q = e.get("quote") or {}
            out.append({
                "symbol": str(e["symbol"]).upper(),
                "qty": float(e.get("preciseQuantity", e.get("quantity"))),
                "last_price": float(q.get("lastPrice") or 0.0),
                "change_pct": float(q.get("changePercent") or 0.0),
                "cost_price": float(e.get("precisePrice", e.get("price"))),
                "market_value": float(e.get("preciseValue", e.get("value", 0.0))),
                "total_cost": float(e.get("preciseCostValue", e.get("costValue", 0.0))),
                "todays_pl": float(e.get("preciseDaysValue", e.get("daysValue", 0.0))),
                "unrealized_pl": float(e.get("preciseGain", e.get("gain", 0.0))),
                "unrealized_pl_pct": float(e.get("preciseGainPercent", e.get("gainPercent", 0.0))),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def money(s: str | None) -> float | None:
    """'$1,234.56' / '-$9.23' / '₪8,212.10' / '12.5%' -> float."""
    if s is None:
        return None
    m = re.search(r"-?[\d,]*\.?\d+", s.replace("−", "-"))
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    return -v if s.strip().startswith(("-", "−")) or "-$" in s or "-₪" in s else v


def parse_balances(text: str) -> dict[str, float]:
    """Account balances from the home page text (fallback when the balance JSON is missing)."""
    out: dict[str, float] = {}
    for key, label in BALANCE_LABELS:
        m = re.search(re.escape(label) + r"\s*\n?\s*([₪$\-−]?[\d,]+\.\d{2})", text)
        if m and (v := money(m.group(1))) is not None:
            out[key] = v
    return out


def parse_dom_rows(rows: list[list[str]]) -> list[dict]:
    """Positions table cells per <tr> (fallback when the portfolio JSON is missing)."""
    out = []
    for cells in rows:
        cells = [c.strip() for c in cells if c is not None]
        if len(cells) < 10:
            continue
        sym = cells[0].split()[0].upper() if cells[0] else ""
        if not re.fullmatch(r"[A-Z0-9.\-]{1,10}", sym):
            continue
        rec: dict = {"symbol": sym}
        for name, cell in zip(POSITION_COLUMNS[1:], cells[1:10]):
            rec[name] = money(cell)
        out.append(rec)
    return out


def parse_ibi_dt(s: str | None) -> str | None:
    """'08/12/2026 13:58:56 EDT' -> '2026-08-12T13:58:56' (exchange time)."""
    if not s:
        return None
    try:
        return datetime.strptime(" ".join(s.split()[:2]), _IBI_DT).isoformat()
    except ValueError:
        return None


def map_order(o: dict) -> dict | None:
    """One row of the 'Latest Account Activity' feed."""
    ref = o.get("ourRef") or o.get("clientRef")
    if not ref or not o.get("symbol"):
        return None

    def num(precise: str, plain: str | None = None) -> float | None:
        for k in (precise, plain):
            if k and o.get(k) is not None:
                try:
                    return float(o[k])
                except (TypeError, ValueError):
                    return None
        return None

    return {
        "ref": str(ref),
        "symbol": str(o["symbol"]).upper(),
        "side": o.get("transaction") or {"B": "BUY", "S": "SELL"}.get(o.get("transType", ""), o.get("transType", "")),
        "status": o.get("translatedStatus") or o.get("status") or "",
        "order_type": o.get("orderType"),
        "created_at": parse_ibi_dt(o.get("createDate")),
        "executed_at": parse_ibi_dt(o.get("executedDate") or o.get("execTime")),
        "qty": num("preciseQuantity", "quantity"),
        "exec_qty": num("preciseExecQty", "execQty"),
        "limit_price": num("preciseLimitPx", "limitPx"),
        "exec_price": num("preciseExecPx", "execPx"),
        "profit_loss": num("profitLoss"),
        "commission": num("commission"),
        "fees": num("fees"),
        "currency": o.get("tradeCurrency"),
    }


def orders_from_json(orders: object) -> list[dict]:
    rows = orders if isinstance(orders, list) else (orders or {}).get("orders", []) if isinstance(orders, dict) else []
    return [m for o in rows if isinstance(o, dict) and (m := map_order(o))]


def summarize(positions: list[dict], cash: float | None) -> dict:
    """Totals computed from IBI's own market values, positions sorted by worth."""
    positions = sorted(positions, key=lambda r: -(r.get("market_value") or 0))
    value = sum(r.get("market_value") or 0 for r in positions)
    cost = sum(r.get("total_cost") or 0 for r in positions)
    total = value + (cash or 0)
    for r in positions:
        r["weight_pct"] = round((r.get("market_value") or 0) / total * 100, 2) if total else None
    return {
        "currency": "USD",
        "total_value": total,
        "market_value": value,
        "cash": cash,
        "cash_pct": round((cash or 0) / total * 100, 2) if total else None,
        "total_cost": cost,
        "unrealized_pl": value - cost,
        "unrealized_pl_pct": round((value / cost - 1) * 100, 2) if cost else None,
        "position_count": len(positions),
        "positions": positions,
    }
