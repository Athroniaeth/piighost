---
icon: lucide/wrench
---

# Change piighost's code

This page is for whoever changes the code of `piighost`. For each common change, it points first to the page of the domain documentation that describes the rules involved, then to the files and tests to open. Read the rule before touching the code that applies it.

## Start locally

- **Stack**: Python 3.11 or later, `uv` package manager. The core depends only on `typing-extensions`. Everything else is an extra of `pyproject.toml` (`langchain`, `redis`, `gliner2`, `config`…), and `all` gathers them.
- **Install**: `uv sync` at the root of the repository.
- **Test**: `uv run pytest`, then `make lint` before any merge. Details in [Run and write tests](../../../openwiki/en/tests/run-and-write-tests.md).
- **Try**: `uv run piighost anonymize "Write to claire.dubois@example.com"`. The first run downloads the catalog group `catalog:piighost/generic`.
- **Services**: none for the tests. Redis, an SQL database or `piighost-api` are used only in operation. See [Store conversations](../../../openwiki/en/operations/storage-and-encryption.md) and [Configure a pipeline](../../../openwiki/en/operations/configuration-and-catalog.md).
- **Examples**: standalone scripts in `examples/`, run with `uv run examples/<script>.py`.

## Find where to change

| Type of change | Read first | Then |
|---|---|---|
| Add a detector | [Add or replace a component](../../../openwiki/en/architecture/ports-and-extension.md#add-a-detector) | `components/detector/regex.py` or `components/detector/ner/spacy.py`, `config/models/detector_model.py`, `tests/components/detector/test_contract.py` |
| Change how overlaps are arbitrated | [Protect a message](../../../openwiki/en/processes/protect-a-message.md) | `components/overlap_resolver/`, `tests/components/overlap_resolver/` |
| Change the form of the placeholders | [Glossary](../../../openwiki/en/glossary.md), [Add or replace a component](../../../openwiki/en/architecture/ports-and-extension.md#typed-placeholders) | `components/placeholder/`, `tags.py`, `tests/components/placeholder/` |
| Touch the conversation or the human correction | [Follow a conversation](../../../openwiki/en/processes/follow-a-conversation.md) | `pipeline/thread.py`, `tests/pipeline/test_thread.py`, `test_thread_hitl.py` |
| Change the deny list or the allow list | [Impose a deny list and an allow list](../../../openwiki/en/processes/impose-a-deny-list-and-an-allow-list.md) | `components/override/`, `tests/components/override/test_override.py` |
| Change how tool calls are handled | [Let a tool act](../../../openwiki/en/processes/let-a-tool-act.md) | `integrations/langchain/middleware.py` (`awrap_tool_call`), `integrations/pydantic_ai/hooks.py`, `tests/integrations/langchain/test_middleware.py` |
| Change the stream restoration | [Show a streamed reply](../../../openwiki/en/processes/show-a-streamed-reply.md) | `components/placeholder/streaming.py`, `tests/components/placeholder/test_streaming*.py` |
| Add an acceptance test | [Acceptance tests](../../../openwiki/en/tests/acceptance-tests.md) | `tests/acceptance/`, an `AT-<need>-<n>` identifier in the docstring |
| Add a configuration key | [Configure a pipeline](../../../openwiki/en/operations/configuration-and-catalog.md) | `config/models/`, `config/settings.py`, `tests/config/` |
| Change the `piighost` command | [Configure a pipeline](../../../openwiki/en/operations/configuration-and-catalog.md#check-from-the-command-line) | `cli/__init__.py`, `tests/cli/test_cli.py` |
| Add a storage or change the encryption | [Store conversations](../../../openwiki/en/operations/storage-and-encryption.md) | `conversation_memory/`, `crypto/`, `tests/conversation_memory/` |
| Change the LangChain middleware or another integration | [Plug the protection into an agent](../../../openwiki/en/integrations/agents-and-tools.md) | `integrations/`, `integrations/_deidentify.py`, `tests/integrations/` |
| Add a tool to the Claude Code hooks | [Plug the protection into an agent](../../../openwiki/en/integrations/agents-and-tools.md) | `integrations/claude_code/hooks.py` (`_TOOL_OUTPUT_TEXT_FIELDS`), `tests/integrations/test_claude_code_hooks.py` |

For how a contribution goes (branch, commits, review), see [Contributing](contributing.md).
