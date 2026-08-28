---
icon: lucide/terminal
---

# De-identify Claude Code with hooks

Claude Code speaks Anthropic's Messages API, not the OpenAI shape, so you cannot point it at the OpenAI-compatible proxy. Instead, `piighost` plugs into Claude Code's own hook system: small commands the harness runs at fixed points in a turn. The hooks de-identify what the model sees and restore the real values where they are actually needed, without touching your agent code.

Three hooks cover a turn:

- **`UserPromptSubmit`** anonymizes your prompt before the model reads it.
- **`PostToolUse`** anonymizes a tool's output before the model reads it.
- **`PreToolUse`** restores the real values in a tool's input before the tool runs.

So the model only ever sees placeholders like `<<PERSON:1>>`, while the tools that actually run (Bash, Read, Edit, ...) receive the real values. The Claude Code `session_id` is used as the de-identification thread, so a value keeps the same token for the whole session.

!!! note "Prerequisites"
    `piighost` installed with the client extra, `pip install piighost[client]`, and a running [`piighost-api`](https://github.com/Athroniaeth/piighost-api) server. The hook is a thin client: it forwards each event to the API, which owns the pipeline and the conversation memory.

## Wire the hooks

Each hook invocation runs `python -m piighost.integrations.claude_code`. It reads one hook event as JSON on stdin and writes the mutation back as JSON on stdout. Merge this into your `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python -m piighost.integrations.claude_code"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m piighost.integrations.claude_code"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m piighost.integrations.claude_code"
          }
        ]
      }
    ]
  }
}
```

The same snippet ships as `settings.template.json` inside the integration package. Run `claude` as usual; the hooks fire automatically.

## Point it at your server

The hook talks to `piighost-api` at `http://localhost:8000` by default. Override it with an environment variable:

```bash
export PIIGHOST_API_URL="https://piighost.internal:8000"
```

To watch what the hook does, set `PIIGHOST_HOOK_LOG` to a file path; the runner appends one JSON record per event (the event, the tool, the session id, and the mutation it returned):

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

## Which fields get anonymized

A prompt and a tool input are plain enough to de-identify wholesale, but a tool's output is a structured object where only some fields hold model-facing text. The `PostToolUse` hook therefore anonymizes a per-tool allowlist of text fields rather than the whole payload, so it never mangles a path, an exit code, or a line number:

| Tool | Anonymized fields |
|------|-------------------|
| `Bash` | `stdout`, `stderr` |
| `Read` | `file.content` |
| `Write` | `content`, `originalFile`, patch lines |
| `Edit` | `oldString`, `newString`, `originalFile`, patch lines |
| `Agent` | message text |
| `WebFetch` | `result` |
| `WebSearch` | result titles |

A tool that is not in the list, or an output whose shape is unexpected, passes through untouched.

## Discover a new tool's shape

To extend the allowlist to a tool it does not yet cover, run the capture module in place of the runner. It logs each event to a JSONL file and mutates nothing, so you can see the real field names:

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-capture.jsonl"
# In settings.json, swap the command for:
#   python -m piighost.integrations.claude_code.capture
```

Exercise the tool, read the log to find which fields carry the text, and add the tool to the allowlist in the integration.

## Use it programmatically

The public API is two functions. `handle_hook(event, pipeline)` is a pure dispatch that takes a parsed event and any thread pipeline (a local `ThreadAnonymizationPipeline` or a remote `PIIGhostClient`) and returns the mutation envelope, or `None` to pass through. `run()` is the stdin/stdout entrypoint the module invokes. Drive `handle_hook` directly to test the behaviour or to embed it in your own runner.
