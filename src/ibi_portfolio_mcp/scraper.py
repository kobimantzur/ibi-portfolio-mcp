"""Read-only IBI NextGen (ibi.orbisfn.io) reader.

Opens a fresh headless Chromium, types your username and password into IBI's own login page, waits for the
home page, and keeps copies of the JSON the app itself loads (portfolio, balance, latest account activity).
The page's positions table and balances text are read as a fallback.

Read-only by design:
  * the only things it clicks are the Login button, the login form's submit and the "Latest Account Activity" tab
  * a network guard aborts any non-GET request to an order / trade / transfer / withdraw URL
  * nothing is saved: no cookies, no tokens, no session on disk (unless you turn on IBI_DEBUG_DIR)
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from .parse import orders_from_json, parse_balances, parse_dom_rows, positions_from_json

LOGIN_URL = "https://ibi.orbisfn.io/login"
AUTH_HOST = "auth.ibi.co.il"
TRADING_URL = "https://ibi.orbisfn.io/trading"
API_PATTERNS = {
    "portfolio": "/api/user/portfolio/full",
    "balance": "/api/user/balance",
    "orders": "/api/orders/latest",
}
# Non-GET requests to these paths are aborted. Reading the activity feed stays allowed.
WRITE_PATH = re.compile(r"/(orders?|trades?|transfers?|withdraw\w*|deposit\w*)(/|$)", re.I)
SAFE_PATHS = {"/api/orders/latest"}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}


class IbiError(RuntimeError):
    pass


class IbiOtpRequired(IbiError):
    pass


@dataclass
class Snapshot:
    fetched_at: datetime
    positions: list[dict] = field(default_factory=list)
    balances: dict[str, float] = field(default_factory=dict)
    orders: list[dict] = field(default_factory=list)
    source: str = "none"          # "json" or "page"
    blocked_requests: list[str] = field(default_factory=list)

    @property
    def cash(self) -> float | None:
        return self.balances.get("buying_power")


def _log(msg: str) -> None:
    # stdout belongs to the MCP protocol: progress goes to stderr. Never log credentials.
    print(f"[ibi] {msg}", file=sys.stderr, flush=True)


def is_write_request(method: str, url: str) -> bool:
    path = urlparse(url).path
    if method.upper() in READ_METHODS or path in SAFE_PATHS:
        return False
    return bool(WRITE_PATH.search(path))


def fetch(user: str, password: str, *, headed: bool = False, login_timeout_s: int = 90,
          with_activity: bool = True, debug_dir: str | None = None) -> Snapshot:
    from playwright.sync_api import Error as PWError, TimeoutError as PWTimeout, sync_playwright

    snap = Snapshot(fetched_at=datetime.now(UTC))
    captured: dict[str, object] = {}
    dbg = None
    if debug_dir:
        dbg = Path(debug_dir).expanduser() / snap.fetched_at.strftime("ibi-%Y%m%d-%H%M%S")
        dbg.mkdir(parents=True, exist_ok=True)
        _log(f"debug artifacts (contain your balances, delete when done): {dbg}")

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=not headed)
        except PWError as e:
            if "Executable doesn't exist" in str(e):
                raise IbiError("Chromium is not installed. Run: uv run playwright install chromium") from None
            raise
        ctx = browser.new_context(viewport={"width": 1500, "height": 1000})

        def guard(route):
            req = route.request
            if is_write_request(req.method, req.url):
                snap.blocked_requests.append(f"{req.method} {urlparse(req.url).path}")
                _log(f"read-only guard blocked {req.method} {urlparse(req.url).path}")
                return route.abort()
            return route.continue_()

        ctx.route("**/*", guard)
        page = ctx.new_page()

        def on_response(resp):
            for key, pat in API_PATTERNS.items():
                if pat in resp.url and resp.status == 200:
                    try:
                        captured[key] = resp.json()
                    except Exception:  # noqa: BLE001
                        pass

        page.on("response", on_response)

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.get_by_role("button", name=re.compile(r"^Login", re.I)).first.click()
            page.wait_for_url(re.compile(re.escape(AUTH_HOST)), timeout=30_000)
            # the page keeps a hidden copy of the form for the SMS tab: fill the visible one
            page.locator('input[placeholder="Email or ID"]:visible').first.fill(user)
            page.locator('input[placeholder="Password"]:visible').first.fill(password)
            page.locator('button[type="submit"]:visible').first.click()
            _log("login submitted")

            try:
                page.wait_for_url(re.compile(r"^https://ibi\.orbisfn\.io/"), timeout=login_timeout_s * 1000)
            except PWTimeout:
                body = page.inner_text("body")[:2000]
                if re.search(r"code|SMS|verification|קוד", body, re.I):
                    raise IbiOtpRequired(
                        "IBI asked for a one-time SMS code. Set IBI_HEADED=1, run again and type the code "
                        "in the browser window that opens.") from None
                raise IbiError("login did not reach the IBI home page (wrong username/password?)") from None

            _log("logged in, reading portfolio")
            deadline = time.time() + 45
            while "portfolio" not in captured and time.time() < deadline:
                page.wait_for_timeout(500)

            body_text = page.inner_text("body")
            page_balances = parse_balances(body_text)
            page_positions: list[dict] = []
            if "portfolio" not in captured:
                table = page.locator("table").filter(has_text="Symbol").first
                try:
                    table.wait_for(timeout=15_000)
                    rows = table.evaluate(
                        "t => [...t.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText))")
                    page_positions = parse_dom_rows(rows)
                except PWTimeout:
                    pass

            if with_activity:
                try:
                    page.goto(TRADING_URL, wait_until="domcontentloaded")
                    page.get_by_role("tab", name=re.compile("Latest Account Activity", re.I)).click(timeout=20_000)
                    deadline = time.time() + 30
                    while "orders" not in captured and time.time() < deadline:
                        page.wait_for_timeout(500)
                except Exception as e:  # noqa: BLE001
                    _log(f"account activity unavailable: {type(e).__name__}")

            if dbg:
                (dbg / "page.txt").write_text(body_text)
                for k, v in captured.items():
                    (dbg / f"{k}.json").write_text(json.dumps(v, indent=2, ensure_ascii=False))
                page.screenshot(path=str(dbg / "last-page.png"), full_page=True)
        except Exception:
            if dbg:
                try:
                    page.screenshot(path=str(dbg / "error.png"))
                except Exception:  # noqa: BLE001
                    pass
            raise
        finally:
            ctx.close()
            browser.close()

    snap.positions = positions_from_json(captured.get("portfolio"))
    snap.source = "json" if snap.positions else "page"
    if not snap.positions:
        snap.positions = page_positions
    snap.balances = dict(page_balances)
    bal = captured.get("balance")
    if isinstance(bal, dict) and bal.get("buyingPower") is not None:
        snap.balances["buying_power"] = float(bal["buyingPower"])
    snap.orders = orders_from_json(captured.get("orders"))
    if not snap.positions and not snap.balances:
        raise IbiError("logged in but found no positions or balances; IBI may have changed its site")
    return snap
