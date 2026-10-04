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
| Package root | Every name in `piighost.__all__`, that is `AnonymizationPipeline`, `ThreadAnonymizationPipeline`, `Anonymizer`, `RegexDetector`, `ExactMatchDetector`, `CompositeDetector`, `ChunkedDetector`, `LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`, `Detection`, `Entity`, `Span`, `PIIGhostError` |
| Ports and templates | Every `Any*` protocol and its `Base*` template, one pair per pipeline stage |
| Data models | `Detection`, `Entity` and `Span`, frozen dataclasses with a stable field set |
| Configuration | `PipelineConfig`, `load_config`, `load_pipeline`, `load_thread_pipeline`, and the keys listed in the [TOML reference](../configuration/toml.md) |
| Command line | `piighost validate`, `piighost schema`, `piighost anonymize` |
| LangChain integration | `PIIAnonymizationMiddleware`, `ToolCallStrategy`, `InventedPlaceholderStrategy`, `EntityCreateByAssistantStrategy` |
| Model detectors | `Gliner2Detector`, `SpacyDetector`, `TransformersDetector`, all three on the shared `BaseNERDetector` pass |
| Guard rails | `DetectorGuardRail`, which re-runs any detector on the output |

</div>

A minor release adds components, options and placeholder factories on top of these without changing them. An option added on a minor release always carries the previous behaviour as its default.

### Experimental

<div class="wide-table" markdown="1">

| Surface | Why it can still move |
|---|---|
| `piighost.integrations.claude_code` | A spike. No Claude Code hook can rewrite the assistant's displayed reply, and that gap is unresolved. De-identification also runs one call per text leaf rather than batched. |
| `piighost.integrations.llama_index` | Recent, two components, and the shape of the query-engine wrapper has not yet been settled against real corpora. |
| `LLMDetector`, `LLMGuardRail` | The prompt and the structured-output schema can be reshaped when a provider changes, because they depend on what that provider accepts. |
| `ModerationGuardRail` | Bound to a third-party Mistral moderation API whose categories and thresholds are outside this project. |
| `BridgeDetector`, `AnySpanRunner` | Recent, and the span payload it accepts from a runner has not yet been exercised against enough runners to be frozen. |
| `Gliner2PiiDetector` | A preset. Its default labels follow one PII checkpoint, and move when that checkpoint does. |
| `PresidioDetector` | An adapter over Presidio's analyzer. The recognizers and entity names belong to the Presidio project. |
| `Gliner2GuardRail` | Recent, and its default task and labels follow one guardrail checkpoint. |

</div>

Pin an exact version if you build on an experimental surface, and read the CHANGELOG before a minor upgrade.

### Deprecated

No name is deprecated in 2.0. The names 1.x kept for back-compatibility are removed, and listed in the next section.

Security fixes land on the latest minor only, on the stable and the experimental surface alike. An older minor receives no fix. Staying current is therefore part of the contract.

## Upgrading to 2.0

### The regex catalogs are hub groups

`piighost` ships no pattern of its own. The `piighost.components.detector.patterns` module is gone, with its four catalogs, and the same sets are groups of the [piighost hub](https://hub.piighost.dev).

| 1.x | 2.0 |
|---|---|
| `GENERIC_PATTERNS`, `catalogs = ["generic"]` | `hub:piighost/generic` |
| `US_PATTERNS`, `catalogs = ["us"]` | `hub:piighost/us` |
| `EU_PATTERNS`, `catalogs = ["eu"]` | `hub:piighost/eu` |
| `FR_PATTERNS`, `catalogs = ["fr"]` | `hub:piighost/fr` |

```python
# 1.x
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

detector = RegexDetector({**GENERIC_PATTERNS, **FR_PATTERNS})

# 2.0
--8<-- "snippets/upgrading_catalogs.py:example"
```

A config still naming `generic`, `us`, `eu` or `fr` is refused at load time with the reference that replaces it. A reference pinned to a commit is fetched on the first build and read from the disk cache afterwards. A pipeline therefore reaches the network once. The hub groups have moved on since the catalogs were copied. The group `us` carries `US_ITIN`, `fr` carries `FR_SIREN`, and the email pattern of `generic` takes Latin letters only. `piighost anonymize` with no config runs `hub:piighost/generic`.

### The 1.x aliases are removed

| Removed | Use instead |
|---|---|
| `piighost.integrations.middleware` | `piighost.integrations.langchain` |
| `AssistantEntityStrategy` | `EntityCreateByAssistantStrategy` |
| the `piighost[middleware]` extra | `piighost[langchain]` |

```python
# 1.x
from piighost.integrations.middleware import AssistantEntityStrategy, PIIAnonymizationMiddleware

# 2.0
--8<-- "snippets/upgrading.py:aliases"
```

### `BridgeDetector` takes an offset unit

`offset_unit` is a required keyword, `OffsetUnit.CODE_POINT` for a runner written in Python, `OffsetUnit.UTF16` for one written in JavaScript. A JavaScript runner counts an emoji as two units. Its offsets therefore used to land one character late after each emoji. An offset that is not an integer, `8.0` included, now raises `BridgePayloadError` instead of being truncated. A span scored below `threshold` is dropped, even when the runner ignored that threshold. See the [detectors reference](../reference/detectors.md).

### A thread is always named

`require_thread_id` is removed from the LangChain middleware. A call whose LangGraph config carries no `thread_id` always raises `MissingThreadIdError`, and so does a Claude Code event without a `session_id`. `PIIGhostClient.detect` takes a required `thread_id`. If your conversations need no separation, name the `"default"` thread.

```python
# 1.x
middleware = PIIAnonymizationMiddleware(pipeline, require_thread_id=False)
await agent.ainvoke({"messages": messages})

# 2.0
--8<-- "snippets/upgrading.py:middleware"
--8<-- "snippets/upgrading.py:invoke"
```

### The override lists are renamed

In 1.x the override's `whitelist` held the values always masked, and its `blacklist` the values always left in clear. Most readers expect the reverse from these two words, and a reader who inverts them leaves in clear the values they meant to mask. 2.0 takes the names Presidio uses.

<div class="wide-table" markdown="1">

| 1.x | 2.0 | Meaning |
|---|---|---|
| `whitelist`, `[override.whitelist]` | `deny_list`, `[override.deny_list]` | values always masked |
| `blacklist`, `[override.blacklist]` | `allow_list`, `[override.allow_list]` | values always left in clear |
| `whitelist_strategy`, `WhitelistStrategy` | `deny_list_strategy`, `DenyListStrategy` | how the deny list treats a value the assistant wrote |
| `blacklist_strategy`, `BlacklistStrategy` | `allow_list_strategy`, `AllowListStrategy` | which detections an allow list hit clears |
| `whitelist_wins`, `OverrideConflictStrategy.WHITELIST_WINS` | `deny_list_wins`, `OverrideConflictStrategy.DENY_LIST_WINS` | a value on both lists is masked |
| `blacklist_wins`, `OverrideConflictStrategy.BLACKLIST_WINS` | `allow_list_wins`, `OverrideConflictStrategy.ALLOW_LIST_WINS` | a value on both lists stays in clear |

</div>

The members `RESPECT_PROVENANCE`, `FORCE`, `EXACT`, `VALUE`, `OVERLAP` and `RAISE` keep their names. A config that still uses an old key or value is refused at load time with the name that replaces it, and is never read under the new meaning. `DetectionOverride(whitelist=...)` raises `TypeError`.

```toml
# 1.x
[override]
whitelist_strategy = "force"
conflict_strategy = "whitelist_wins"

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

# 2.0
[override]
deny_list_strategy = "force"
conflict_strategy = "deny_list_wins"

[override.deny_list]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }
```

### Behaviours that changed

- **Unicode spaces.** `RegexDetector` reads every Unicode space as an ordinary one, so a pattern that looked for a no-break space on purpose no longer finds one. Two values that differ only by their spaces are one value, and get one token.
- **Hyphens.** In a whole-word search, every Unicode hyphen joins two words, the non-breaking one Word types included. `Jean`{ .pii } is therefore no longer found inside `Jean‑Paul`{ .pii } written with that hyphen.
- **NER detectors.** Every adapter re-reads the text of a detection from the source and applies its threshold itself, whatever its model returns. A `Gliner2Detector` detection can therefore carry a slightly different text than before, the document's rather than the model's.
- **Overrides.** After a deny list, two detections on one span keep their detector order, as they do when no deny list is set.
- **In-process memory.** `InMemoryConversationMemory` is bounded by default to 10,000 threads and one day idle. An evicted or expired thread no longer restores its tokens. Pass `max_threads=None` and `ttl=None` to get the unbounded 1.x store back.
- **LLM detector and guard.** An output `LLMDetector` or `LLMGuardRail` cannot read raises `UnreadableOutputError` instead of reading as zero detections, so the message is refused. Pass `fail_open=True`, or `fail_open = true` in a config, to send it on undetected as 1.x did.
- **Claude Code hooks.** A hook that cannot de-identify, a server down for instance, blocks the prompt or the tool call and replaces a tool output by a notice. Set `PIIGHOST_HOOK_FAIL_OPEN=1` to let the text through in clear as 1.x did.

A conversation memory written by 1.x keys the provenance of a value by its casefolded text (lowercased in the Unicode sense), while 2.0 keys it by the value with its spaces collapsed. A value typed with an unusual space can lose its provenance across the upgrade. If that provenance matters to a thread in flight, purge the store, as for the Argon2 change below.

### The API server

`piighost-api` requires `piighost>=2.0,<3`, and its configuration follows the 2.0 rules above, the hub references of `catalogs` included.

- `--config` and `PIIGHOST_CONFIG` take a hub reference as well as a file path.
- A configuration without a `[memory]` section is served with the in-process memory instead of being refused. Declare a `redis` memory to share the threads between instances.
- `/v1/anonymize`, `/v1/anonymize/corrected` and `/v1/deanonymize` require a `thread_id`, and answer `400` without one instead of using the shared `"default"` thread.
- `/v1/labels` reads the labels of a hub group from the hub.
- Observation goes through the standard `OTEL_*` variables. `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` serve `dataset extract` only, and no `OPIK_*` variable is read.
- The server reads no `REDIS_URL`. The Redis address is the `url` of the `[memory]` section.
- A deployment still setting `PIPELINE_PATH`, or passing a `module:variable` path, predates the TOML loader. Set `PIIGHOST_CONFIG` to a config file or a hub reference instead.

The routes and the variables are listed in [API endpoints](../reference/api-endpoints.md) and [Server CLI](../reference/api-cli.md).

## Argon2 digests changed

`Argon2Hasher` now runs the value through HMAC-SHA256, keyed by the pepper (the secret read from `PIIGHOST_HASH_PEPPER`), before Argon2id hashes it. A digest is therefore no longer the one an earlier release produced. Nothing in the API changed, but every key already stored under the old digest becomes unreachable.

This concerns a Redis or SQLAlchemy conversation memory built with `type = "argon2"`. A deployment on `sha256`, or with no hasher at all, is unaffected.

Stored entries are orphaned rather than corrupted. The pipeline finds nothing under the new key, treats the message as never seen, and re-detects it. An in-flight thread therefore restarts its token numbering, and the same value can land on a different number than the one the model has been reading.

Purge the store as part of the upgrade, before restarting the application:

```bash
# Redis, the whole database backing the conversation memory
redis-cli -n 0 FLUSHDB
```

```sql
-- SQLAlchemy, the conversation memory table (its default name)
TRUNCATE TABLE piighost_conversation_messages;
```

An entry left behind expires on its own when a `ttl` is configured. Without a `ttl`, it stays forever, so purging is the only way to reclaim the space.

## Coming from 0.x

A 0.x code base is ported by rewriting its setup rather than by renaming imports, because every release before 1.0.0 exposed a different API. What changed:

- imports live under `piighost.components`, `piighost.pipeline`, `piighost.config` and `piighost.integrations`
- a pipeline takes a detector and nothing else, since the linker and the anonymizer have defaults
- the `faker`, `cache`, `langfuse` and `opik` extras are gone, and no stage caches detection results
- the `sqlalchemy` extra came back in 1.2.0, as a conversation memory backend

Restart from the [Quickstart](../getting-started/quickstart.md), then read [First pipeline](../getting-started/first-pipeline.md) for the stages and the [TOML reference](../configuration/toml.md) to move the setup into a config file.
