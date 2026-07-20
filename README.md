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

The wizard walks you through sign-in, optional BYOK LLM setup, and your first agent run or scaffolded tool:

```bash
teardrop quickstart
```

Quickstart keeps local tool scaffolding and public marketplace browsing available
without sign-in. A saved session is verified when you choose an agent run; if it
is stale, the wizard offers sign-in again before asking for a prompt or payment
confirmation. Environment credentials must be updated or unset when they are
rejected because they take precedence over interactive login.

Prefer the manual path? Pick a sign-in method:

```bash
# Email + password
teardrop auth signup --email you@example.com --org-name acme

# Wallet-first (no email needed) — generates a wallet on first run if you don't have one
teardrop auth login --siwe --generate-wallet

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
| Generate a new wallet & sign in | `teardrop auth login --siwe --generate-wallet [--save-key]` |
| Sign in with wallet (existing key) | `teardrop auth login --siwe --key-file wallet.key [--save-key]` |
| Email + password | `teardrop auth login --email you@example.com` |
| Pre-issued JWT | `teardrop auth login --token <jwt>` |
| Invite a team member | `teardrop auth invite colleague@example.com` |
| Show identity | `teardrop auth status` |
| Sign out | `teardrop auth logout` |

Private keys are never persisted by the CLI unless you pass ``--save-key``.
When saved, the key is stored in your OS keyring (never in a config file)
and can be used for automatic re-authentication when the session token
expires.  An encrypted keyring backend is required — plaintext fallbacks
are refused.

For machine-to-machine credentials, env-var precedence, and CI patterns, see [docs/cli-reference.md](docs/cli-reference.md#authentication).

---

## Publish a Tool

Scaffold a starter spec, edit it, and publish:

```bash
teardrop tools init my_scraper       # writes ./tool.json
$EDITOR tool.json                    # set webhook_url, schema, price
teardrop tools probe --from-file tool.json  # test webhook health before publishing
teardrop tools publish --from-file tool.json \
    --settlement-wallet 0xYourChecksumAddress
```

Or run the interactive wizard:

```bash
teardrop tools publish
```

Tool name rules: `^[a-z][a-z0-9_]*$`, ≤ 64 chars. Prices are in atomic USDC (6 decimals): `5000` = **$0.005** per call. Settlement wallet is required once before your first payout.

Test a local webhook before publishing with `teardrop tools probe --from-file tool.json`; the spec's method and auth settings are used by default. After publishing, use `teardrop tools probe <tool-name>`. Pass `--auth-header-name` and `--auth-header-value` to override auth settings, or use `--method` and `--payload` to customize the probe request.

Manage existing tools: `teardrop tools list | info | update | pause | delete | probe`. Full reference: [docs/cli-reference.md](docs/cli-reference.md#tool-management).

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

# Exclude specific tools
teardrop run "Summarize news" --exclude platform/web_search

# Estimate cost based on current pricing & config (no run performed)
teardrop run "Analyze this data" --estimate-cost

# Apply a tool policy from a file
teardrop run "Execute workflow" --policy-file policy.json

# Machine-readable output
teardrop run "..." --json --no-stream

# Include UI component data for dashboard export (adds ~60s overhead)
teardrop run "..." --json --with-ui
```

Streaming output renders Markdown live with inline tool calls and structured UI components. A token + cost summary prints at the end. By default, CLI output is optimized for scripting and automation (`emit_ui=false`); use `--with-ui` only if you need structured UI component data in the JSON output.

---

## Automate Runs

Use interval schedules for recurring prompts and event triggers for inbound webhooks:

```bash
teardrop schedules create \
    --name hourly-briefing \
    --prompt "Summarize open incidents" \
    --interval-seconds 3600

teardrop schedules list
teardrop schedules runs <schedule-id>

teardrop event-triggers create \
    --name inbound-orders \
    --prompt "Validate and process this order payload"

teardrop event-triggers runs <trigger-id>
teardrop event-triggers rotate-secret <trigger-id>
```

`event-triggers create` and `event-triggers rotate-secret` print the signing secret once. Store it immediately.

Full reference: [docs/cli-reference.md](docs/cli-reference.md#schedules) and [docs/cli-reference.md](docs/cli-reference.md#event-triggers).

---

## Chat with an Agent

A stateful chat mode that automatically continues the same thread across invocations:

```bash
teardrop chat "What is the current ETH gas price?"   # auto-creates a thread
teardrop chat "Follow up on that"                     # continues the same thread
teardrop chat "Start fresh" --new                     # starts a new conversation
teardrop chat "Specific thread" --thread thr_abc123   # explicit thread by id
teardrop chat "..." --json                            # machine-readable output
```

The active thread id is stored in `~/.teardrop/config.toml` and reused on your next `teardrop chat` call. The thread id is printed after every turn for copy/paste. All run flags (`--context`, `--exclude`, `--policy-file`, `--estimate-cost`, `--with-ui`, `--no-stream`) are supported.

Use `teardrop run` for one-shot, script-friendly calls — use `teardrop chat` for conversational interaction.

---

If a run fails on credit, check your balance and history:

```bash
teardrop balance             # current credits
teardrop balance credit-history   # past charges and top-ups
```

To add credits, visit [teardrop.dev](https://teardrop.dev).

---

## Agent Tools

List all tools visible to your agent (platform, marketplace subscriptions, and your own tools):

```bash
teardrop agent-tools list
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

### LLM credit model

Non-BYOK organizations use Teardrop's shared provider keys. Platform credits or x402 cover the model token costs and Teardrop platform fee. BYOK organizations pay their model provider directly through their own encrypted key, but still need platform credits or x402 for the Teardrop orchestration fee. BYOK uses the configured model and does not use pooled smart routing.

New email-authenticated organizations may receive optional promotional credit after verifying their email when the program is enabled. Eligibility and availability are server-configured; SIWE users and marketplace author tools are excluded. A real top-up removes promotional restrictions.

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
