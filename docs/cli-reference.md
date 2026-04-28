# teardrop-cli — Full Reference

This document covers every flag, env var, and subcommand. For the quick path, start with the [README](../README.md).

---

## Table of Contents

- [Authentication](#authentication)
- [Running Agents](#running-agents)
- [Billing & Credits](#billing--credits)
- [Tool Management](#tool-management)
- [Marketplace](#marketplace)
- [Earnings & Withdrawals](#earnings--withdrawals)
- [LLM Configuration](#llm-configuration)
- [MCP Servers](#mcp-servers)
- [Models & Benchmarks](#models--benchmarks)
- [Configuration File](#configuration-file)
- [Exit Codes](#exit-codes)
- [Development](#development)

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

# Sign-In With Ethereum (EIP-4361) — pick one source for the key:
teardrop auth login --siwe                              # interactive hidden prompt
teardrop auth login --siwe --key-file ./wallet.key      # read once, never persisted
teardrop auth login --siwe --generate-wallet            # creates a fresh wallet
TEARDROP_SIWE_PRIVATE_KEY=0x... teardrop auth login --siwe   # CI / non-interactive
```

The CLI never writes your private key to disk. After signing the SIWE message it scrubs the key from process memory.

### Signup

```bash
teardrop auth signup                              # interactive
teardrop auth signup --email you@example.com --org-name acme
teardrop auth signup --json                       # JWT response as JSON
```

Calls `POST /register`. Password rules: ≥ 8 characters, ≥ 1 digit. Org name 1–200 chars. Rate-limited to 3 signups/min/email. On success the JWT is stored locally.

### Identity & session

```bash
teardrop auth status               # show authenticated identity
teardrop auth status --json
teardrop auth logout               # revoke refresh token + clear stored credentials
```

### Credential resolution order

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
teardrop run "Summarize the latest ETH gas trends"
teardrop run "Follow up on that" --thread <thread-id>
teardrop run "Process this order" --context '{"order_id":"ord_123"}'
teardrop run "Give me a report" --no-stream
teardrop run "..." --json
```

Streaming output renders Markdown live with inline tool calls. A token + cost summary prints at the end.

---

## Billing & Credits

```bash
teardrop balance                       # credit balance, spending limit, daily spend
teardrop balance --json
teardrop usage                         # token + run totals (all time)
teardrop usage --start 2026-01-01 --end 2026-01-31
teardrop usage --json
```

### Top up via Stripe (credit card)

```bash
teardrop topup stripe --amount 25.00
teardrop topup stripe --amount 25.00 --no-browser     # print URL instead of opening browser
```

The CLI polls for completion and prints the new balance when payment confirms.

### Top up via USDC (on-chain)

```bash
teardrop topup usdc --amount 25.00
```

Prints an x402 payment description. Send USDC to the given address; balance updates after the tx confirms.

---

## Tool Management

### Scaffold

```bash
teardrop tools init <name>                          # writes ./tool.json
teardrop tools init my_tool --out custom.json --force
teardrop tools init premium --with-marketplace      # include MCP + price fields
```

### Publish

```bash
teardrop tools publish                              # interactive wizard
teardrop tools publish --from-file tool.json
teardrop tools publish --from-file tool.json --settlement-wallet 0xYourChecksumAddress
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

`base_price_usdc` is in atomic USDC (6 decimals): `5000` = **$0.005** per call. Tool name rules: `^[a-z][a-z0-9_]*$`, ≤ 64 chars.

### Manage

```bash
teardrop tools list
teardrop tools info get_weather
teardrop tools update get_weather --price 0.003
teardrop tools update get_weather --description "Updated" --publish
teardrop tools pause get_weather
teardrop tools update get_weather --active           # re-enable
teardrop tools delete get_weather
teardrop tools delete get_weather --yes              # skip confirmation
```

---

## Marketplace

```bash
teardrop marketplace list
teardrop marketplace list --category data --json
teardrop marketplace search "weather"
teardrop marketplace info acme/weather
teardrop marketplace subscribe acme/weather
teardrop marketplace subscribe acme/weather --yes    # skip confirmation
teardrop marketplace subscriptions
teardrop marketplace unsubscribe acme/weather
```

Browsing requires no authentication.

---

## Earnings & Withdrawals

```bash
teardrop earnings balance
teardrop earnings history --limit 50 --tool get_weather
teardrop earnings withdraw 10.00
teardrop earnings withdraw 10.00 --yes
teardrop earnings withdrawals --limit 20 --json
```

Withdrawals settle on-chain to your registered settlement wallet, typically within 1–5 minutes.

---

## LLM Configuration

```bash
teardrop llm-config get                              # current config (5-min cache)
teardrop llm-config get --json --no-cache
teardrop llm-config delete                           # revert to platform defaults
teardrop llm-config byok                             # interactive BYOK wizard
```

### Set model and routing

```bash
# Cost tier
teardrop llm-config set --provider openrouter --model deepseek-chat --routing cost

# Speed tier
teardrop llm-config set --provider google --model gemini-3-flash --routing speed

# Quality tier (default)
teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --routing quality

# Advanced tuning
teardrop llm-config set \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --max-tokens 8000 \
  --temperature 0.7 \
  --timeout-seconds 60
```

**Providers:** `openrouter`, `google`, `anthropic`
**Routing:** `default` · `cost` · `speed` · `quality`
**Validation:** temperature 0.0–2.0 · max tokens 1–200,000 · timeout ≥ 1 s

### Bring-your-own-key (BYOK)

```bash
# Inline (visible in shell history)
teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --byok-key $ANTHROPIC_API_KEY

# Stdin pipe (no shell history)
cat "$key_file" | teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --byok-key -

# PowerShell
Get-Content "$key_file" | teardrop llm-config set `
  --provider anthropic --model claude-sonnet-4-6 --byok-key -

# Remove BYOK key
teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --clear-key
```

---

## MCP Servers

Attach external [Model Context Protocol](https://modelcontextprotocol.io) servers. Their tools become available to your agents automatically.

```bash
teardrop mcp list
teardrop mcp add --name "my-server" --url https://mcp.example.com
teardrop mcp add --name "secure" --url https://mcp.example.com \
  --auth-type bearer --auth-token <token>
teardrop mcp discover <server-id>
teardrop mcp remove <server-id> --yes
```

---

## Models & Benchmarks

```bash
teardrop models benchmarks                           # public catalogue (no auth)
teardrop models benchmarks --json --no-cache
teardrop models benchmarks --org <org-id>            # your org's actual metrics
teardrop models benchmarks --org <org-id> --force-refresh
```

Public benchmarks show P95 latency, per-token pricing, and 7-day run volume per tier. Org-scoped benchmarks show your average latency, cost per run, and tokens per second.

---

## Configuration File

Stored at `~/.teardrop/config.toml`. Created automatically on first login. Mode `0600` on POSIX. Sensitive secrets (passwords, tokens) live in the **system keyring**, never in this file.

```bash
teardrop config list                  # tokens redacted to first 12 chars
teardrop config get api_url
teardrop config set api_url https://api.teardrop.dev

teardrop init                         # explicit bootstrap
teardrop init --base-url https://api.teardrop.dev
```

Writable keys: `api_url`, `email`, `org_id`. Tokens and secrets are managed only via `auth login` / `auth logout`.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (auth, rate limit, API, insufficient credit) |
| 2 | Invalid input (e.g. malformed `--context` JSON) |

---

## Development

```bash
git clone https://github.com/teardrop-ai/teardrop-cli
cd teardrop-cli
pip install -e ".[dev]"
```

### Test tiers

| Command | What runs | Network |
|---------|-----------|---------|
| `pytest` | Unit + smoke + perf | No |
| `pytest -m smoke` | Subprocess-hermetic smoke only | No |
| `pytest -m perf` | Startup performance assertions only | No |
| `pytest -m e2e` | Live API tests (skipped without creds) | Yes |

### Live end-to-end tests

```bash
TEARDROP_E2E=1 TEARDROP_E2E_TOKEN=<jwt> pytest -m e2e
TEARDROP_E2E=1 TEARDROP_E2E_EMAIL=you@example.com TEARDROP_E2E_SECRET=•••• pytest -m e2e
```

See [`tests/e2e/README.md`](../tests/e2e/README.md) for the full env var reference.

### Lint and format

```bash
ruff check src tests
ruff format src tests
```

### Test fixtures (`src/teardrop_cli/_fixtures.py`)

| Helper | Returns |
|--------|---------|
| `make_jwt_payload(sub, org, role)` | Mock JWT payload |
| `make_sse_events(text)` | SSE event sequence (text → usage → done) |
| `make_llm_config(...)` | Mock `OrgLlmConfig` |
| `make_benchmarks_response(models)` | Mock benchmarks response |
