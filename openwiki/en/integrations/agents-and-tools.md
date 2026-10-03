---
type: workflow
title: Plug the protection into an agent and its tools
description: What the model, the tools and the user see when PIIGhost protects a LangChain, Pydantic AI, LlamaIndex or Claude Code agent, which options change this sharing, and where each rule lives in the code.
tags: [integrations, langchain, pydantic-ai, llama-index, claude-code, client, tool-calls, thread-id]
sources:
  - id: openwiki-source-60f405cf9fd8c0cba8a61889
    resource: repo://src/piighost/integrations/_deidentify.py
  - id: openwiki-source-9703fc61b3e278e6ef8403ff
    resource: repo://src/piighost/integrations/claude_code/hooks.py
  - id: openwiki-source-c469f9c4e3d15d32abf9692f
    resource: repo://src/piighost/integrations/claude_code/runner.py
  - id: openwiki-source-a8fd2755cc1e33939a1b3ecb
    resource: repo://src/piighost/integrations/client/remote.py
  - id: openwiki-source-85881a85af445f438a8d7d5f
    resource: repo://src/piighost/integrations/langchain/middleware.py
  - id: openwiki-source-0893e40bf380b075c325a32c
    resource: repo://src/piighost/integrations/llama_index/query_engine.py
  - id: openwiki-source-b43ea3b38b4c09af8aeccb0d
    resource: repo://src/piighost/integrations/llama_index/transform.py
  - id: openwiki-source-d998a4e1822dbcfab4a92c61
    resource: repo://src/piighost/integrations/pydantic_ai/hooks.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Plug the protection into an agent and its tools

## In short

- Plugged into an agent, PIIGhost masks the messages before the model and puts the real values back into the reply.
- By default, the agent's tools (search, sending mail, reading a file) receive the real values, and what they return is masked before the model.
- A conversation without an identifier is refused, with LangChain as with Claude Code. Otherwise, all conversations would share their placeholders.
- With Claude Code, the displayed reply keeps the placeholders: no hook point allows rewriting it.
- The history kept by the agent contains the real values. Protect it as personal data.

The terms are defined in the [glossary](../glossary.md). The conversation mechanism is described in [Follow a conversation and restore the reply](../processes/follow-a-conversation.md).

## For the business

PIIGhost has no screen. The settings are made in the agent's code or in its configuration. This part describes what each actor sees and the choices to settle.

### Who sees what

| Actor | LangChain, Pydantic AI | LlamaIndex | Claude Code |
|---|---|---|---|
| The model | placeholders | placeholders (question and indexed documents) | placeholders (request and results of the listed tools) |
| The tools | the real values (default setting) | not applicable | the real values |
| The end user | the reply with the real values | the reply with the real values | the reply with placeholders |
| The indexing service | not applicable | placeholders | not applicable |

### Choose how tools are handled

Four settings decide what the tool receives and what the model reads. The choice is made for the whole agent. The table of settings, the worked example and the rules are in [Let a tool act on the real values](../processes/let-a-tool-act.md).

### Rules to know

**BR-AGT-01.** When a LangChain agent is called without a conversation identifier, then it stops on `No thread_id in the LangGraph config; pass config={'configurable': {'thread_id': ...}} on the agent call, or 'default' if your conversations need no separation.` Why: without an identifier, all conversations would become one and share their placeholders. An application that does not need to separate its conversations passes `default` itself.

**BR-AGT-02.** When the model writes a placeholder that PIIGhost never issued, then the reply is refused by default, with `Deanonymized text holds tokens the pipeline never issued`. Two other choices exist: keep the placeholder as is, or remove it from the text.

**BR-AGT-03.** When the assistant is the first to quote a value, then it stays in clear by default. Example: the assistant answers "The head office is in Lyon". "Lyon" comes from it, so it is not masked at the next turn. Two other choices: mask it like user data, or not analyze the assistant's messages at all.

**BR-AGT-04.** When the tool setting is "Full" or "Output only", then the text returned by the tool goes through full detection and is masked before the model. With LangChain, only the text of the tool message is masked. With Pydantic AI, a structured result (list, dictionary) is walked through entirely.

**BR-AGT-05.** When a Claude Code event has no session identifier, then it is refused with `The hook event carries no session_id, the thread its values belong to.` No shared conversation is used.

**BR-AGT-06.** When a Claude Code tool is not in the list of handled tools, then its result passes in clear. Handled tools: Bash, Read, Write, Edit, Agent, WebFetch, WebSearch, ToolSearch. Grep, in particular, is not among them.

**BR-AGT-07.** When the model's reply is streamed as it is produced, then the display shows placeholders until the end of the message, unless the application plugs in the provided stream decoder. See [Show a streamed reply](../processes/show-a-streamed-reply.md).

### What the end user sees

- With LangChain, Pydantic AI and LlamaIndex: a readable reply, with the real values.
- With Claude Code: a reply that contains placeholders like `<<PERSON:1>>`. The modified files and the commands run, however, hold the real values.

### Frequently asked questions

**The displayed reply contains `<<PERSON:1>>`.** Three possible causes. You use Claude Code, which does not restore the displayed reply. Or the application streams the reply without a stream decoder (BR-AGT-07). Or the restoration takes place in another thread than the protection: check that the same conversation identifier is passed to both.

**The agent stops with `No thread_id in the LangGraph config`.** The call does not pass a conversation identifier. Ask the development team to pass it on each call, or `default` if the conversations do not need to be separated (BR-AGT-01).

**The agent stops with `Deanonymized text holds tokens the pipeline never issued`.** The model wrote an unknown placeholder, often by copying a placeholder from another conversation or from a document. Keep the refusal if you prefer a visible error to a doubtful text (BR-AGT-02).

**A tool received `<<EMAIL:1>>` instead of the address.** The tool setting is "Output only" or "None". Switch it to "Full" if the tool must act on the real address. See [Let a tool act](../processes/let-a-tool-act.md).

**The result of a Grep search went out in clear in Claude Code.** Grep is not in the list of handled tools (BR-AGT-06). Remove Grep from the session, or have the tool added to the list.

## For developers

### Where the rules live

| Rule | Location |
|---|---|
| BR-AGT-01 | `src/piighost/integrations/langchain/middleware.py:47-66` (`_thread_id`) |
| BR-AGT-02 | `src/piighost/integrations/_deidentify.py:133-155`, default `RAISE` line 57 |
| BR-AGT-03 | `src/piighost/integrations/langchain/middleware.py:370` (`_message_role`), `pipeline/thread.py:322-329` |
| BR-AGT-04 | `middleware.py:220-272` (LangChain), `pydantic_ai/hooks.py:138-154` (Pydantic AI) |
| BR-AGT-05 | `src/piighost/integrations/claude_code/hooks.py:101-105` |
| BR-AGT-06 | `src/piighost/integrations/claude_code/hooks.py:22-38` |
| BR-AGT-07 | `middleware.py:206-218`, `_deidentify.py:83-107` |

Related components:

- `TextDeidentifier` (`integrations/_deidentify.py`): shared logic for masking, restoration and invented placeholders, used by LangChain, Pydantic AI and LlamaIndex. It refuses at construction a pipeline without a `recognizer` (`UnrecognizableFactoryError`).
- `PIIAnonymizationMiddleware`: `abefore_model`, `aafter_model`, `awrap_tool_call`.
- `pii_hooks(pipeline, thread_id, ...)`: Pydantic AI capability, `thread_id` fixed or a function of the `RunContext`.
- `PIINodeAnonymizer` and `PIIQueryEngine` (LlamaIndex): masking of the nodes before embedding, then masking of the question and restoration of the answer in the same corpus conversation.
- `handle_hook(event, pipeline)` and `run()` (Claude Code): `run` reads the event on stdin and calls `piighost-api` at `PIIGHOST_API_URL` (default `http://localhost:8000`).
- `PIIGhostClient`: implements `AnyThreadPipeline` over HTTP (`/v1/anonymize`, `/v1/deanonymize`, `/v1/detect`, `/v1/labels`, `/v1/threads/{id}/tokens`). It raises `RemoteError` on a non-2xx response.

### Plug in the LangChain middleware

1. Start from `examples/langchain_middleware.py`.
2. Build a `ThreadAnonymizationPipeline` whose factory is delimited (by default `LabelCounterPlaceholderFactory`).
3. Pass it to `PIIAnonymizationMiddleware(pipeline)`. Add `tool_strategy`, `invented_strategy` or `assistant_strategy` only to change a default.
4. Pass `config={"configurable": {"thread_id": "..."}}` on each call of the agent.
5. For a streamed display, wrap the `agent.astream(..., stream_mode="messages")` loop in `middleware.deanonymize_stream(source, thread_id)`.

#### Check

```bash
uv run pytest tests/integrations/langchain
```

In a trace of the agent, the message received by the model must contain `<<PERSON:1>>` and the argument received by the tool the real value.

### Pitfalls

- **The LangGraph state keeps the message content in clear.** `aafter_model` restores the content in the state, and the checkpointer saves it that way. Only the `tool_calls` stay as placeholders (`middleware.py:199-200`). The same goes for the Pydantic AI history after `after_model_request`.
- **LangChain masks again the arguments of the `tool_calls` in the history**, as a precaution, except under `IGNORE`. Pydantic AI does not.
- **The Claude Code hooks tolerate an unknown output shape**: they let it through. Set `PIIGHOST_HOOK_LOG` to see the real shapes. This log contains restored values in clear: keep it local and delete it afterwards.
- **If `piighost-api` cannot be reached, the hook fails closed** (`claude_code/runner.py:68-88`). A prompt or a tool call exits with code 2, which Claude Code reads as a block. A tool output, already produced, is replaced by a notice. `PIIGHOST_HOOK_FAIL_OPEN=1` lets the text through in clear (DPO-9).
- **`PIIQueryEngine` refuses a streaming engine** (`NotImplementedError`) and its synchronous paths go through `asyncio.run`: call `aquery` from asynchronous code.
- **`PIIGhostClient.anonymize` returns an empty placeholder dictionary.** The mapping lives on the server. Restore with `deanonymize`.

### Doc / code gaps

No gap found on this page. The Grep limitation is documented in `docs/en/examples/claude-code.md`.

### Tests

| Test | Covers |
|---|---|
| `tests/integrations/langchain/test_middleware.py` | Conversation identifier, block content, each tool strategy, `Command`, invented placeholders, assistant provenance, refusal of a non-delimited factory |
| `tests/integrations/langchain/test_middleware_stream.py` | Streamed restoration |
| `tests/integrations/test_pydantic_ai_hooks.py` | Pydantic AI capability |
| `tests/integrations/llama_index/` | Node transformation, query engine |
| `tests/integrations/test_claude_code_hooks.py` | The three events, list of fields, unknown tool let through |
| `tests/integrations/client/test_client.py` | HTTP client |

Not covered: the behavior of `run()` when `piighost-api` cannot be reached, and the persistence in clear of the LangGraph state.

See also [Configure a pipeline](../operations/configuration-and-hub.md).
