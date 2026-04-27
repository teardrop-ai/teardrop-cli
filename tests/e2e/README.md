# E2E Tests

Live integration tests that exercise the CLI against the real Teardrop API. All tests are skipped automatically in the default `pytest` run — they require explicit opt-in.

---

## Running E2E Tests

```bash
# Minimum: token auth (standard env var)
TEARDROP_E2E=1 \
TEARDROP_API_KEY=<jwt> \
pytest -m e2e

# Email + secret auth
TEARDROP_E2E=1 \
TEARDROP_EMAIL=you@example.com \
TEARDROP_SECRET=yourpassword \
pytest -m e2e

# Against a non-production environment
TEARDROP_E2E=1 \
TEARDROP_E2E_BASE_URL=https://staging.api.teardrop.ai \
TEARDROP_API_KEY=<staging-jwt> \
pytest -m e2e
```

---

## Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TEARDROP_E2E` | ✓ | — | Set to `1` to enable live tests |
| `TEARDROP_API_KEY` | one of these | — | Pre-issued JWT (standard env var; priority 1) |
| `TEARDROP_EMAIL` | one of these | — | Email for email+secret login |
| `TEARDROP_SECRET` | one of these | — | Password / secret |
| `TEARDROP_E2E_BASE_URL` | | `https://api.teardrop.ai` | Override API base URL |
| `TEARDROP_E2E_TEST_TOOL` | | — | `org/tool` name for marketplace lifecycle test |
| `TEARDROP_E2E_WALLET_PRIVATE_KEY` | | — | Ethereum private key for live SIWE test |
| `TEARDROP_E2E_STRIPE` | | — | Set to `1` to run the Stripe session creation test (opt-in; see *Side Effects* below) |

---

## Test Files

| File | What it proves |
|---|---|
| `test_auth_e2e.py` | Login/status/logout round-trip; token refresh; credential priority |
| `test_run_e2e.py` | Real agent execution returns text; `--thread` forwarded; auth error exits 1 |
| `test_billing_e2e.py` | `balance --json` numeric; usage schema; Stripe session created (opt-in via `TEARDROP_E2E_STRIPE=1`) |
| `test_marketplace_e2e.py` | Catalog listing; search filtering; subscribe/unsubscribe lifecycle |
| `test_siwe_login_e2e.py` | SIWE wallet signs nonce, receives JWT, status succeeds |

---

## Expected Run Times

| Scope | Expected duration |
|---|---|
| Auth round-trip | ~3–5 s |
| Agent run | ~5–15 s (depends on model) |
| Balance / usage | ~1–2 s each |
| Stripe session creation | ~2–3 s |
| Marketplace list + subscribe | ~3–5 s |
| SIWE login | ~3–5 s |
| Full `pytest -m e2e` | ~60–90 s |

---

## Side Effects

E2E tests run against the production API. Most tests are read-only, but a few write data:

| Test | Side effect | Self-healing? |
|---|---|---|
| `test_run_*.py` | Creates conversation thread(s) in the database | No — the SDK has no `delete_thread` method. Each run uses a unique `e2e-test-<uuid>` thread ID so threads are isolated but not removed. |
| `test_stripe_session_url_printed` | Creates an abandoned Stripe checkout session | Partial — Stripe auto-expires sessions after ~24 h. Cannot be cancelled via API. Skipped by default; opt-in with `TEARDROP_E2E_STRIPE=1`. |
| `test_subscribe_then_unsubscribe` | Subscribes then unsubscribes from a tool | Yes — unsubscribe cleanup runs even on assertion failure (teardown order guaranteed). |
| All auth tests | Writes credentials to an isolated `tmp_path` config dir | Yes — temp dir is cleaned up by pytest after the test. |

---

## Skip Behaviour

Tests skip cleanly (not fail) in these cases:

- `TEARDROP_E2E` not set → entire test package skipped
- No credentials supplied → `live_creds` / `blank_runner` fixtures skip
- `TEARDROP_E2E_TEST_TOOL` not set → marketplace lifecycle test skipped
- `TEARDROP_E2E_WALLET_PRIVATE_KEY` not set → SIWE live test skipped
- `TEARDROP_E2E_STRIPE` not set → Stripe session creation test skipped
- Token-only creds for `test_token_refresh` → test skipped (requires email+secret)
