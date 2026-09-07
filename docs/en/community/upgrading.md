---
icon: lucide/arrow-up-circle
---

# Versions and upgrades

`piighost` follows semantic versioning. A patch release changes a behaviour, a minor release adds components or options, and a major release changes the public API. A name marked deprecated keeps working, and keeps resolving to the current implementation, until the next major release.

Check the installed release, then upgrade:

```bash
python -c "import piighost; print(piighost.__version__)"

pip install -U piighost
# or, with uv
uv lock --upgrade-package piighost
```

Every release has an entry in [CHANGELOG.md](https://github.com/Athroniaeth/piighost/blob/master/CHANGELOG.md), with its features, its fixes and its breaking changes.

## API stability

Not every public name carries the same guarantee. A stable name changes only on a major release. An experimental one can change on a minor release, and the CHANGELOG entry says so when it does.

### Stable

<div class="wide-table" markdown="1">

| Surface | What it covers |
|---|---|
| Package root | Every name in `piighost.__all__`: `AnonymizationPipeline`, `ThreadAnonymizationPipeline`, `Anonymizer`, `RegexDetector`, `ExactMatchDetector`, `CompositeDetector`, `ChunkedDetector`, `LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`, `Detection`, `Entity`, `Span`, `PIIGhostError` |
| Ports and templates | Every `Any*` protocol and its `Base*` template, one pair per pipeline stage |
| Data models | `Detection`, `Entity` and `Span`, frozen dataclasses with a stable field set |
| Configuration | `PipelineConfig`, `load_config`, `load_pipeline`, `load_thread_pipeline`, and the keys listed in the [TOML reference](../configuration/toml.md) |
| Command line | `piighost validate`, `piighost schema`, `piighost anonymize` |
| LangChain integration | `PIIAnonymizationMiddleware`, `ToolCallStrategy`, `InventedPlaceholderStrategy`, `EntityCreateByAssistantStrategy` |

</div>

A minor release adds components, options and placeholder factories on top of these without changing them. An option added on a minor release always carries the previous behaviour as its default.

### Experimental

<div class="wide-table" markdown="1">

| Surface | Why it can still move |
|---|---|
| `piighost.integrations.claude_code` | A spike. No Claude Code hook can rewrite the assistant's displayed reply, so that gap is unresolved, and de-identification runs one call per text leaf rather than batched. |
| `piighost.integrations.llama_index` | Recent, two components, and the shape of the query-engine wrapper has not yet been settled against real corpora. |
| `LLMDetector`, `LLMGuardRail` | The prompt and the structured-output schema depend on what a provider accepts, so both can be reshaped when a provider changes. |
| `ModerationGuardRail` | Bound to a third-party Mistral moderation API whose categories and thresholds are outside this project. |

</div>

Pin an exact version if you build on one of these, and read the CHANGELOG before a minor upgrade.

### Deprecated

The names on their way out are listed in the next section, with the release that deprecated them.

Security fixes land on the latest 1.x minor only, on the stable and the experimental surface alike. An older minor receives nothing, so staying current is part of the contract.

## Deprecated names

Three names from earlier releases are still importable. They resolve to the current implementation, so nothing breaks today, and they will be removed in a future major release.

| Deprecated | Use instead | Since | On use |
|---|---|---|---|
| `piighost.integrations.middleware` | `piighost.integrations.langchain` | 1.4.0 | `DeprecationWarning` on import |
| `AssistantEntityStrategy` | `EntityCreateByAssistantStrategy` | 1.5.0 | `DeprecationWarning` on access |
| the `piighost[middleware]` extra | `piighost[langchain]` | 1.4.0 | no warning, both install `langchain` |

The old module and the old strategy name reach the same objects as the current ones, so the update is a rewritten import line:

```python
# deprecated, still works
from piighost.integrations.middleware import AssistantEntityStrategy, PIIAnonymizationMiddleware

# current
from piighost.integrations.langchain import EntityCreateByAssistantStrategy, PIIAnonymizationMiddleware
```

Run your test suite with `python -W error::DeprecationWarning` to fail on any deprecated name left in a code base. The current surface is listed in the [LangChain reference](../reference/langchain.md).

## Argon2 digests changed

`Argon2Hasher` now runs the value through HMAC-SHA256 under the pepper before Argon2id hashes it, so a digest is no longer the one an earlier release produced. Nothing in the API changed, but every key already stored under the old digest becomes unreachable.

This concerns a Redis or SQLAlchemy conversation memory built with `type = "argon2"`. A deployment on `sha256`, or with no hasher at all, is unaffected.

Stored entries are orphaned rather than corrupted. The pipeline finds nothing under the new key, treats the message as never seen, and re-detects it, so an in-flight thread restarts its token numbering and the same value can land on a different number than the one the model has been reading.

Purge the store as part of the upgrade, before restarting the application:

```bash
# Redis, the whole database backing the conversation memory
redis-cli -n 0 FLUSHDB
```

```sql
-- SQLAlchemy, the conversation memory table (its default name)
TRUNCATE TABLE piighost_conversation_messages;
```

An entry left behind expires on its own when a `ttl` is configured. Without one it stays forever, so purging is the only way to reclaim the space.

## Coming from 0.x

Every release before 1.0.0 exposed a different API, so a 0.x code base is ported by rewriting its setup rather than by renaming imports. What changed:

- imports live under `piighost.components`, `piighost.pipeline`, `piighost.config` and `piighost.integrations`
- a pipeline takes a detector and nothing else, since the linker and the anonymizer have defaults
- the `faker`, `cache`, `langfuse` and `opik` extras are gone, and no stage caches detection results
- the `sqlalchemy` extra came back in 1.2.0, as a conversation memory backend

Restart from the [Quickstart](../getting-started/quickstart.md), then read [First pipeline](../getting-started/first-pipeline.md) for the stages and the [TOML reference](../configuration/toml.md) to move the setup into a config file.
