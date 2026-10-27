"""MCP server: read-only IBI portfolio data for Claude and other AI assistants (stdio)."""
from __future__ import annotations

import asyncio
import os
import sys
import time

from mcp.server.mcpserver import MCPServer

from . import __version__
from .credentials import MissingCredentials, get_credentials, load_env_file
from .parse import summarize
from .scraper import IbiError, Snapshot, fetch

CACHE_TTL_S = int(os.getenv("IBI_CACHE_SECONDS", "300"))

mcp = MCPServer(
    "ibi-portfolio",
    version=__version__,
    instructions=(
        "Read-only access to the user's IBI (Israel Brokerage & Investments) NextGen account: positions, cash, "
        "profit/loss and recent account activity. Each fresh read logs in to IBI and takes about a minute; results "
        "are cached for a few minutes. This server cannot place, change or cancel orders, and you should not give "
        "personalized investment advice."
    ),
)

_cache: dict[str, object] = {"at": 0.0, "snap": None}
_lock = asyncio.Lock()


async def _snapshot(refresh: bool) -> Snapshot:
    async with _lock:   # one browser login at a time
        snap = _cache["snap"]
        if snap is not None and not refresh and time.time() - _cache["at"] < CACHE_TTL_S:
            return snap
        user, password = get_credentials()
        snap = await asyncio.to_thread(
            fetch, user, password,
            headed=os.getenv("IBI_HEADED", "") in ("1", "true", "yes"),
            login_timeout_s=int(os.getenv("IBI_LOGIN_TIMEOUT_S", "180" if os.getenv("IBI_HEADED") else "90")),
            debug_dir=os.getenv("IBI_DEBUG_DIR") or None,
        )
        _cache.update(at=time.time(), snap=snap)
        return snap


def _meta(snap: Snapshot) -> dict:
    return {"fetched_at": snap.fetched_at.isoformat(), "source": snap.source,
            **({"blocked_write_requests": snap.blocked_requests} if snap.blocked_requests else {})}


def _error(e: Exception) -> dict:
    return {"error": str(e), "kind": type(e).__name__}


@mcp.tool()
async def get_portfolio(refresh: bool = False) -> dict:
    """Current IBI portfolio: total value, cash, profit/loss, and every open position (symbol, quantity, cost,
    market value, P/L, weight). Values come from IBI itself, in USD. Set refresh=true to skip the short cache."""
    try:
        snap = await _snapshot(refresh)
    except (IbiError, MissingCredentials) as e:
        return _error(e)
    return {**summarize([dict(p) for p in snap.positions], snap.cash), "balances": snap.balances, **_meta(snap)}


@mcp.tool()
async def get_account_activity(limit: int = 50, refresh: bool = False) -> dict:
    """Recent orders and executions from IBI's 'Latest Account Activity' (side, symbol, status, quantity, price,
    fees, dates). Read-only."""
    try:
        snap = await _snapshot(refresh)
    except (IbiError, MissingCredentials) as e:
        return _error(e)
    rows = sorted(snap.orders, key=lambda o: o.get("created_at") or "", reverse=True)
    return {"activity": rows[: max(1, limit)], "count": len(snap.orders), **_meta(snap)}


def main() -> None:
    load_env_file()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # terminal smoke test: logs in once and prints a short summary (no positions)
        try:
            snap = asyncio.run(_snapshot(True))
        except (IbiError, MissingCredentials) as e:
            sys.exit(f"FAILED ({type(e).__name__}): {e}")
        s = summarize([dict(p) for p in snap.positions], snap.cash)
        print(f"OK: {s['position_count']} positions, total {s['total_value']:,.2f} USD, source {snap.source}, "
              f"{len(snap.orders)} activity rows")
        return
    mcp.run()


if __name__ == "__main__":
    main()
