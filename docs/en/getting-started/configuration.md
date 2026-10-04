---
icon: lucide/file-cog
---

# Configuration file

You will describe a whole pipeline in a TOML file. The file starts at three lines and grows into a conversational pipeline, which keeps a token stable across the turns of a conversation. Each step changes one thing in the file, then you check the file and run it to see what changed.

!!! note "Prerequisites"
    `piighost` installed with the `config` extra, `pip install "piighost[config]"`, see [Installation](installation.md). Every step runs without a model. Step 4 fetches a catalog from the [piighost hub](https://hub.piighost.dev) once, then reads it from the on-disk cache. Step 6 adds the `fuzzy` extra.

## 1. Set up the check loop

Two commands drive every step below. Start with a `pipeline.toml` that is wrong on purpose, with `pattern` where the schema expects `patterns`.

```toml
--8<-- "snippets/configuration/typo.toml"
```

Validate it.

```bash
--8<-- "snippets/configuration/validate.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/typo.out"
```

The command names the section and the key it choked on, and exits `1`. That exit code also makes it a CI gate. Run it after every edit below. It builds no component, so it loads no model.

Dump the schema once and point your editor at it for completion on the section and key names.

```bash
--8<-- "snippets/configuration/schema.sh"
```

Both commands are documented in the [command-line interface](../reference/cli.md).

## 2. Build a pipeline from three lines

Fix the key, `patterns` with an s. The file now carries one section, and that is enough to build a pipeline.

```toml
--8<-- "snippets/configuration/email.toml"
```

```bash
--8<-- "snippets/configuration/validate.sh"
```

```text
--8<-- "snippets/configuration/validated.out"
```

Write `run.py` next to it. It loads the file and de-identifies the text you pass on the command line. Every later step reuses `run.py` unchanged.

```python
--8<-- "snippets/configuration/run.py"
```

```bash
--8<-- "snippets/configuration/run_email.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/email.out"
```

The file declares no anonymizer, yet the token names the label and numbers it. It declares no linker, yet both occurrences of one address would share that token. The anonymizer and the linker each fall back to their default, and so does overlap resolution. This file is on disk as `examples/config/detector_only.toml`.

## 3. Pick the token

Ask for a plain redaction instead of the numbered token, with an `[anonymizer.placeholder]` section.

```toml
--8<-- "snippets/configuration/redact.toml"
```

```bash
--8<-- "snippets/configuration/run_email.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/redact.out"
```

The address is gone and its label with it. `examples/config/minimal.toml` carries this file, with the default linker written out. `examples/config/minimal.json` carries the same file in JSON. The file suffix picks the parser. The [configuration reference](../configuration/toml.md) lists every token style.

## 4. Pull a catalog from the hub

Your pattern covers email only, so the IP address in the sample text went through in clear. Replace the inline pattern with the `generic` group of the hub, which carries email, URL, IPv4 and credit card. The `:fab51b33` suffix pins the group to a commit. The group is therefore fetched from the hub the first time the pipeline is built, then read from the cache. Four labels now reach the anonymizer, so put the numbered token back to tell them apart.

```toml
--8<-- "snippets/configuration/hub.toml"
```

```bash
--8<-- "snippets/configuration/run_hub.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/hub.out"
```

The IP address is covered now, and the accented address with it. A format of your own, an order number such as `CMD-2024-0042`{ .pii }, is in no catalog. Declare it inline, next to the catalog.

```toml
--8<-- "snippets/configuration/order.toml"
```

```bash
--8<-- "snippets/configuration/run_order.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/order.out"
```

The order number is a token now. A label declared in both takes your pattern, because catalogs merge first and your inline patterns after them.

## 5. Run two detectors at once

The catalog matches formats, and a first name has no format. Declare the names you already know in a second detector, and let a `composite` detector run both and merge what they return.

```toml
--8<-- "snippets/configuration/composite.toml"
```

```bash
--8<-- "snippets/configuration/run_names.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/composite.out"
```

The names and the formats are caught in one pass. One person spelled two ways still gets two tokens, `<<PERSON:1>>`{ .placeholder } and `<<PERSON:2>>`{ .placeholder }. The next step settles that duplicate.

## 6. Merge the near-duplicate entities

`Patrick`{ .pii } and `Patrik`{ .pii } are the same person, and a model reading two tokens follows two people. Install the `fuzzy` extra.

```bash
pip install "piighost[config,fuzzy]"
```

Append an `[entity_resolver]` section to the file. That section clusters the entities whose values are close enough to each other.

```toml
--8<-- "snippets/configuration/fuzzy.toml"
```

```bash
--8<-- "snippets/configuration/run_names.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/fuzzy.out"
```

Both spellings share `<<PERSON:1>>`{ .placeholder }. Drop the section and the stage is gone again, as it is for every optional stage.

## 7. Keep the tokens across a conversation

Each run of `run.py` restarts the numbering, since the pipeline keeps nothing from one call to the next. Append a `[memory]` section. That section gives the pipeline a per-thread store, and changes the loader you call.

```toml
--8<-- "snippets/configuration/memory.toml"
```

```bash
--8<-- "snippets/configuration/validate.sh"
```

```text
--8<-- "snippets/configuration/validated.out"
```

The file is valid, and `run.py` now refuses it.

```bash
--8<-- "snippets/configuration/run_memory.sh"
```

The traceback ends on:

```text
--8<-- "snippets/configuration/memory.out"
```

A file carrying a memory describes a thread pipeline, so it takes `load_thread_pipeline`. Write `thread.py`, which sends two messages on the thread `"thread-42"`.

```python
--8<-- "snippets/configuration/thread.py"
```

```bash
--8<-- "snippets/configuration/thread.sh"
```

The output should be:

```text
--8<-- "snippets/configuration/thread.out"
```

The second message reuses the `<<PERSON:1>>`{ .placeholder } assigned by the first. Each loader refuses the other's files. `load_thread_pipeline` on a file without a memory therefore raises `this configuration declares no memory; use load_pipeline`.

## What's next

- [Configuration reference](../configuration/toml.md) for every section, every `type` and every key.
- [Deploy a production pipeline](../deployment.md) for a memory shared between workers, Redis or a SQL database, with the stored values encrypted at rest. The two files are `examples/config/thread_redis.toml` and `examples/config/thread_sqlalchemy.toml`.
- [Force a detection or keep a value in clear](../examples/overrides.md) for the deny list and the allow list.
