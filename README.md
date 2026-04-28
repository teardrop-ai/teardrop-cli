# teardrop-cli

Command-line interface for [Teardrop](https://teardrop.dev) — the crypto-native AI agent platform. Publish tools to the marketplace, subscribe to third-party tools, run agents, manage USDC billing, and configure bring-your-own-key LLM settings, all from a single CLI.

---

## Requirements

- Python ≥ 3.11
- A Teardrop account ([sign up](https://teardrop.dev))

---

## Installation

```bash
pip install teardrop-cli
teardrop --version
```

---

## Quick Start

```bash
# 1. Install
pip install teardrop-cli

# 2. Log in (prompts for email + password if flags are omitted)
teardrop auth login --email you@example.com --secret ••••

# 3. Run your first agent prompt
teardrop run "What is the current ETH gas price?"
```

---

## Authentication

### Login flows

```bash
# Email + password
teardrop auth login --email you@example.com --secret ••••

# Machine-to-machine (client credentials)
teardrop auth login --client-id <id> --client-secret <secret>

# Pre-issued JWT
teardrop auth login --token <jwt>

# Sign-In With Ethereum (EIP-4361)
# macOS / Linux
export TEARDROP_SIWE_PRIVATE_KEY=0x<private-key>
# Windows (PowerShell)
$env:TEARDROP_SIWE_PRIVATE_KEY = "0x<private-key>"

teardrop auth login --siwe
```

### Identity & session

```bash
teardrop auth status        # show authenticated identity
teardrop auth status --json # as JSON
teardrop auth logout        # revoke refresh token and clear stored credentials
```

### Credential resolution order

At runtime, credentials are resolved in this priority order:

| Priority | Source |
|----------|--------|
| 1 | `TEARDROP_API_KEY` env var (static JWT) |
| 2 | `TEARDROP_EMAIL` + `TEARDROP_SECRET` env vars |
| 3 | `TEARDROP_CLIENT_ID` + `TEARDROP_CLIENT_SECRET` env vars |
| 4 | `access_token` in `~/.teardrop/config.toml` |
| 5 | System keyring (email + secret, or client credentials) |

---

## Running Agents

```bash
# Basic prompt (streams Markdown to the terminal)
teardrop run "Summarize the latest ETH gas trends"

# Continue an existing conversation thread
teardrop run "Follow up on that" --thread <thread-id>

# Attach structured context
teardrop run "Process this order" --context '{"order_id": "ord_123"}'

# Collect the full response before printing (no streaming)
teardrop run "Give me a report" --no-stream

# Machine-readable JSON output
teardrop run "..." --json
```

Streaming output renders Markdown live. Tool calls appear inline as they execute. A token + cost summary is printed at the end of each run.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (auth, rate limit, API, insufficient credit) |
| 2 | Invalid `--context` JSON |

If you hit a credit error, top up with `teardrop topup stripe --amount 10.00`.

---

## Billing & Credits

### Check balance and usage

```bash
teardrop balance             # credit balance, spending limit, daily spend
teardrop balance --json

teardrop usage               # token and run totals (all time)
teardrop usage --start 2026-01-01 --end 2026-01-31
teardrop usage --json
```

### Top up via Stripe (credit card)

```bash
teardrop topup stripe --amount 25.00
```

Opens a Stripe checkout page in your browser. The CLI polls for completion and prints your new balance when payment is confirmed. Add `--no-browser` to print the checkout URL instead of auto-opening it.

### Top up via USDC (on-chain)

```bash
teardrop topup usdc --amount 25.00
```

Prints an x402 payment description — a set of on-chain USDC payment requirements specifying the receiving address, amount, and chain. Send the exact amount to the given address using any USDC-compatible wallet; your balance updates automatically once the transaction confirms.

---

## Tool Marketplace

The marketplace lets your org **consume** tools published by other organizations and **publish** tools of your own to earn USDC per call.

---

### Browsing & Subscribing (consumers)

No authentication required to browse.

```bash
# List all published tools
teardrop marketplace list
teardrop marketplace list --category data --json

# Search by keyword (client-side filter across name + description)
teardrop marketplace search "weather"
teardrop marketplace search "onchain price feed"

# Inspect a tool's schema and pricing before subscribing
teardrop marketplace info acme/weather

# Subscribe your org (one-time confirmation prompt)
teardrop marketplace subscribe acme/weather
teardrop marketplace subscribe acme/weather --yes    # skip confirmation

# View your active subscriptions
teardrop marketplace subscriptions
teardrop marketplace subscriptions --json

# Unsubscribe
teardrop marketplace unsubscribe acme/weather
```

Once subscribed, the tool is immediately available to your agent — no restart required.

---

### Publishing a Tool (publishers)

#### Interactive wizard

```bash
teardrop tools publish
```

The wizard prompts for name, description, webhook URL, timeout, price, and input schema. It also asks whether to list the tool on the public marketplace.

#### From a JSON spec file (recommended for CI/CD)

```bash
teardrop tools publish --from-file tool.json
```

Example `tool.json`:

```json
{
  "name": "get_weather",
  "description": "Fetch current weather conditions for a given city.",
  "webhook_url": "https://api.example.com/webhooks/teardrop",
  "input_schema": {
    "type": "object",
    "properties": {
      "city": { "type": "string", "description": "City name, e.g. 'London'" }
    },
    "required": ["city"]
  },
  "timeout_seconds": 10,
  "publish_as_mcp": true,
  "marketplace_description": "Real-time weather data for any city worldwide.",
  "base_price_usdc": 5000
}
```

> `base_price_usdc` is in atomic USDC units (6 decimal places): `5000` = **$0.005000** per call.

**Tool name rules:** lowercase letters, digits, and underscores only; must start with a letter; maximum 64 characters (`^[a-z][a-z0-9_]*$`).

#### Set your settlement wallet (required before first payout)

Pass `--settlement-wallet` at publish time to register the EIP-55 checksum address where marketplace earnings are sent:

```bash
teardrop tools publish \
  --from-file tool.json \
  --settlement-wallet 0xYourChecksumAddress
```

Or on Windows PowerShell (single line):

```powershell
teardrop tools publish --from-file tool.json --settlement-wallet 0xYourChecksumAddress
```

You only need to do this once. To update it later, re-run publish with the new address.

#### Manage existing tools

```bash
# List all org tools
teardrop tools list
teardrop tools list --json

# Inspect a tool's full schema and configuration
teardrop tools info get_weather

# Update individual fields (only supplied flags are changed)
teardrop tools update get_weather --price 0.003
teardrop tools update get_weather --description "Updated description" --publish

# Pause (disable) a tool — subscribers lose access until re-enabled
teardrop tools pause get_weather
teardrop tools update get_weather --active    # re-enable

# Delete a tool permanently
teardrop tools delete get_weather
teardrop tools delete get_weather --yes    # skip confirmation
```

---

### Earnings & Withdrawals (publishers)

```bash
# Marketplace earnings balance
teardrop earnings balance
teardrop earnings balance --json

# Per-call earnings history
teardrop earnings history
teardrop earnings history --limit 50 --tool get_weather
teardrop earnings history --json

# Withdraw to your settlement wallet
teardrop earnings withdraw 10.00             # prompts for confirmation
teardrop earnings withdraw 10.00 --yes       # skip confirmation

# Withdrawal history
teardrop earnings withdrawals
teardrop earnings withdrawals --limit 20 --json
```

Withdrawals are processed on-chain. Funds typically arrive within 1–5 minutes.

---

## LLM Configuration

Configure the model, routing strategy, and API key used by your org's agents. Settings are applied globally across all agent runs.

### Get and delete

```bash
# Show current configuration (cached for 5 minutes)
teardrop llm-config get
teardrop llm-config get --json
teardrop llm-config get --no-cache    # force refresh

# Revert to platform global defaults
teardrop llm-config delete
teardrop llm-config delete --yes      # skip confirmation
```

### Set model and routing

Teardrop offers three production models, each optimized for a routing tier:

```bash
# Cost tier (DeepSeek V4 Flash via OpenRouter)
teardrop llm-config set --provider openrouter --model deepseek-chat --routing cost

# Speed tier (Gemini 3 Flash)
teardrop llm-config set --provider google --model gemini-3-flash --routing speed

# Quality tier (Claude Sonnet 4.6 — default)
teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --routing quality

# Advanced tuning (optional)
teardrop llm-config set \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --max-tokens 8000 \
  --temperature 0.7 \
  --timeout-seconds 60
```

**Supported providers:** `openrouter`, `google`, `anthropic`

**Routing preferences:** `default` · `cost` · `speed` · `quality`

**Validation:** temperature 0.0–2.0 · max tokens 1–200,000 · timeout ≥ 1 s

### Bring-your-own-key (BYOK)

Use your own provider API key — Teardrop's shared key is bypassed entirely.

```bash
# Inline (key visible in shell history — acceptable for non-sensitive dev use)
teardrop llm-config set \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --byok-key $ANTHROPIC_API_KEY

# Secure stdin pipe (key never appears in history or process list)
# macOS / Linux
cat "$key_file" | teardrop llm-config set \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --byok-key -

# Windows (PowerShell)
Get-Content "$key_file" | teardrop llm-config set `
  --provider anthropic `
  --model claude-sonnet-4-6 `
  --byok-key -

# Remove BYOK key and revert to platform shared key
teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --clear-key
```

### Teardrop platform models

All available models are hosted on the Teardrop platform. To use a different provider's API key with BYOK, set it alongside one of the three supported models.

---

## MCP Servers

Attach external [Model Context Protocol](https://modelcontextprotocol.io) servers to your org. Any tools they expose become available to your agents automatically.

```bash
# List connected servers
teardrop mcp list
teardrop mcp list --json

# Add a server
teardrop mcp add --name "my-server" --url https://mcp.example.com
teardrop mcp add --name "secure" --url https://mcp.example.com \
  --auth-type bearer --auth-token <token>

# Inspect the tools a server exposes
teardrop mcp discover <server-id>

# Remove a server
teardrop mcp remove <server-id>
teardrop mcp remove <server-id> --yes    # skip confirmation
```

---

## Models & Benchmarks

```bash
# Public catalogue — no authentication required
teardrop models benchmarks
teardrop models benchmarks --json
teardrop models benchmarks --no-cache    # bypass 10-minute local cache

# Your org's actual performance metrics (authentication required)
teardrop models benchmarks --org <org-id>
teardrop models benchmarks --org <org-id> --force-refresh
```

The public table shows model details, P95 latency, per-token pricing, and 7-day run volume across all three tiers (cost, speed, quality). The org-scoped table shows your average latency, cost per run, and tokens per second for your selected routing preference.

---

## Configuration File

Config is stored at `~/.teardrop/config.toml` and created automatically on first login. The file is restricted to owner read/write (`0600` on POSIX). Sensitive secrets (passwords, tokens) are stored in the **system keyring**, not in the file.

### Read and write config values

```bash
# Show all stored values (tokens redacted to first 12 characters)
teardrop config list
teardrop config list --json

# Read or write a single key
teardrop config get api_url
teardrop config set api_url https://api.teardrop.dev

# Create the config file explicitly (useful for bootstrap scripts)
teardrop init
teardrop init --base-url https://api.teardrop.dev
```

Writable keys: `api_url`, `email`, `org_id`. Tokens and secrets are managed only via `auth login` and `auth logout`.

---

## Development

```bash
git clone https://github.com/teardrop-ai/teardrop-cli
cd teardrop-cli
pip install -e ".[dev]"
```

### Test tiers

| Command | What runs | Network required |
|---------|-----------|-----------------|
| `pytest` | Unit tests + smoke tests + perf assertions | No |
| `pytest -m smoke` | Subprocess-based hermetic smoke tests only | No |
| `pytest -m perf` | Startup performance assertions only | No |
| `pytest -m e2e` | Live API tests (skipped without credentials) | Yes |

**Run unit + smoke tests (default):**

```bash
pytest
```

**Run live end-to-end tests:**

```bash
# Token auth
TEARDROP_E2E=1 TEARDROP_E2E_TOKEN=<jwt> pytest -m e2e

# Email + secret auth
TEARDROP_E2E=1 TEARDROP_E2E_EMAIL=you@example.com TEARDROP_E2E_SECRET=•••• pytest -m e2e
```

See [`tests/e2e/README.md`](tests/e2e/README.md) for the full environment variable reference and per-test descriptions.

**Lint and format:**

```bash
ruff check src tests
ruff format src tests
```

**Test fixtures** in `src/teardrop_cli/_fixtures.py`:

| Helper | Returns |
|--------|---------|
| `make_jwt_payload(sub, org, role)` | Mock JWT payload |
| `make_sse_events(text)` | SSE event sequence (text chunk → usage → done) |
| `make_llm_config(...)` | Mock `OrgLlmConfig` |
| `make_benchmarks_response(models)` | Mock benchmarks response |
