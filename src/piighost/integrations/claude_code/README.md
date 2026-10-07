# Claude Code hooks integration (spike)

De-identify what Claude Code's tools return to the model with piighost, through
Claude Code's hooks, without touching the API transport. The hooks run locally,
next to Claude Code.

The hooks do not cover everything the model receives. To de-identify every
request sent to Anthropic (prompt, `@` files and every tool output included),
point `ANTHROPIC_BASE_URL` at the piighost-api Anthropic-compatible proxy
(`/anthropic`, see `docs/en/examples/anthropic-proxy.md`).

## How it works

Each hook runs `python -m piighost.integrations.claude_code`, which reads the
hook event on stdin and calls piighost-api (via `PIIGhostClient`) with the Claude
Code `session_id` as the anonymization thread.

| Hook | Direction | Field mutated |
|------|-----------|---------------|
| `PostToolUse` | anonymize a listed tool's output before the model reads it | `updatedToolOutput` |
| `PreToolUse` | restore real values in a tool input before it runs | `updatedInput` |
| `UserPromptSubmit` | record the prompt's values in the thread, block the prompt if the server is unreachable | none |

The model reads placeholders where a listed tool returned real values, and tool
actions (edits, commands) run on real values. Anonymization state lives
server-side, keyed by the session id.

`UserPromptSubmit` emits no mutation because Claude Code lets no hook replace the
prompt (hooks reference: it "can't replace the prompt; it only injects
`additionalContext`"). An earlier version emitted `updatedPrompt`, which Claude
Code ignored silently. The hook still calls the server, so a server that cannot be
reached blocks the prompt (exit code 2) rather than letting the session run
without protection.

## Tool outputs: a targeted field allowlist

A `tool_response` is often structured, and only some of its fields carry
model-facing text; the rest is metadata the tool and model need verbatim (file
paths, urls, base64 image data, git shas, ids, line numbers, counts, flags).
Anonymizing the whole thing would corrupt that metadata, so `hooks.py` keeps a
per-tool allowlist of the dotted field paths that hold free text
(`_TOOL_OUTPUT_TEXT_FIELDS`), derived from observed Claude Code results:

| Tool | Anonymized fields |
|------|-------------------|
| `Bash` | `stdout`, `stderr` |
| `Read` | `file.content` |
| `Write` | `content`, `originalFile`, `structuredPatch[].lines[]` |
| `Edit` | `oldString`, `newString`, `originalFile`, `structuredPatch[].lines[]` |
| `Agent` | `content[].text` |
| `Grep` | `content` (matching lines in content mode, `filenames` holds paths and is left alone) |
| `WebFetch` | `result` |
| `WebSearch` | `results[].content[].title` |
| `ToolSearch` | `query` |

A plain-string `tool_response` is anonymized whole. A tool not in the allowlist is
passed through untouched, so its metadata is never mangled. Its text reaches the
model in clear, server up or down, since the hook never calls the server for it.
MCP tools are in this case. Set `PIIGHOST_HOOK_LOG`
to log each hook call: a passed-through tool output is logged whole, so a new
tool's shape can be read and its text fields added.

## Known limitations

What reaches the model in clear, because no hook can rewrite it:

- The user prompt. `UserPromptSubmit` cannot replace it.
- Files mentioned with `@` in the prompt. Claude Code inlines them without any
  tool call, so no `PreToolUse` or `PostToolUse` hook fires.
- The output of a tool missing from the allowlist, MCP tools included.

The Anthropic-compatible proxy covers all three. For secrets, also deny `.env`
in Claude Code's permissions (`"deny": ["Read(./.env)", "Read(./.env.*)"]`).

No Claude Code hook can rewrite the assistant's displayed reply, so Claude's chat
text still shows tokens such as `<<PERSON:1>>`. Tool actions and written files are
restored; only the prose you read is not.

Anonymization runs one call per text leaf, so a large structured output (a long
diff, say) makes several calls to piighost-api. Fine for a spike, worth batching
later.

## Setup

1. Install piighost with the client extra and run piighost-api:

       pip install "piighost[client]"
       # start piighost-api on http://localhost:8000

2. Point the runner at the server if it is not the default:

       export PIIGHOST_API_URL=http://localhost:8000

   If the server cannot be reached, the hooks fail closed: a prompt or a tool
   call is blocked, and each allowlisted text field of a tool output is replaced
   by a notice. The rest of the output keeps its shape, because Claude Code
   ignores an `updatedToolOutput` that does not match a built-in tool's output
   schema and sends the original instead. A tool outside the allowlist gets no
   notice, see above. Set `PIIGHOST_HOOK_FAIL_OPEN=1` to let the text through in
   clear instead.

3. Merge `settings.template.json` into your Claude Code `.claude/settings.json`,
   then start `claude`. The three hooks fire automatically.
