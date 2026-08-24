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

## Known limitation

No Claude Code hook can rewrite the assistant's displayed reply, so Claude's chat
text still shows tokens such as `<<PERSON:1>>`. Tool actions and written files
are restored; only the prose you read is not.

Structured tool outputs (a `tool_response` that is not a plain string) are passed
through untouched for now; only string outputs are anonymized.

## Setup

1. Install piighost with the client extra and run piighost-api:

       pip install "piighost[client]"
       # start piighost-api on http://localhost:8000

2. Point the runner at the server if it is not the default:

       export PIIGHOST_API_URL=http://localhost:8000

3. Merge `settings.template.json` into your Claude Code `.claude/settings.json`,
   then start `claude`. The three hooks fire automatically.
