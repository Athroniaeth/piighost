# Claude Code hooks integration (spike)

De-identify a Claude Code session with piighost through Claude Code's hooks,
without touching the API transport. Because hooks run locally, this works on a
subscription (OAuth), where the `ANTHROPIC_BASE_URL` proxy does not.

## How it works

Each hook runs `python -m piighost.integrations.claude_code`, which reads the
hook event on stdin and calls piighost-api (via `PIIGhostClient`) with the Claude
Code `session_id` as the anonymization thread.

| Hook | Direction | Field mutated |
|------|-----------|---------------|
| `UserPromptSubmit` | anonymize the prompt before the model reads it | `updatedPrompt` |
| `PostToolUse` | anonymize a tool's output before the model reads it | `updatedToolOutput` |
| `PreToolUse` | restore real values in a tool input before it runs | `updatedInput` |

The model never sees real PII, and tool actions (edits, commands) run on real
values. Anonymization state lives server-side, keyed by the session id.

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
| `WebFetch` | `result` |
| `WebSearch` | `results[].content[].title` |
| `ToolSearch` | `query` |

A plain-string `tool_response` is anonymized whole. A tool not in the allowlist is
passed through untouched, so its metadata is never mangled; run the capture logger
(`python -m piighost.integrations.claude_code.capture`, writing to
`PIIGHOST_HOOK_LOG`) to observe a new tool's shape and add its text fields.

## Known limitations

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

3. Merge `settings.template.json` into your Claude Code `.claude/settings.json`,
   then start `claude`. The three hooks fire automatically.
