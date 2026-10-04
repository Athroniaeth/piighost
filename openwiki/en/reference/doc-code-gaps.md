---
type: reference
title: Doc / code gap register
description: Each gap found between the existing PIIGhost documentation (docs/, AGENTS.md, docstrings) and the behavior of the code, with the source on each side and the domain documentation page concerned.
tags: [reference, documentation, discrepancies, review]
sources:
  - id: openwiki-source-ca6cb4b1a14fd7969dfae3ec
    resource: repo://CHANGELOG.md
  - id: openwiki-source-0b69b3c329609131d2e52b9b
    resource: repo://docs/en/architecture.md
  - id: openwiki-source-fa5bbad74af0c6433d558198
    resource: repo://docs/en/community/faq.md
  - id: openwiki-source-0338c20fdc4eb0eacd90211e
    resource: repo://docs/en/roadmap.md
  - id: openwiki-source-85d8e9a0caddafe5d9e86ff1
    resource: repo://docs/en/security.md
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-cf4da74160eab5c3e37887a7
    resource: repo://src/piighost/components/detector/base.py
  - id: openwiki-source-aa685735384e8973ddee846d
    resource: repo://src/piighost/components/linker/exact.py
  - id: openwiki-source-6f090348d19a69e9634505fd
    resource: repo://src/piighost/components/override/base.py
  - id: openwiki-source-6b7f5f02702990f6448a1a5f
    resource: repo://src/piighost/components/override/detector.py
  - id: openwiki-source-bbc55964bae79b175f6d8646
    resource: repo://src/piighost/components/placeholder/__init__.py
  - id: openwiki-source-bf20a98e70f3bb3b8be6a584
    resource: repo://src/piighost/components/placeholder/label_hash.py
  - id: openwiki-source-2e9ef08220178b673a83c4b1
    resource: repo://src/piighost/components/placeholder/label.py
  - id: openwiki-source-9f3ba9afe8d0b86331fc300d
    resource: repo://src/piighost/components/placeholder/redact.py
  - id: openwiki-source-41e1e26a4994aaf47da714b8
    resource: repo://src/piighost/config/models/detector.py
  - id: openwiki-source-7ef27c7836ed8bc6a9f4f484
    resource: repo://src/piighost/config/models/hasher.py
  - id: openwiki-source-beb42dcd927067e197327036
    resource: repo://src/piighost/conversation_memory/base.py
  - id: openwiki-source-e7c9258b08b04c2f058cde4e
    resource: repo://src/piighost/crypto/cipher/base.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Doc / code gap register

## In short

- This page lists the places where the existing documentation says something other than the code.
- The code is authoritative: the domain documentation always describes what the code does.
- No gap is fixed here. Each one awaits a decision from the maintainer, to fix the doc or to fix the code. A settled gap keeps its entry, with its status.
- The gaps found concern the developer documentation and one FAQ example. None changes what the end user sees.

The terms are defined in the [glossary](../glossary.md). Back to the [quickstart](../quickstart.md).

## Read an entry

Each entry gives what the doc says, what the code does, the domain documentation page that covers it and the effect of the gap. When the French version of the doc (`docs/fr/`) repeats the gap, it is cited too. `AGENTS.md` and `CLAUDE.md` are ignored by git in this repository (`.gitignore:186`). Their gaps therefore only affect agents that work locally.

## Gaps

### ECART-01: ports without a `Base*` template

| | |
|---|---|
| Doc | `AGENTS.md:7`, `:26` and `:82`: each stage has an `Any*` port and a `Base*` template. `docs/en/architecture.md:109-111` and `docs/fr/architecture.md:112`: only two ports have no template, the guard rails and the memory. |
| Code | Five ports have no template. They are declared in `components/detector/base.py:9`, `components/override/base.py:9-17`, `components/guard/base.py:42`, `conversation_memory/base.py:10-14`, `crypto/cipher/base.py:7-10`. |
| Domain documentation page | [Add or replace a component](../architecture/ports-and-extension.md) |
| Effect | A contributor can look for a `BaseDetector` that does not exist. |

### ECART-02: version cited in an error message

| | |
|---|---|
| Doc | Message of `config/models/detector.py:62-66`: the built-in catalogs were removed "in piighost 2.0". |
| Code | The package is at `1.10.0` (`pyproject.toml:3`). `CHANGELOG.md` places the move of the catalogs to the hub in 1.8.0. |
| Domain documentation page | [Add or replace a component](../architecture/ports-and-extension.md) |
| Effect | A 1.x user reads a version that does not exist. [to check]: "2.0" may mean the internal rewrite ("v2"), not a published version number. |

### ECART-03: hashed placeholder example

| | |
|---|---|
| Doc | Docstring of `components/placeholder/label_hash.py:14` and `AGENTS.md:45`: the first placeholder is `<<PERSON:6b86b273>>`. |
| Code | `label_hash.py:35-40` hashes the string `PERSON:1`. The first placeholder is `<<PERSON:09ef3b74>>`. `6b86b273` is the digest of the string `1` alone. |
| Domain documentation page | [Glossary](../glossary.md) |
| Effect | A reader who compares a real placeholder to the example believes in a bug. The `docs/` pages use a neutral example (`<<PERSON:a1b2c3d4>>`) and are not affected. |

### ECART-04: shape of the label and redaction placeholders

| | |
|---|---|
| Doc | `AGENTS.md:45` illustrates the "label" axis with `<PERSON>` and `[REDACT]`. |
| Code | The factories emit `<<PERSON>>` (`components/placeholder/label.py:26-28`) and `<<REDACT>>` (`redact.py:25-28`), with the `<<` and `>>` delimiters by default. |
| Domain documentation page | [Glossary](../glossary.md) |
| Effect | Low: the shape of the delimiters is poorly illustrated. |

### ECART-05: hasher of the Redis memory

| | |
|---|---|
| Doc | `AGENTS.md:49`: the Redis backend hashes the keys "with Argon2id". |
| Code | The hasher is a choice, HMAC-SHA256 or Argon2id (`config/models/hasher.py:76-79`). Without a hasher, the key is a non-secret SHA-256 (`conversation_memory/base.py:73-77`). |
| Domain documentation page | [Store conversations and protect traces](../operations/storage-and-encryption.md) |
| Effect | A reader can believe that Argon2id is always active. |

### ECART-06: whitelist, blacklist and cache reads

| | |
|---|---|
| Doc | Docstring of `DetectionOverride` (`components/override/detector.py:51-53`): the pipelines apply the lists "after every detection read". |
| Code | A read from the conversation cache does not go through the lists again (`pipeline/thread.py:271-274`). |
| Domain documentation page | [Impose a whitelist and a blacklist](../processes/impose-a-whitelist-and-blacklist.md) |
| Effect | A modified list does not apply to messages already analyzed. [to check]: if "detection read" means only the call to the detector, the sentence is correct but misleading. |

### ECART-07: `ConversationMemory` class

| | |
|---|---|
| Doc | `docs/en/security.md:23` and `:57`, `docs/fr/security.md:23` and `:58`: "the `ConversationMemory` links variants" and carries the link between value and placeholder. |
| Code | No `ConversationMemory` class. The port is `AnyConversationMemory` (`conversation_memory/base.py:106`). The grouping of the variants is done by `ExactEntityLinker` (`components/linker/exact.py:8-21`), not by the memory, which stores only detections (`conversation_memory/base.py:1-8`). |
| Domain documentation page | [Follow a conversation and restore the reply](../processes/follow-a-conversation.md) |
| Effect | A reader looks for a missing class and attributes the grouping to the wrong component. |

### ECART-08: Faker, planned or ruled out

| | |
|---|---|
| Doc | `docs/en/community/faq.md:32` and `docs/fr/community/faq.md:32`: a Faker factory "is on the roadmap". `docs/en/roadmap.md:40` and `docs/fr/roadmap.md:40` list it under the "Non-goals", ruled out on purpose. |
| Code | No Faker factory in `src/` (`components/placeholder/` contains only `redact`, `label`, `label_counter`, `label_hash`, `mask`). |
| Domain documentation page | [Glossary](../glossary.md) |
| Effect | Two doc pages contradict each other on a feature announced to users. It is the only gap visible to a non-developer audience. |

### ECART-09: result of a tool

| | |
|---|---|
| Doc | `docs/en/tool-call-strategies.md` and `docs/fr/tool-call-strategies.md`, as well as `placeholder-factories.md` in both languages: the reply of a tool is scanned "for the known values". |
| Code | The result goes through the full conversation pipeline, detection included (`integrations/langchain/middleware.py:253-272`). A value never cited before in the conversation is detected too. |
| Domain documentation page | [Let a tool act on the real values](../processes/let-a-tool-act.md) |
| Effect | The doc underestimated the protection. Status: doc fixed on 2026-10-02 (`3473217`). |

### ECART-10: stream cut in the middle of a placeholder

| | |
|---|---|
| Doc | `docs/en/reference/langchain.md` and `docs/fr/reference/langchain.md`: the streamed display "never shows a broken token". |
| Code | At the end of the stream, `flush` returns the held remainder as is (`components/placeholder/streaming.py:186`). A stream cut inside a placeholder therefore shows the beginning of that placeholder. |
| Domain documentation page | [Show a streamed reply](../processes/show-a-streamed-reply.md) |
| Effect | Rare case, with no value leak. Status: doc fixed on 2026-10-02 (`3473217`). |

## Points to check, with no established gap

These points contradict no doc. They are flagged in the pages of the domain documentation with the means to decide.

| Point | Page |
|---|---|
| Does the request go out in clear in Claude Code when `piighost-api` is unreachable? | [Plug the protection into an agent](../integrations/agents-and-tools.md) |
| Does the expiration of a Redis message renumber the placeholders of the conversation? | [Follow a conversation](../processes/follow-a-conversation.md) |
| Overriding a whole section with a JSON object (`PIIGHOST_DETECTOR`) has no test. | [Configure a pipeline](../operations/configuration-and-hub.md) |
