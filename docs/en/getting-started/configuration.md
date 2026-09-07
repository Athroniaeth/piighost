---
icon: lucide/file-cog
---

# Configuration file

You will describe a whole pipeline in a TOML file, growing it from three lines to a conversational pipeline that keeps a token stable across the turns of a conversation. Each step changes one thing in the file, then you check the file and run it to see what changed.

!!! note "Prerequisites"
    `piighost` installed with the `config` extra, `pip install "piighost[config]"`, see [Installation](installation.md). Every step runs without a model and without network access. Step 6 adds the `fuzzy` extra.

## 1. Set up the check loop

Two commands drive every step below. Start with a `pipeline.toml` that is wrong on purpose, with `pattern` where the schema expects `patterns`.

```toml
[detector]
type = "regex"
pattern = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

Validate it.

```bash
piighost validate pipeline.toml
```

The output should be:

```text
invalid configuration in pipeline.toml: 1 validation error for PipelineConfig
detector.regex.pattern
  Extra inputs are not permitted [type=extra_forbidden, input_value={'EMAIL': '[a-z0-9._%+-]+...a-z0-9.-]+\\.[a-z]{2,}'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/extra_forbidden
```

The command names the section and the key it choked on, and exits `1`, which also makes it a CI gate. Run it after every edit below. It builds no component, so it loads no model.

Dump the schema once and point your editor at it for completion on the section and key names.

```bash
piighost schema > schema.json
```

Both commands are documented in the [command-line interface](../reference/cli.md).

## 2. Build a pipeline from three lines

Fix the key, `patterns` with an s. The file now carries one section, and that is enough to build a pipeline.

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

```bash
piighost validate pipeline.toml
```

```text
OK: pipeline.toml
```

Write `run.py` next to it. It loads the file and de-identifies the text you pass on the command line, and every later step reuses it unchanged.

```python
import asyncio
import sys

from piighost.config import load_pipeline


async def main() -> None:
    pipeline = load_pipeline("pipeline.toml")
    result = await pipeline.anonymize(sys.argv[1])
    print(result.text)


asyncio.run(main())
```

```bash
python run.py "Write to alice@corp.com from 10.0.0.7."
```

The output should be:

```text
Write to <<EMAIL:1>> from 10.0.0.7.
```

The token names the label and numbers it although the file declares no anonymizer, and both occurrences of one address would share that token although the file declares no linker. Each of those two stages falls back to its default, and so does overlap resolution. This file is on disk as `examples/config/detector_only.toml`.

## 3. Pick the token

Ask for a plain redaction instead of the numbered token, with an `[anonymizer.placeholder]` section.

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }

[anonymizer.placeholder]
type = "redact"
```

```bash
python run.py "Write to alice@corp.com from 10.0.0.7."
```

The output should be:

```text
Write to <<REDACT>> from 10.0.0.7.
```

The address is gone and its label with it. `examples/config/minimal.toml` carries this file with the default linker written out, and `examples/config/minimal.json` carries it in JSON, the suffix picking the parser. The [configuration reference](../configuration/toml.md) lists every token style.

## 4. Pull a prebuilt catalog

Your pattern covers email only, so the IP address in the sample text went through in clear. Replace the inline pattern with the `generic` catalog, which carries email, URL, IPv4 and credit card. Four labels now reach the anonymizer, so put the numbered token back to tell them apart.

```toml
[detector]
type = "regex"
catalogs = ["generic"]

[anonymizer.placeholder]
type = "label_counter"
```

```bash
python run.py "Write to alice@corp.com and prénom@corp.com from 10.0.0.7."
```

The output should be:

```text
Write to <<EMAIL:1>> and pré<<EMAIL:2>> from <<IPV4:1>>.
```

The IP address is covered now, and `prénom@corp.com`{ .pii } only half of it. The catalog patterns match ASCII shapes, so the match starts after the accent. Add an inline pattern on the same label, and it overrides the catalog's.

```toml
[detector]
type = "regex"
catalogs = ["generic"]
patterns = { EMAIL = '[A-Za-zÀ-ÿ0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' }

[anonymizer.placeholder]
type = "label_counter"
```

```bash
python run.py "Write to alice@corp.com and prénom@corp.com from 10.0.0.7."
```

The output should be:

```text
Write to <<EMAIL:1>> and <<EMAIL:2>> from <<IPV4:1>>.
```

The whole address is a token now. Catalogs merge first, then your inline patterns, so a label declared in both takes your pattern.

## 5. Run two detectors at once

The catalog matches formats, and a first name has no format. Declare the names you already know in a second detector, and let a `composite` detector run both and merge what they return.

```toml
[detector]
type = "composite"

[[detector.detectors]]
type = "regex"
catalogs = ["generic"]
patterns = { EMAIL = '[A-Za-zÀ-ÿ0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' }

[[detector.detectors]]
type = "exact"
values = { Patrick = "PERSON", Patrik = "PERSON" }

[anonymizer.placeholder]
type = "label_counter"
```

```bash
python run.py "Patrick writes to alice@corp.com. Patrik answers from 10.0.0.7."
```

The output should be:

```text
<<PERSON:1>> writes to <<EMAIL:1>>. <<PERSON:2>> answers from <<IPV4:1>>.
```

The names and the formats are caught in one pass. One person spelled two ways still gets two tokens, `<<PERSON:1>>`{ .placeholder } and `<<PERSON:2>>`{ .placeholder }, which the next step settles.

## 6. Merge the near-duplicate entities

`Patrick`{ .pii } and `Patrik`{ .pii } are the same person, and a model reading two tokens follows two people. Install the `fuzzy` extra.

```bash
pip install "piighost[config,fuzzy]"
```

Append an `[entity_resolver]` section to the file, which clusters the entities whose values are close enough to each other.

```toml
[entity_resolver]
type = "fuzzy"
threshold = 0.85
```

```bash
python run.py "Patrick writes to alice@corp.com. Patrik answers from 10.0.0.7."
```

The output should be:

```text
<<PERSON:1>> writes to <<EMAIL:1>>. <<PERSON:1>> answers from <<IPV4:1>>.
```

Both spellings share `<<PERSON:1>>`{ .placeholder }. Drop the section and the stage is gone again, as it is for every optional stage.

## 7. Keep the tokens across a conversation

Each run of `run.py` restarts the numbering, since the pipeline keeps nothing from one call to the next. Append a `[memory]` section, which gives it a per-thread store and changes the loader you call.

```toml
[memory]
type = "in_memory"
```

```bash
piighost validate pipeline.toml
```

```text
OK: pipeline.toml
```

The file is valid, and `run.py` now refuses it.

```bash
python run.py "Patrick writes to alice@corp.com."
```

The traceback ends on:

```text
piighost.exceptions.ConfigError: this configuration declares a memory; use load_thread_pipeline
```

A file carrying a memory describes a thread pipeline, so it takes `load_thread_pipeline`. Write `thread.py`, which sends two messages on the thread `"thread-42"`.

```python
import asyncio

from piighost.config import load_thread_pipeline


async def main() -> None:
    pipeline = load_thread_pipeline("pipeline.toml")
    first = await pipeline.anonymize("Patrick writes to alice@corp.com.", "thread-42")
    print(first.text)
    second = await pipeline.anonymize("Patrik answers from 10.0.0.7.", "thread-42")
    print(second.text)


asyncio.run(main())
```

```bash
python thread.py
```

The output should be:

```text
<<PERSON:1>> writes to <<EMAIL:1>>.
<<PERSON:1>> answers from <<IPV4:1>>.
```

The second message reuses the `<<PERSON:1>>`{ .placeholder } assigned by the first. The two loaders refuse each other's files, so `load_thread_pipeline` on a file without a memory raises `this configuration declares no memory; use load_pipeline`.

## What's next

- [Configuration reference](../configuration/toml.md) for every section, every `type` and every key.
- [Deploy a production pipeline](../deployment.md) for a memory shared between workers, Redis or a SQL database, with the stored values encrypted at rest. The two files are `examples/config/thread_redis.toml` and `examples/config/thread_sqlalchemy.toml`.
- [Force a detection or keep a value in clear](../examples/overrides.md) for the whitelist and the blacklist.
