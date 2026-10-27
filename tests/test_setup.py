import json

from ibi_portfolio_mcp import credentials
from ibi_portfolio_mcp.setup import NAME, _add_to_codex, _add_to_json

CMD = "/home/someone/.local/bin/ibi-portfolio-mcp"


def test_json_keeps_other_servers_and_backs_up(tmp_path):
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}))
    assert _add_to_json(cfg, CMD).startswith("connected")
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["other"] == {"command": "x"} and data["theme"] == "dark"
    assert data["mcpServers"][NAME] == {"command": CMD, "args": []}
    assert (tmp_path / "claude_desktop_config.json.bak").exists()


def test_json_creates_missing_file_and_refuses_broken_one(tmp_path):
    new = tmp_path / "sub" / "mcp.json"
    _add_to_json(new, CMD)
    assert json.loads(new.read_text())["mcpServers"][NAME]["command"] == CMD
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert _add_to_json(broken, CMD).startswith("skipped")
    assert broken.read_text() == "{not json"


def test_codex_appends_once_with_long_timeout(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "gpt-5"\n')
    assert _add_to_codex(cfg, CMD).startswith("connected")
    assert _add_to_codex(cfg, CMD).startswith("already")
    text = cfg.read_text()
    assert text.startswith('model = "gpt-5"\n') and text.count(f"[mcp_servers.{NAME}]") == 1
    assert f"command = '{CMD}'" in text and "tool_timeout_sec = 300" in text


def test_codex_windows_path_is_literal(tmp_path):
    cfg = tmp_path / "config.toml"
    _add_to_codex(cfg, r"C:\Users\me\.local\bin\ibi-portfolio-mcp.exe")
    assert r"command = 'C:\Users\me\.local\bin\ibi-portfolio-mcp.exe'" in cfg.read_text()


def test_env_wins_over_vault(monkeypatch):
    monkeypatch.setenv("IBI_USER", "env-user")
    monkeypatch.setenv("IBI_PASS", "env-pass")
    monkeypatch.setattr(credentials, "_from_vault", lambda key: "vault-value")
    assert credentials.get_credentials() == ("env-user", "env-pass")


def test_vault_used_when_env_empty(monkeypatch):
    for v in ("IBI_USER", "IBI_PASS", "IBI_USER_CMD", "IBI_PASS_CMD"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(credentials, "_from_vault", lambda key: {"username": "u", "password": "p"}[key])
    assert credentials.get_credentials() == ("u", "p")
