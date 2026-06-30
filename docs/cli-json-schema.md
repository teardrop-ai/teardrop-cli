# Teardrop CLI Agent Run JSON Schema

When running `teardrop run "..." --json` or `teardrop chat "..." --json`,
the output is a single JSON object (implies `--no-stream`).

## Schema Details

The JSON object contains the following fields:

- `text` (string): The final text response from the agent.
- `thread_id` (string | null): The ID of the thread used for the run. This can be used with the `--thread` flag in future runs (or `teardrop chat`) to continue the conversation.

## Example Output

```json
{
  "text": "The price of ETH is currently $2,450.32.",
  "thread_id": "thr_abc123"
}
```

## Usage
To capture specific fields, use `jq`:
```bash
teardrop run "ETH price" --json | jq -r .text
teardrop chat "ETH price" --json | jq -r .thread_id
```

---

## Schedules (`schedules create/get/list/update --json`)

`schedules list --json` returns a JSON array; all other commands return a single object.

| Field | Type | Description |
|---|---|---|
| `id` | string (UUID) | Schedule identifier |
| `org_id` | string | Owning org |
| `user_id` | string | Creator user |
| `name` | string | Display name |
| `prompt` | string | Agent prompt |
| `schedule_kind` | `"interval"` | Fixed constant |
| `interval_seconds` | integer | Run frequency |
| `enabled` | boolean | Active state |
| `callback_url` | string \| null | Webhook called after each run |
| `next_run_at` | string (ISO 8601) | Next scheduled time |
| `last_run_at` | string \| null (ISO 8601) | Last completed run |
| `consecutive_failures` | integer | Failures since last success |
| `created_at` | string (ISO 8601) | |
| `updated_at` | string (ISO 8601) | |

```bash
teardrop schedules create --name my-schedule --prompt "..." --interval-seconds 3600 --json | jq -r .id
teardrop schedules update <id> --enabled false --json | jq .enabled
teardrop schedules list --json | jq '.[].name'
```

---

## Event Triggers (`event-triggers create/get/list/update --json`)

`event-triggers list --json` returns a JSON array; all other commands return a single object.

| Field | Type | Description |
|---|---|---|
| `id` | string (UUID) | Trigger identifier |
| `org_id` | string | Owning org |
| `user_id` | string | Creator user |
| `name` | string | Display name |
| `prompt` | string | Prompt template (supports `{{field}}` / `{{event_json}}`) |
| `schedule_kind` | `"event"` | Fixed constant |
| `enabled` | boolean | Active state |
| `callback_url` | string \| null | Webhook called after each run |
| `trigger_token` | string | Public route discriminator |
| `event_path` | string | Inbound dispatch path (e.g. `/agent/events/{trigger_token}`) |
| `consecutive_failures` | integer | Failures since last success |
| `last_run_at` | string \| null (ISO 8601) | |
| `created_at` | string (ISO 8601) | |
| `updated_at` | string (ISO 8601) | |

**`event-triggers create --json` only** additionally includes:

| Field | Type | Description |
|---|---|---|
| `secret` | string | Plaintext signing secret — shown once, never retrievable again |

**`event-triggers rotate-secret --json`** returns the rotation model (not the full trigger object):

| Field | Type | Description |
|---|---|---|
| `id` | string (UUID) | Trigger identifier |
| `secret` | string | New plaintext signing secret — shown once |

```bash
# Capture id and secret on creation for use in CI
eval $(teardrop event-triggers create --name ci-hook --prompt "..." --json \
  | jq -r '"TRIGGER_ID=" + .id, "TRIGGER_SECRET=" + .secret')

teardrop event-triggers list --json | jq '.[].trigger_token'
teardrop event-triggers rotate-secret <id> --json | jq -r .secret
```

---

## Run History (`schedules runs / event-triggers runs --json`)

Both commands return the same paginated envelope:

```json
{ "items": [ <ScheduledRunResult>, ... ], "next_cursor": "<cursor> | null" }
```

Each `ScheduledRunResult` item:

| Field | Type | Description |
|---|---|---|
| `id` | string (UUID) | Outcome record ID |
| `schedule_id` | string (UUID) | Owning schedule or trigger ID |
| `org_id` | string | |
| `run_id` | string (UUID) | Core execution thread ID |
| `status` | `"completed" \| "failed" \| "timeout" \| "skipped"` | |
| `output_text` | string | Synthesized agent output |
| `cost_usdc` | integer | Atomic USDC charged ($1.00 = `1000000`) |
| `error` | string | Sanitized reason on failure; empty on success |
| `created_at` | string (ISO 8601) | |

```bash
teardrop schedules runs <id> --json | jq '.items[] | select(.status == "failed") | .error'
teardrop event-triggers runs <id> --limit 50 --json | jq '.next_cursor'
```
