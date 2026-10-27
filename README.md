# ibi-portfolio-mcp

**A read-only MCP server for IBI (Israel Brokerage & Investments, אי.בי.אי).** It lets Claude, ChatGPT, Cursor or any MCP client read your IBI portfolio (positions, cash, profit/loss and recent account activity) so you can ask things like *"how is my portfolio doing?"*. It **cannot buy, sell or move money**.

> 🇮🇱 שרת MCP לקריאה בלבד עבור חשבון המסחר שלך באי.בי.אי (IBI NextGen). הוא נותן ל-Claude או לכל עוזר AI אחר לראות את תיק ההשקעות שלך: אחזקות, מזומן, רווח והפסד ופעולות אחרונות. הוא לא יכול לבצע פקודות קנייה או מכירה. הסיסמה נשארת אצלך במחשב ולא מגיעה למודל.

Unofficial. Not affiliated with or endorsed by IBI.

## What you get

| Tool | What it returns |
|---|---|
| `get_portfolio` | Total value, cash, cash %, total P/L, and every position: symbol, quantity, cost, market value, P/L, weight |
| `get_account_activity` | Recent orders and executions: buy/sell, status, quantity, price, fees, dates |

Example questions once it is connected:
- "What's my IBI portfolio worth and how much cash do I have?"
- "Which 5 positions are the biggest, and what is the P/L on each?"
- "What did I buy or sell this month?"

## Read-only, on purpose

| | |
|---|---|
| ✅ Reads positions, balances, account activity | The same data you see on the IBI home page and the Trading page |
| ❌ Place, change or cancel orders | Not in the code. The only clicks are Login, the login form's submit and the "Latest Account Activity" tab |
| ❌ Transfers or withdrawals | Not in the code |
| 🛡️ Network guard | Any non-GET request to an `order` / `trade` / `transfer` / `withdraw` / `deposit` URL is aborted, and the tool result tells you if that ever happened |

Your login gives full access to your account, so read [`scraper.py`](src/ibi_portfolio_mcp/scraper.py) yourself before using this. It is about 200 lines.

## Which IBI accounts work

- ✅ **IBI NextGen** (the US-stocks platform at `ibi.orbisfn.io`, English UI)
- ❌ Other IBI platforms (for example the Israeli TASE trading site) are not supported yet. PRs welcome.

## Install

You need Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/kobimantzur/ibi-portfolio-mcp
cd ibi-portfolio-mcp
uv sync
uv run playwright install chromium
```

Then store your password (next section) and test it from a terminal:

```bash
uv run ibi-portfolio-mcp check
# OK: 12 positions, total 48,210.55 USD, source json, 20 activity rows
```

## Your IBI password (secrets)

This is the part to get right, so here is exactly what happens.

### What the server needs

Your IBI NextGen **username** (email or ID) and **password**, the same ones you type at `ibi.orbisfn.io`. IBI has no API and no read-only keys, so the server logs in the way you do: it opens a hidden Chrome window on your own computer and types them into IBI's real login page.

### Where your password goes, and where it does not

| | |
|---|---|
| ✅ Your computer | Read from your keychain, password manager or environment when a tool runs |
| ✅ IBI's login page (`auth.ibi.co.il`) | Typed into the form, inside a local browser, over HTTPS |
| ❌ The AI model / Anthropic / OpenAI | Never. Tools take no password argument and never return it |
| ❌ Logs | Never printed. Errors from your password command are not echoed |
| ❌ Disk | No cookies, tokens or sessions are saved. Each read is a fresh browser that is closed after |
| ❌ Anyone else | No server, no telemetry. The code talks only to IBI |

**What the AI does see:** your portfolio numbers. Whatever a tool returns goes to your AI provider like any other chat message. If that is not OK for you, do not connect this server.

### Ways to give it the password (best first)

| Option | How | Password stored as plain text? |
|---|---|---|
| 1. macOS Keychain ✅ recommended | `IBI_PASS_CMD` runs a command that prints the password | ❌ No |
| 2. Password manager CLI ✅ | Same, with `op`, `bw`, `bws` and similar | ❌ No |
| 3. MCP client config | `IBI_PASS` in the client's `env` block | ⚠️ Yes, in that config file |
| 4. `.env` file | `IBI_PASS` in a `.env` file (gitignored) | ⚠️ Yes, in that file |

**Option 1: macOS Keychain.** Save it once (it asks for the password, so it never lands in your shell history):

```bash
security add-generic-password -s ibi-portfolio-mcp -a ibi -w
```

Then set:

```
IBI_USER=your-email-or-id
IBI_PASS_CMD=security find-generic-password -s ibi-portfolio-mcp -a ibi -w
```

The first time it runs, macOS may ask whether to allow access. Choose "Always Allow".

**Option 2: password manager.** Any command that prints only the password works:

```
IBI_PASS_CMD=op read op://Private/IBI/password          # 1Password CLI
IBI_PASS_CMD=bw get password ibi.orbisfn.io             # Bitwarden CLI (vault must be unlocked)
IBI_PASS_CMD=secret-tool lookup service ibi             # Linux keyring
```

`IBI_USER_CMD` works the same way for the username.

**Options 3 and 4.** `IBI_PASS` set directly. Simple, but the password sits in a plain file: keep that file private (`chmod 600`) and never commit it. `.env` is already in `.gitignore`. The server loads `.env` from the folder it starts in, or the file named in `IBI_ENV_FILE`. Real environment variables win over the file.

### SMS code (two-factor)

If IBI asks for a one-time code, the tool returns an `IbiOtpRequired` error. Set `IBI_HEADED=1`: a visible browser window opens, the server fills in your username and password, and you type the code yourself. You get 3 minutes.

### If you think your password leaked

Change it at IBI. Then update your keychain entry or config.

## Connect it to your AI app

All examples use the Keychain setup above. Replace `/path/to/ibi-portfolio-mcp` with where you cloned it.

**Claude Code**

```bash
claude mcp add --scope user ibi-portfolio \
  -e IBI_USER=your-email-or-id \
  -e 'IBI_PASS_CMD=security find-generic-password -s ibi-portfolio-mcp -a ibi -w' \
  -- uv run --directory /path/to/ibi-portfolio-mcp ibi-portfolio-mcp
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`), **Cursor** (`~/.cursor/mcp.json`) and most other clients:

```json
{
  "mcpServers": {
    "ibi-portfolio": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ibi-portfolio-mcp", "ibi-portfolio-mcp"],
      "env": {
        "IBI_USER": "your-email-or-id",
        "IBI_PASS_CMD": "security find-generic-password -s ibi-portfolio-mcp -a ibi -w"
      }
    }
  }
}
```

Restart the app after editing. If `uv` is not found, use its full path (`which uv`).

## Settings

| Variable | Default | What it does |
|---|---|---|
| `IBI_USER` / `IBI_USER_CMD` | | Username, or a command that prints it |
| `IBI_PASS` / `IBI_PASS_CMD` | | Password, or a command that prints it |
| `IBI_ENV_FILE` | `./.env` | Extra env file to load |
| `IBI_HEADED` | `0` | `1` shows the browser window (needed for SMS codes) |
| `IBI_LOGIN_TIMEOUT_S` | `90` (`180` headed) | How long to wait for login |
| `IBI_CACHE_SECONDS` | `300` | Reuse the last read for this long, so one chat does not log in again and again |
| `IBI_DEBUG_DIR` | off | Saves screenshots and raw JSON there. They contain your balances: delete them when done |

## How it works

1. A tool is called. If the last read is newer than `IBI_CACHE_SECONDS`, it is returned as is.
2. Otherwise a fresh headless Chromium opens `ibi.orbisfn.io` and logs in with your credentials.
3. The IBI web app loads your data from its own backend. The server keeps a copy of those JSON responses (portfolio, balance, latest activity) and reads the page as a fallback.
4. The browser is closed and the numbers are returned. Nothing is written to disk.

A read takes about 30 to 60 seconds. If IBI changes its website this can break; open an issue with the error text (never paste your password or screenshots with your balances).

## Troubleshooting

| Error | Fix |
|---|---|
| `MissingCredentials` | `IBI_USER` and `IBI_PASS` / `IBI_PASS_CMD` are not reaching the server. Put them in the client's `env` block |
| `IBI_PASS_CMD failed` | Run that command in a terminal; it must print only the password |
| `IbiOtpRequired` | Set `IBI_HEADED=1` and type the SMS code in the window |
| `login did not reach the IBI home page` | Wrong username or password, or IBI shows a notice. Try `IBI_HEADED=1` to watch |
| `Executable doesn't exist` | Run `uv run playwright install chromium` |

## Development

```bash
uv run pytest -q
```

Tests use made-up numbers only. Never commit real account data.

## Disclaimer

Unofficial project, not affiliated with IBI Israel Brokerage & Investments. It automates your own login to read your own data; check that this fits IBI's terms of use for your account. Use at your own risk. Nothing here is investment advice. MIT license.
