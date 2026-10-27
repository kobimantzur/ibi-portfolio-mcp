"""Where the IBI username and password come from. They are only ever handed to scraper.fetch().

Lookup order, first hit wins:
  1. IBI_USER / IBI_PASS environment variables (or a .env file)
  2. IBI_USER_CMD / IBI_PASS_CMD: a command that prints the value (password managers)
  3. the computer's own secret vault, filled by `ibi-portfolio-mcp setup`
     (macOS Keychain, Windows Credential Manager, Linux Secret Service)
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

VAULT_SERVICE = "ibi-portfolio-mcp"
VAULT_USER_KEY = "username"
VAULT_PASS_KEY = "password"


class MissingCredentials(RuntimeError):
    pass


def load_env_file() -> None:
    """IBI_ENV_FILE if set, else ./.env. Real environment variables always win."""
    from dotenv import load_dotenv

    path = os.getenv("IBI_ENV_FILE")
    if path:
        load_dotenv(Path(path).expanduser(), override=False)
    elif Path(".env").is_file():
        load_dotenv(".env", override=False)


def _from_command(var: str) -> str | None:
    """IBI_PASS_CMD="op read op://Private/IBI/password" -> the command's stdout."""
    cmd = os.getenv(var)
    if not cmd:
        return None
    try:
        out = subprocess.run(shlex.split(cmd, posix=os.name != "nt"), capture_output=True, text=True, timeout=30,
                             check=True)
    except (subprocess.SubprocessError, OSError) as e:
        # do not echo stderr: some password managers print the secret's name or path there
        raise MissingCredentials(f"{var} failed ({type(e).__name__}); run it in a terminal to check") from None
    return out.stdout.strip() or None


def _from_vault(key: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(VAULT_SERVICE, key)
    except Exception:  # noqa: BLE001  (no vault on this machine, e.g. a headless Linux box)
        return None


def save_to_vault(user: str, password: str) -> None:
    import keyring

    keyring.set_password(VAULT_SERVICE, VAULT_USER_KEY, user)
    keyring.set_password(VAULT_SERVICE, VAULT_PASS_KEY, password)


def delete_from_vault() -> None:
    import keyring
    from keyring.errors import PasswordDeleteError

    for key in (VAULT_USER_KEY, VAULT_PASS_KEY):
        try:
            keyring.delete_password(VAULT_SERVICE, key)
        except PasswordDeleteError:
            pass


def get_credentials() -> tuple[str, str]:
    user = os.getenv("IBI_USER") or _from_command("IBI_USER_CMD") or _from_vault(VAULT_USER_KEY)
    password = os.getenv("IBI_PASS") or _from_command("IBI_PASS_CMD") or _from_vault(VAULT_PASS_KEY)
    if not user or not password:
        raise MissingCredentials(
            "IBI username/password not found. Run `ibi-portfolio-mcp setup` in a terminal once, "
            "or see the README section 'Your IBI password'.")
    return user, password
