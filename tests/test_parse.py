"""All numbers here are made up."""
from ibi_portfolio_mcp.parse import (money, orders_from_json, parse_balances, parse_dom_rows, positions_from_json,
                                     summarize)
from ibi_portfolio_mcp.scraper import is_write_request

PORTFOLIO = {"entries": [
    {"symbol": "aapl", "preciseQuantity": 10.0, "precisePrice": 150.0, "preciseCostValue": 1500.0, "preciseValue": 2000.0,
     "preciseDaysValue": 12.5, "preciseGain": 500.0, "preciseGainPercent": 33.33, "quote": {"lastPrice": 200.0, "changePercent": 0.6}},
    {"symbol": "XYZ", "preciseQuantity": 2.5, "precisePrice": 40.0, "preciseCostValue": 100.0, "preciseValue": 80.0, "quote": {}},
    {"symbol": "BROKEN"},
]}

PAGE = """Account Info
Buying Power

$1,000.00

Portfolio Value

$2,080.00
Balance USD

$900.50
Balance ILS

₪3,210.75
"""


def test_positions_from_json():
    rows = positions_from_json(PORTFOLIO)
    assert [r["symbol"] for r in rows] == ["AAPL", "XYZ"]
    assert rows[0]["qty"] == 10 and rows[0]["unrealized_pl"] == 500
    assert rows[1]["last_price"] == 0.0
    assert positions_from_json(None) == [] and positions_from_json({"entries": "x"}) == []


def test_money():
    assert money("$1,234.56") == 1234.56
    assert money("-$9.23") == -9.23
    assert money("−$9.23") == -9.23
    assert money("₪8,212.10") == 8212.10
    assert money("12.5%") == 12.5
    assert money(None) is None and money("n/a") is None


def test_balances():
    b = parse_balances(PAGE)
    assert b == {"buying_power": 1000.0, "balance_usd": 900.5, "balance_ils": 3210.75, "portfolio_value": 2080.0}


def test_dom_rows():
    rows = [["AAPL\nD", "10", "$200.00", "0.60%", "$150.00", "$2,000.00", "$1,500.00", "$12.50", "$500.00", "33.33%"],
            ["", "x"], ["n/a?"] + ["1"] * 9]
    p = parse_dom_rows(rows)
    assert len(p) == 1 and p[0]["symbol"] == "AAPL" and p[0]["qty"] == 10 and p[0]["cost_price"] == 150


def test_summarize():
    s = summarize(positions_from_json(PORTFOLIO), cash=1000.0)
    assert s["total_value"] == 3080.0 and s["market_value"] == 2080.0
    assert s["unrealized_pl"] == 480.0 and s["unrealized_pl_pct"] == 30.0
    assert s["positions"][0]["symbol"] == "AAPL" and s["positions"][0]["weight_pct"] == 64.94
    assert summarize([], None)["cash_pct"] is None


def test_orders():
    rows = orders_from_json({"orders": [
        {"ourRef": "A1", "symbol": "aapl", "transType": "B", "translatedStatus": "Filled", "preciseQuantity": 5,
         "preciseExecPx": 190.0, "createDate": "08/12/2026 13:58:56 EDT", "commission": "1.5"},
        {"symbol": "NOREF"},
    ]})
    assert rows == [{"ref": "A1", "symbol": "AAPL", "side": "BUY", "status": "Filled", "order_type": None,
                     "created_at": "2026-08-12T13:58:56", "executed_at": None, "qty": 5.0, "exec_qty": None,
                     "limit_price": None, "exec_price": 190.0, "profit_loss": None, "commission": 1.5, "fees": None,
                     "currency": None}]


def test_read_only_guard():
    assert is_write_request("POST", "https://ibi.viewtrade.com/api/orders")
    assert is_write_request("PUT", "https://ibi.viewtrade.com/api/order/123")
    assert is_write_request("DELETE", "https://ibi.viewtrade.com/api/orders/123")
    assert is_write_request("POST", "https://ibi.viewtrade.com/api/withdrawal")
    assert not is_write_request("GET", "https://ibi.viewtrade.com/api/orders/latest")
    assert not is_write_request("POST", "https://ibi.viewtrade.com/api/orders/latest")
    assert not is_write_request("POST", "https://auth.ibi.co.il/u/login")
    assert not is_write_request("GET", "https://ibi.viewtrade.com/api/user/portfolio/full")
