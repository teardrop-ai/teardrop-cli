# teardrop-cli

Command-line interface for the [Teardrop](https://teardrop.dev) crypto-native AI agent platform. Authenticate, run prompts against agents, manage marketplace earnings, configure MCP servers, and inspect organization tools.

---

## Requirements

- Python ≥ 3.11
- A Teardrop account (email/password, M2M client credentials, Ethereum wallet, or pre-issued JWT)

---

## Installation

```bash
git clone https://github.com/teardrop-ai/teardrop-cli
cd teardrop-cli
pip install -e .
```

The entry point is `teardrop`.

---

## Authentication

Credentials are resolved in this priority order at runtime:

| Priority | Source |
|----------|--------|
| 1 | `TEARDROP_TOKEN` env var (static JWT) |
| 2 | `TEARDROP_EMAIL` + `TEARDROP_SECRET` env vars |
| 3 | `TEARDROP_CLIENT_ID` + `TEARDROP_CLIENT_SECRET` env vars |
| 4 | System keyring |
| 5 | Config file (`~/.config/teardrop/config.toml`) |

### Login flows

```bash
# Email + password (interactive prompts if flags omitted)
teardrop auth login --email user@example.com --secret ••••

# Machine-to-machine (client credentials)
teardrop auth login --client-id <id> --client-secret <secret>

# Sign-In With Ethereum (EIP-4361)
teardrop auth login --siwe          # prompts for private key

# Pre-issued JWT
teardrop auth login --token <jwt>
```

```bash
teardrop auth whoami            # show current identity
teardrop auth whoami --json     # as JSON
teardrop auth logout            # clear all stored credentials
```

Override the API endpoint for any command with `--base-url <url>` (hidden flag).

---

## Agent

### Run a prompt

```bash
teardrop agent run "Summarize the latest ETH gas trends"

# Continue an existing thread
teardrop agent run "Follow up on that" --thread-id <id>

# Override model
teardrop agent run "..." --model gpt-4o

# Machine-readable: one JSON object per line (SSE event passthrough)
teardrop agent run "..." --json
```

Streaming output renders Markdown live in the terminal. Tool calls are shown inline as they execute. A usage summary (input/output tokens + cost) is printed at the end.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Insufficient balance (`PaymentRequiredError`) |
| 3 | Rate limited (`RateLimitError`) |
| 5 | Agent stream error |
| 130 | Interrupted (`Ctrl-C`) |

---

## Marketplace

```bash
# Current balance
teardrop marketplace balance
teardrop marketplace balance --json

# Earnings history
teardrop marketplace earnings
teardrop marketplace earnings --limit 50 --cursor <cursor>

# Withdraw USDC
teardrop marketplace withdraw --amount-usdc 100 --payout-address 0x...
teardrop marketplace withdraw --amount-usdc 100 --payout-address 0x... --yes   # skip confirm

# Register payout address for marketplace listings
teardrop marketplace publish --payout-address 0x...
```

---

## MCP Servers

Manage Model Context Protocol servers attached to your organization.

```bash
# List registered servers
teardrop mcp list

# Add a server
teardrop mcp add --name "my-server" --url https://mcp.example.com
teardrop mcp add --name "secure" --url https://mcp.example.com \
    --auth-type bearer --auth-token <token>

# Discover tools exposed by a server
teardrop mcp discover <server-id>

# Remove a server
teardrop mcp remove <server-id>
teardrop mcp remove <server-id> --yes    # skip confirm
```

---

## Tools

Inspect and dry-run validate organization tools.

```bash
# List all tools
teardrop tools list
teardrop tools list --json

# Show a tool's schema and optionally validate input
teardrop tools test <tool-id>
teardrop tools test <tool-id> --input '{"param": "value"}'
```

`--input` performs local validation: checks required fields are present and types match the schema before any network call.

---

## Configuration

The config file lives at the platform-appropriate path (e.g., `~/.config/teardrop/config.toml` on Linux/macOS). It is created automatically on first login and restricted to owner-read (`0o600` on POSIX).

Sensitive secrets (passwords, tokens) are stored in the **system keyring**; only non-secret fields (email, client_id) are written to the config file.

```toml
# ~/.config/teardrop/config.toml
base_url = "https://api.teardrop.dev"   # optional override
```

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src tests
```

**Testing utilities** in `src/teardrop_cli/_fixtures.py`:
- `make_jwt_payload(sub, org, role)` — mock JWT payload
- `make_sse_events(text)` — mock SSE event sequence (text chunk → usage → done)

All async tests use `asyncio_mode = "auto"` (configured in `pyproject.toml`).
