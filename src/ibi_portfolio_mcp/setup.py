"""`ibi-portfolio-mcp setup`: one guided command for non-developers.

1. saves the IBI username + password in the computer's own vault (never in a file)
2. downloads the browser it needs
3. tests the login once
4. connects the AI apps it finds (Claude Desktop, ChatGPT desktop / Codex, Cursor, Claude Code)
"""
from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .credentials import VAULT_USER_KEY, _from_vault, delete_from_vault, save_to_vault

NAME = "ibi-portfolio"


def _ask(question: str, default_yes: bool = True) -> bool:
    hint = "[Y/n]" if default_yes else "[y/N]"
    ans = input(f"{question} {hint} ").strip().lower()
    return default_yes if not ans else ans.startswith("y")


def server_command() -> str:
    """Absolute path of this program, so apps started from the Dock/Start menu can find it."""
    found = shutil.which("ibi-portfolio-mcp")
    return str(Path(found or sys.argv[0]).resolve())


def install_browser() -> None:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, stdout=sys.stderr)


# ---------- connecting apps ----------

def _claude_desktop_config() -> Path | None:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if os.name == "nt" and os.getenv("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    return None


def _codex_config() -> Path:
    return Path(os.getenv("CODEX_HOME") or Path.home() / ".codex") / "config.toml"


def _add_to_json(path: Path, cmd: str) -> str:
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return f"skipped: {path} is not valid JSON, add it by hand (see README)"
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    data.setdefault("mcpServers", {})[NAME] = {"command": cmd, "args": []}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return f"connected ({path})"


def _add_to_codex(path: Path, cmd: str) -> str:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if f"[mcp_servers.{NAME}]" in text:
        return f"already connected ({path})"
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    # a fresh IBI read takes about a minute; the default tool timeout is 60s
    block = (f"\n[mcp_servers.{NAME}]\ncommand = '{cmd}'\nstartup_timeout_sec = 30\ntool_timeout_sec = 300\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n" + block if text else block.lstrip("\n"), encoding="utf-8")
    return f"connected ({path})"


def _add_to_claude_code(cmd: str) -> str:
    claude = shutil.which("claude")
    r = subprocess.run([claude, "mcp", "add", "--scope", "user", NAME, "--", cmd], capture_output=True, text=True)
    if r.returncode == 0:
        return "connected"
    return "already connected" if "already exists" in (r.stdout + r.stderr) else "failed: " + (r.stderr or r.stdout).strip()[:200]


def connect_apps(cmd: str, assume_yes: bool = False) -> None:
    apps = []
    cd = _claude_desktop_config()
    if cd and cd.parent.exists():
        apps.append(("Claude Desktop", lambda: _add_to_json(cd, cmd)))
    codex = _codex_config()
    apps.append(("ChatGPT desktop app / Codex", lambda: _add_to_codex(codex, cmd)))
    if (Path.home() / ".cursor").exists():
        apps.append(("Cursor", lambda: _add_to_json(Path.home() / ".cursor/mcp.json", cmd)))
    if shutil.which("claude"):
        apps.append(("Claude Code", lambda: _add_to_claude_code(cmd)))

    for label, add in apps:
        if assume_yes or _ask(f"Connect to {label}?"):
            print(f"  {label}: {add()}")
    print("\nRestart the apps you connected, then ask: \"How is my IBI portfolio doing?\"")


# ---------- the guided flow ----------

def run_setup() -> None:
    print("IBI Portfolio MCP setup. Read-only: it can never trade or move money.\n")

    if _from_vault(VAULT_USER_KEY) and not _ask("A saved IBI login already exists. Replace it?", default_yes=False):
        pass
    else:
        print("Your IBI NextGen login (the one you use at ibi.orbisfn.io).")
        print("It is saved only in this computer's secure vault (Keychain / Credential Manager).\n")
        user = input("IBI username (email or ID): ").strip()
        password = getpass.getpass("IBI password (hidden as you type): ")
        if not user or not password:
            sys.exit("Nothing saved: username and password are both needed.")
        save_to_vault(user, password)
        print("Saved.\n")

    print("Downloading the browser it uses (one time, about 100 MB)...")
    install_browser()

    if _ask("\nTest the login now? It takes about a minute.") and not _test_login():
        return

    print()
    connect_apps(server_command())


def _test_login() -> bool:
    import asyncio

    from .scraper import IbiError
    from .server import _snapshot

    try:
        snap = asyncio.run(_snapshot(True))
    except IbiError as e:
        print(f"\nLogin test failed: {e}")
        print("Fix it and run `ibi-portfolio-mcp setup` again. To change the saved login: `ibi-portfolio-mcp forget`.")
        return False
    print(f"Works: found {len(snap.positions)} positions.")
    return True


def run_forget() -> None:
    delete_from_vault()
    print("Removed the saved IBI login from this computer's vault.")
