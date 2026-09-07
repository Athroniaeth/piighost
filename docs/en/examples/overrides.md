---
icon: lucide/gavel
tags:
  - Advanced
  - Detector
---

# How to force a detection or keep a value in clear

Your detector reads your company name as a person and you want that name left alone. Your internal codenames go undetected and you want them replaced every time. Both are decisions about the detection set rather than about the detector, and `DetectionOverride` is the stage that imposes them, a whitelist detector whose hits are forced into the set and a blacklist detector whose hits are dropped from it.

The stage runs right after detection, before overlap resolution and linking, so its two lists trump the detector's reading and also a corrected set coming back from a human review. See [Architecture](../architecture.md) for the full stage order.

!!! note "Prerequisites"
    `piighost` alone, `pip install piighost`. Every snippet below runs as is, no model download and no network. The last section reads a config file, which needs the config extra, `pip install piighost[config]`.

## 1. Keep a value in clear with a blacklist

Point a detector at the value, hand it to `DetectionOverride` as the blacklist, and pass the override to the pipeline. What the blacklist finds leaves the detection set, so the value reaches the model in clear.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "ORG"})
blacklist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(blacklist=blacklist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Emma works at Acme.")
    print(result.text)
    # <<PERSON:1>> works at Acme.


asyncio.run(main())
```

`blacklist_strategy` decides which detections a blacklist hit takes down.

- Keep `BlacklistStrategy.VALUE`, the default, when the value must never be de-identified whatever the detector calls it. It clears every detection carrying the same case-folded text, position and label ignored, so the label you write beside the value never has to match what the primary detector emits.
- Use `BlacklistStrategy.EXACT` when the label is the point, and both detectors read the value the same way. It clears a detection only when its span and its label both match the hit.
- Use `BlacklistStrategy.OVERLAP` when a longer detection containing the value must go down too. It clears any detection whose span touches a blacklisted span, labels ignored.

The three modes on one text, with a detector that mislabels `Acme`{ .pii } as a person and reads `Globex Ltd`{ .pii } as one organization.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import BlacklistStrategy, DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: BlacklistStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector(
        {"Emma": "PERSON", "Acme": "PERSON", "Globex Ltd": "ORG"}
    )
    blacklist = ExactMatchDetector({"Acme": "ORG", "Globex": "ORG"})
    override = DetectionOverride(blacklist=blacklist, blacklist_strategy=strategy)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    return AnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        override=override,
    )


async def main():
    text = "Emma works at Acme, formerly Globex Ltd."
    for strategy in BlacklistStrategy:
        pipeline = build_pipeline(strategy)
        result = await pipeline.anonymize(text)
        print(strategy.value, "->", result.text)


asyncio.run(main())
```

```text
exact -> <<PERSON:1>> works at <<PERSON:2>>, formerly <<ORG:1>>.
value -> <<PERSON:1>> works at Acme, formerly <<ORG:1>>.
overlap -> <<PERSON:1>> works at Acme, formerly Globex Ltd.
```

`EXACT` matched neither detection, since the blacklist says `Acme`{ .pii } is an organization where the detector says a person, and since the detector's span covers `Globex Ltd`{ .pii } where the blacklist covers `Globex`{ .pii } alone. `VALUE` compares whole values, so it cleared `Acme`{ .pii } and left `Globex Ltd`{ .pii }, whose text is not the blacklisted one. `OVERLAP` cleared both, the blacklisted span sitting inside the longer detection.

!!! note "A blacklisted value does not trip the guard rail"
    A [guard rail](../reference/guard-rails.md) re-reads the output and refuses residual PII. The pipeline hands it the values the blacklist matched in the text, so a value you deliberately left in clear is exempt. Any other leak still raises `PIIRemainingError`.

## 2. Force a missed value with a whitelist

Point a detector at the pattern the primary detector misses, here a codename a regex describes exactly, and hand it over as the whitelist. Its hits enter the detection set whatever the primary detector saw.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector(GENERIC_PATTERNS)
whitelist = RegexDetector({"CODENAME": r"ACME-[A-Z]+"})
override = DetectionOverride(whitelist=whitelist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Ship ACME-FALCON to alice@example.com.")
    print(result.text)
    # Ship <<CODENAME:1>> to <<EMAIL:1>>.


asyncio.run(main())
```

A forced hit also replaces every detection it overlaps, so the whitelist label wins over the primary reading. Use that to correct a label, not only to add a detection.

```python
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "PERSON"})
whitelist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(whitelist=whitelist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Acme hired Emma.")
    print(result.text)
    # <<ORG:1>> hired <<PERSON:1>>.


asyncio.run(main())
```

A forced value goes through linking and token assignment like any other detection, so the conversational pipeline stores it in memory and `deanonymize` restores it.

## 3. Tokenize a value the assistant introduced

In a thread, a value the assistant wrote first stays in clear even when the whitelist matches it. The model produced that value because it was useful in context and does not know it is confidential, so replacing it would strip its world knowledge and signal that this precise value is sensitive. `whitelist_strategy` decides who wins.

- Keep `WhitelistStrategy.RESPECT_PROVENANCE`, the default, to leave an assistant-introduced value in clear. The whitelist still guarantees the value is detected, and the same value introduced by the user is still tokenized.
- Use `WhitelistStrategy.FORCE` to tokenize a whitelisted value whoever wrote it first.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride, WhitelistStrategy
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
from piighost.pipeline import ThreadAnonymizationPipeline


def build_pipeline(strategy: WhitelistStrategy) -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({})
    whitelist = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(whitelist=whitelist, whitelist_strategy=strategy)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    memory = InMemoryConversationMemory()
    return ThreadAnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        memory,
        override=override,
    )


async def main():
    for strategy in WhitelistStrategy:
        pipeline = build_pipeline(strategy)
        assistant = await pipeline.anonymize("Acme rocks", "t1", MessageRole.ASSISTANT)
        user = await pipeline.anonymize("I love Acme", "t1")
        print(strategy.value, "->", assistant.text, "|", user.text)


asyncio.run(main())
```

```text
respect_provenance -> Acme rocks | I love Acme
force -> <<ORG:1>> rocks | I love <<ORG:1>>
```

## 4. Decide who wins when the two lists contradict

A value both lists match is a contradiction, and `conflict_strategy` names the winner.

- Keep `OverrideConflictStrategy.WHITELIST_WINS`, the default, to de-identify the contradicted value. The blacklist applies to the primary detections first, then the whitelist is forced in last.
- Use `OverrideConflictStrategy.BLACKLIST_WINS` to keep it in clear. The whitelist is forced in first, then the blacklist clears the result, forced hits included.
- Use `OverrideConflictStrategy.RAISE` to refuse the contradiction. A whitelisted span overlapping a blacklisted one raises `ConflictingOverrideError` before either list is applied.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride, OverrideConflictStrategy
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import ConflictingOverrideError
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: OverrideConflictStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON"})
    whitelist = ExactMatchDetector({"Acme": "ORG"})
    blacklist = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(
        whitelist=whitelist,
        blacklist=blacklist,
        conflict_strategy=strategy,
    )
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    return AnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        override=override,
    )


async def main():
    for strategy in OverrideConflictStrategy:
        pipeline = build_pipeline(strategy)
        try:
            result = await pipeline.anonymize("Emma works at Acme.")
        except ConflictingOverrideError as error:
            print(strategy.value, "->", type(error).__name__, error)
        else:
            print(strategy.value, "->", result.text)


asyncio.run(main())
```

```text
whitelist_wins -> <<PERSON:1>> works at <<ORG:1>>.
blacklist_wins -> <<PERSON:1>> works at Acme.
raise -> ConflictingOverrideError Overrides contradict each other on 'Acme': a whitelisted span overlaps a blacklisted one.
```

`BLACKLIST_WINS` clears a forced hit through the blacklist strategy, so the default `VALUE` clears a forced value whatever label the whitelist attached to it. Under `EXACT` the two lists have to agree on the label for the blacklist to win.

## 5. Drive the override from a config file

Both lists are detector configs, `[override.whitelist]` and `[override.blacklist]`, and the three strategies are keys of `[override]`. The file below forces the codename and keeps a public mailbox in clear.

```toml
[detector]
type = "regex"
catalogs = ["generic"]

[override]
blacklist_strategy = "value"

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[override.blacklist]
type = "exact"
values = { "public@corp.com" = "EMAIL" }
```

`load_pipeline` parses the file and builds the pipeline, override included.

```python
import asyncio

from piighost.config import load_pipeline

pipeline = load_pipeline("piighost.toml")


async def main():
    result = await pipeline.anonymize(
        "Mail public@corp.com or alice@example.com about ACME-FALCON."
    )
    print(result.text)
    # Mail public@corp.com or <<EMAIL:1>> about <<CODENAME:1>>.


asyncio.run(main())
```

For every key and every accepted value, see the [TOML configuration](../configuration/toml.md).

## See also

- [Pre-built detectors](detectors.md) for the detectors the two lists are built on.
- [Pipeline reference](../reference/pipeline.md) for the `override` parameter and the stage order.
- [Guard rails](../reference/guard-rails.md) for the output check the blacklist exempts a value from.
- [TOML configuration](../configuration/toml.md) for the `[override]` keys.
