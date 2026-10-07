---
icon: lucide/terminal
seo_title: Mask PII in Claude Code with hooks
description: Plug piighost into Claude Code hooks. Tool outputs reach the model as placeholders, and real values are restored where tools need them. What the hooks miss, and the proxy that covers it.
---

# Claude Code hooks

You cannot point Claude Code at the OpenAI-compatible proxy, because it speaks Anthropic's Messages API, not the OpenAI shape. Instead, `piighost` plugs into Claude Code's own hook system. A hook is a small command that Claude Code runs at a fixed point in a turn. The hooks de-identify what the tools return to the model and restore the real values where the tools need them, without touching your agent code. The other route is the [Anthropic-compatible proxy](anthropic-proxy.md), plugged in through Claude Code's base URL.

Three hooks cover a turn:

- **`PostToolUse`** de-identifies a tool's output before the model reads it.
- **`PreToolUse`** restores the real values in a tool's input before the tool runs.
- **`UserPromptSubmit`** checks that `piighost-api` answers, and blocks your prompt when it does not. It cannot de-identify the prompt, because Claude Code lets no hook replace it.

When the Read tool returns a customer row, the model receives `<<PERSON:1>>`{ .placeholder } instead of `Margaret Holloway`{ .pii }. When the model then writes `<<PERSON:1>>`{ .placeholder } into a file, the Write tool receives `Margaret Holloway`{ .pii }. The Claude Code `session_id` is used as the de-identification thread, so a value keeps the same token for the whole session.

!!! warning "What the hooks leave in clear"

    The model receives these in clear, because no hook can rewrite them:

    - Your prompt. If it names `Margaret Holloway`{ .pii }, the model reads `Margaret Holloway`{ .pii }.
    - A file you mention with `@`, such as `@.env`. Claude Code adds its content without any tool call, so no hook sees it.
    - The output of a tool missing from the field list below, such as an MCP tool.

    To de-identify everything Claude Code sends to Anthropic, use the [Anthropic-compatible proxy](anthropic-proxy.md) instead. It de-identifies the messages of each request, so your prompt, the `@` files and every tool output reach Anthropic as placeholders.

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

## Keep `.env` away from the model

The model rarely needs the value of a key to write code. Deny it in the same `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": ["Read(./.env)", "Read(./.env.*)"]
  }
}
```

These rules block the Read tool and the Bash commands that name the file, such as `cat .env`. Claude Code also applies them to Grep, Glob and `@` mentions, on a best-effort basis, see its [permissions page](https://code.claude.com/docs/en/permissions). They do not stop `grep -r` or a script that opens the file itself. For those, Claude Code offers a [sandbox](https://code.claude.com/docs/en/sandboxing).

## Point it at your server

The hook talks to `piighost-api` at `http://localhost:8000` by default. Override it with an environment variable:

```bash
export PIIGHOST_API_URL="https://piighost.internal:8000"
```

When the hook cannot de-identify, because the server is down or the event has no session id, it blocks by default, and Claude Code shows the reason:

- A prompt is blocked.
- A tool call is blocked before the tool runs.
- A tool output already exists. The hook replaces each of its text fields from the list below with a notice, and keeps the rest of the output. Claude Code ignores a replacement that does not match the tool's output shape, so the shape has to stay.

With the server down, the model then reads `[piighost could not de-identify this PostToolUse event (ConnectError: All connection attempts failed), so the tool output is withheld.]` in place of the file content. A tool missing from the list gets no notice, see the warning below.

To let the text through in clear rather than block, for a session where availability matters more than protection, set:

```bash
export PIIGHOST_HOOK_FAIL_OPEN=1
```

To watch what the hook does, set `PIIGHOST_HOOK_LOG` to a file path. The runner appends one JSON record per event (the event, the tool, the session id, and the mutation it returned):

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

## Which fields get de-identified

A prompt and a tool input are plain enough to de-identify wholesale. A tool's output, though, is a structured object where only some fields hold model-facing text. The `PostToolUse` hook therefore does not de-identify the whole payload, so it never mangles a path, an exit code, or a line number. It de-identifies only the text fields listed for each tool:

| Tool | De-identified fields |
|------|-------------------|
| `Bash` | `stdout`, `stderr` |
| `Read` | `file.content` |
| `Write` | `content`, `originalFile`, patch lines |
| `Edit` | `oldString`, `newString`, `originalFile`, patch lines |
| `Agent` | message text |
| `Grep` | `content`, the matching lines |
| `WebFetch` | `result` |
| `WebSearch` | result titles |
| `ToolSearch` | `query` |

!!! warning "The field list fails open"

    A tool that is not in the list, or an output whose shape is unexpected, passes through untouched, whether the server is up or down. Its text therefore reaches the model in clear. MCP tools are in this case. Either extend the list as described below, deny the tool in your permissions, or use the [Anthropic-compatible proxy](anthropic-proxy.md).

## Discover a new tool's shape

To extend the field list to a tool it does not yet cover, set `PIIGHOST_HOOK_LOG` as above before starting Claude Code. The log holds each hook call. A tool output the hook passed through is logged whole, so you can see the real field names.

Exercise the tool, read the log to find which fields carry the text, and add the tool to the field list in the integration. The log holds clear text. Delete it afterwards.

## Use it programmatically

The public API is two functions. `handle_hook(event, pipeline)` is a pure dispatch. It takes a parsed event and any thread pipeline (a local `ThreadAnonymizationPipeline` or a remote `PIIGhostClient`). It returns the mutation envelope, or `None` to pass through. `run()` is the stdin/stdout entrypoint the module invokes. Drive `handle_hook` directly to test the behaviour or to embed it in your own runner.
