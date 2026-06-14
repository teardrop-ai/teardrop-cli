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
