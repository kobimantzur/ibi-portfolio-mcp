"""Where the IBI username and password come from. They are only ever handed to scraper.fetch()."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


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
    """IBI_PASS_CMD="security find-generic-password -s ibi -a me -w" -> the command's stdout."""
    cmd = os.getenv(var)
    if not cmd:
        return None
    try:
        out = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=30, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        # do not echo stderr: some password managers print the secret's name or path there
        raise MissingCredentials(f"{var} failed ({type(e).__name__}); run it in a terminal to check") from None
    return out.stdout.strip() or None


def get_credentials() -> tuple[str, str]:
    user = os.getenv("IBI_USER") or _from_command("IBI_USER_CMD")
    password = os.getenv("IBI_PASS") or _from_command("IBI_PASS_CMD")
    if not user or not password:
        raise MissingCredentials(
            "IBI credentials not set. Set IBI_USER and IBI_PASS (or IBI_PASS_CMD) in the MCP server's environment. "
            "See the README section 'Your IBI password'.")
    return user, password
