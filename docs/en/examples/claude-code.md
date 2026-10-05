---
icon: lucide/terminal
---

# Claude Code hooks

You cannot point Claude Code at the OpenAI-compatible proxy, because it speaks Anthropic's Messages API, not the OpenAI shape. Instead, `piighost` plugs into Claude Code's own hook system. A hook is a small command that Claude Code runs at a fixed point in a turn. The hooks de-identify what the model sees and restore the real values where they are actually needed, without touching your agent code. The other route is the [Anthropic-compatible proxy](anthropic-proxy.md), plugged in through Claude Code's base URL.

Three hooks cover a turn:

- **`UserPromptSubmit`** de-identifies your prompt before the model reads it.
- **`PostToolUse`** de-identifies a tool's output before the model reads it.
- **`PreToolUse`** restores the real values in a tool's input before the tool runs.

So the model only ever sees placeholders like `<<PERSON:1>>`, while the tools that actually run (Bash, Read, Edit, ...) receive the real values. The Claude Code `session_id` is used as the de-identification thread, so a value keeps the same token for the whole session.

!!! note "Prerequisites"
    `piighost` installed with the client extra, `pip install "piighost[client]"`, and a running `piighost-api` server, see [API server](../getting-started/api-server.md). The hook is a thin client. It forwards each event to the API, which owns the pipeline and the conversation memory. The hook sends no API key. So start the server with `PIIGHOST_ALLOW_ANONYMOUS=true`, and keep it on a host only you can reach.

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

The same snippet ships as `settings.template.json` inside the integration package. Run `claude` as usual. The hooks fire automatically.

## Point it at your server

The hook talks to `piighost-api` at `http://localhost:8000` by default. Override it with an environment variable:

```bash
export PIIGHOST_API_URL="https://piighost.internal:8000"
```

When the hook cannot de-identify, because the server is down or the event has no session id, it blocks by default. A prompt or a tool call is blocked, and Claude Code shows the reason. A tool output has already been produced, so the hook replaces it with a notice instead. To let the text through in clear rather than block, for a session where availability matters more than protection, set:

```bash
export PIIGHOST_HOOK_FAIL_OPEN=1
```

To watch what the hook does, set `PIIGHOST_HOOK_LOG` to a file path. The runner appends one JSON record per event (the event, the tool, the session id, and the mutation it returned):

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

## Which fields get de-identified

A prompt and a tool input are plain enough to de-identify wholesale. A tool's output, though, is a structured object where only some fields hold model-facing text. The `PostToolUse` hook therefore does not de-identify the whole payload, so it never mangles a path, an exit code, or a line number. It de-identifies a per-tool allowlist of text fields:

| Tool | De-identified fields |
|------|-------------------|
| `Bash` | `stdout`, `stderr` |
| `Read` | `file.content` |
| `Write` | `content`, `originalFile`, patch lines |
| `Edit` | `oldString`, `newString`, `originalFile`, patch lines |
| `Agent` | message text |
| `WebFetch` | `result` |
| `WebSearch` | result titles |
| `ToolSearch` | `query` |

!!! warning "The allowlist fails open"

    A tool that is not in the list, or an output whose shape is unexpected, passes through untouched. Its text therefore reaches the model in clear. The notable gap is `Grep`, which the list does not cover yet. Its matches are lines of the files it searched. Until it does, either keep `Grep` out of the session or extend the list as described below.

## Discover a new tool's shape

To extend the allowlist to a tool it does not yet cover, set `PIIGHOST_HOOK_LOG` as above before starting Claude Code. The log holds each hook call. A tool output the hook passed through is logged whole, so you can see the real field names.

Exercise the tool, read the log to find which fields carry the text, and add the tool to the allowlist in the integration. The log holds clear text. Delete it afterwards.

## Use it programmatically

The public API is two functions. `handle_hook(event, pipeline)` is a pure dispatch. It takes a parsed event and any thread pipeline (a local `ThreadAnonymizationPipeline` or a remote `PIIGhostClient`). It returns the mutation envelope, or `None` to pass through. `run()` is the stdin/stdout entrypoint the module invokes. Drive `handle_hook` directly to test the behaviour or to embed it in your own runner.
