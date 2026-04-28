# teardrop-cli

The fastest way to **publish a tool, run an agent, and earn USDC** — straight from your terminal.

[Teardrop](https://teardrop.dev) is the crypto-native AI agent platform. Tool authors publish webhooks, get paid per call in USDC, and never touch a dashboard. Agent users run prompts that automatically discover and pay for the right tools.

```bash
pip install teardrop-cli
teardrop quickstart        # 60-second guided onboarding
```

> Already onboarded? Jump to [Run an Agent](#run-an-agent) or [Publish a Tool](#publish-a-tool).

---

## Install

```bash
pip install teardrop-cli
teardrop --version
```

Requires Python ≥ 3.11.

---

## 60-Second Quickstart

The wizard walks you through sign-in, BYOK LLM setup, and your first agent run or scaffolded tool:

```bash
teardrop quickstart
```

Prefer the manual path? Pick a sign-in method:

```bash
# Wallet-first (no email needed) — generates a wallet on first run if you don't have one
teardrop auth login --siwe --generate-wallet

# Email + password
teardrop auth signup --email you@example.com --org-name acme

# Already have an account
teardrop auth login --email you@example.com
```

Then run your first agent:

```bash
teardrop run "Summarize the latest ETH gas trends"
```

---

## Sign In

| Goal | Command |
|------|---------|
| Create account & org | `teardrop auth signup` |
| Sign in with wallet (existing key) | `teardrop auth login --siwe --key-file wallet.key` |
| Generate a new wallet & sign in | `teardrop auth login --siwe --generate-wallet` |
| Email + password | `teardrop auth login --email you@example.com` |
| Pre-issued JWT | `teardrop auth login --token <jwt>` |
| Show identity | `teardrop auth status` |
| Sign out | `teardrop auth logout` |

Private keys are never persisted by the CLI. Sessions are stored in your OS keyring.

For machine-to-machine credentials, env-var precedence, and CI patterns, see [docs/cli-reference.md](docs/cli-reference.md#authentication).

---

## Publish a Tool

Scaffold a starter spec, edit it, and publish:

```bash
teardrop tools init my_scraper       # writes ./tool.json
$EDITOR tool.json                    # set webhook_url, schema, price
teardrop tools publish --from-file tool.json \
    --settlement-wallet 0xYourChecksumAddress
```

Or run the interactive wizard:

```bash
teardrop tools publish
```

Tool name rules: `^[a-z][a-z0-9_]*$`, ≤ 64 chars. Prices are in atomic USDC (6 decimals): `5000` = **$0.005** per call. Settlement wallet is required once before your first payout.

Manage existing tools: `teardrop tools list | info | update | pause | delete`. Full reference: [docs/cli-reference.md](docs/cli-reference.md#tool-management).

---

## Earn

```bash
teardrop earnings balance            # marketplace balance
teardrop earnings history            # per-call history
teardrop earnings withdraw 10.00     # to your settlement wallet
teardrop earnings withdrawals        # past payouts
```

On-chain withdrawals typically settle in 1–5 minutes.

---

## Run an Agent

```bash
teardrop run "What is the current ETH gas price?"

# Continue a thread
teardrop run "Follow up" --thread <thread-id>

# Pass structured context
teardrop run "Process this order" --context '{"order_id":"ord_123"}'

# Machine-readable output
teardrop run "..." --json --no-stream
```

Streaming output renders Markdown live with inline tool calls. A token + cost summary prints at the end.

If a run fails on credit, top up:

```bash
teardrop topup stripe --amount 25.00     # credit card
teardrop topup usdc   --amount 25.00     # on-chain x402
teardrop balance
```

---

## Configure Your LLM

One-shot bring-your-own-key wizard:

```bash
teardrop llm-config byok
```

Or set explicitly:

```bash
# Quality tier (default)
teardrop llm-config set --provider anthropic --model claude-sonnet-4-6 --routing quality

# Cost tier
teardrop llm-config set --provider openrouter --model deepseek-chat --routing cost

# Speed tier
teardrop llm-config set --provider google --model gemini-3-flash --routing speed
```

Pipe a key from stdin to keep it out of shell history: `--byok-key -`. See [docs/cli-reference.md](docs/cli-reference.md#llm-configuration) for advanced tuning, BYOK details, and benchmarks.

---

## Browse the Marketplace

```bash
teardrop marketplace list
teardrop marketplace search "weather"
teardrop marketplace info acme/weather
teardrop marketplace subscribe acme/weather
teardrop marketplace subscriptions
```

Browsing requires no authentication. Subscribed tools become immediately available to your agents.

---

## Where to Go Next

- **[Full CLI reference](docs/cli-reference.md)** — every flag, env-var precedence, exit codes, M2M auth, MCP servers, models benchmarks, config file, development.
- **[End-to-end test guide](tests/e2e/README.md)** — running tests against a live API.
- **[teardrop.dev](https://teardrop.dev)** — platform docs and dashboard.

---

## License

MIT. See [LICENSE](LICENSE).
