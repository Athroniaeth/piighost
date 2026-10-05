---
type: glossary
title: Glossary
description: Definitions of the piighost terms (de-identification, placeholder, detection, entity, conversation, provenance, deny list and allow list, guard rail, identifiers, pepper, cipher) with the visible form of each notion and its name in the code.
tags: [glossary, vocabulary, de-identification, placeholder, entity, thread]
sources:
  - id: openwiki-source-aa685735384e8973ddee846d
    resource: repo://src/piighost/components/linker/exact.py
  - id: openwiki-source-a4810bc908328d4c6013f381
    resource: repo://src/piighost/components/placeholder/base.py
  - id: openwiki-source-bf20a98e70f3bb3b8be6a584
    resource: repo://src/piighost/components/placeholder/label_hash.py
  - id: openwiki-source-2e9ef08220178b673a83c4b1
    resource: repo://src/piighost/components/placeholder/label.py
  - id: openwiki-source-657eb428104869e89297f5fd
    resource: repo://src/piighost/components/placeholder/mask.py
  - id: openwiki-source-9f3ba9afe8d0b86331fc300d
    resource: repo://src/piighost/components/placeholder/redact.py
  - id: openwiki-source-169555bcaa5f0efb2e817dc5
    resource: repo://src/piighost/config/models/override.py
  - id: openwiki-source-beb42dcd927067e197327036
    resource: repo://src/piighost/conversation_memory/base.py
  - id: openwiki-source-c8ac86a9a1c1e30960f0784f
    resource: repo://src/piighost/models/detection.py
  - id: openwiki-source-e1607726ec4e3f07dd3e5916
    resource: repo://src/piighost/models/span.py
  - id: openwiki-source-5ddce4dd4539293afb49cdfd
    resource: repo://src/piighost/pipeline/base.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Glossary

`piighost` has no screen. What you "see" is a placeholder in the text sent to the model, an error message, a key of the configuration file or an output of the `piighost` command. The "What you see" column gives this form. The "Technical name" column is for developers.

For the context of each term, start from [Where to start](quickstart.md).

## Protect the data

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Confidential data | Everything `piighost` protects, that is personal data and secrets. | the original value, before protection | none |
| Personal data (PII) | Value that can identify a person, for example a name, an address, a phone or an e-mail. PII stands for *Personally Identifiable Information*. | `Patrick`, `claire.dubois@example.com` | label `PERSON`, `EMAIL`… |
| Secret | Access credential that must never reach a model, for example an API key, a password or a private key. | an API key in a message | catalog group `piighost/logs` |
| De-identification | Replacement of confidential data with placeholders, keeping what is needed to restore them. In the sense of the GDPR (General Data Protection Regulation), it is a pseudonymization. | `Hello <<PERSON:1>>` | default pipeline |
| Anonymization | Removal with no way back. `piighost` achieves it only with a placeholder that keeps nothing. | `<<REDACT>>` | `RedactPlaceholderFactory` |
| Restoration | Putting the real values back in place of the placeholders, in the reply shown to the user. | `Hello Patrick` in the reply | `deanonymize` |
| LLM | *Large Language Model*. AI model that reads and writes text, like the one that answers the user. An LLM can also serve as a detector or a guard rail. | no visible form | `LLMDetector`, `LLMGuardRail` |
| Pipeline | Sequence of stages a text goes through before it reaches the model, from finding the values to replacing them with placeholders. Each stage can be replaced. | the sections of the configuration file | `AnonymizationPipeline`, `ThreadAnonymizationPipeline` |
| DPIA | Data protection impact assessment, required by the GDPR for a risky processing. | [How to document piighost in a DPIA](../../docs/en/dpia.md) | none |

## The placeholders

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Placeholder | Replacement text for a value. The model sees only the placeholder. | `<<PERSON:1>>` | token, `AnyPlaceholderFactory` |
| Numbered placeholder | Placeholder that keeps the type and a number per type, in order of appearance. Default value. | `<<PERSON:1>>`, `<<PERSON:2>>`, `<<EMAIL:1>>` | `LabelCounterPlaceholderFactory` |
| Hashed placeholder | Numbered placeholder whose number is displayed as a hash. The hash comes from the type and the number, never from the value. | `<<PERSON:09ef3b74>>` | `LabelHashPlaceholderFactory` |
| Type placeholder | Placeholder that keeps only the type. Two people receive the same placeholder, so restoration is not reliable. | `<<PERSON>>` | `LabelPlaceholderFactory` |
| Mask | Value of which only the first characters stay visible. No restoration. | `J*******` | `MaskPlaceholderFactory` |
| Invented placeholder | Placeholder in the right format that `piighost` never issued, because the model hallucinated it or a text injected it. | `Deanonymized text holds tokens the pipeline never issued: […]` | `InventedPlaceholderError` |
| Preservation tag | What a type of placeholder keeps, that is the type, the identity, the shape, the ability to be found again. Used for the check before execution. | no visible form | `PreservesRecognizableIdentity`… |

## What piighost spots

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Detector | Component that finds the sensitive values in a text. By pattern, by AI model or by large language model. | key `[detector]` | `AnyDetector` |
| Pattern (regex) | Expression that recognizes a value by its shape. The pattern checks no checksum (Luhn, IBAN). A value damaged by character recognition is therefore still detected. | key `patterns` | `RegexDetector` |
| Catalog | Online service that publishes pattern groups and whole configurations, each addressed by its reference. It was called the hub up to `piighost` 1.x. | `https://catalog.piighost.dev`, variable `PIIGHOST_CATALOG_URL` | `piighost.catalog` |
| Catalog group | List of patterns published on the catalog, for a country, a profession or secrets, and called by its reference. | `catalog:piighost/generic` | key `catalogs`, `RegexDetector.from_catalog` |
| NER | *Named Entity Recognition*. AI model that classifies words as person, place, organization. | key `type = "gliner2"`, `"spacy"`… | `BaseNERDetector` |
| Detection | One occurrence found, with its position, text, type and confidence between 0 and 1. | one line of `piighost anonymize --json` | `Detection` |
| Position (span) | Character interval `[start, end)` of a detection in the text. | `"start": 10, "end": 35` | `Span` |
| Entity | All the occurrences of the same value and the same type. They share a single placeholder. | `Patrick` and `patrick` both give `<<PERSON:1>>` | `Entity`, `ExactEntityLinker` |
| Overlap | Two detections that cover common characters. Depending on the resolver, only one detection is kept, or their union. | no visible form | `ConfidenceOverlapResolver`, `MergeOverlapResolver` |
| Guard rail | Final check that looks for a sensitive value left in the protected text, and blocks the sending if it finds one. | `Anonymized text still contains PII: ['PERSON']` | `AnyGuardRail`, `PIIRemainingError` |
| Fail open | Setting that lets the message leave when an LLM detector or guard rail cannot read the answer of its LLM, or when the Claude Code hooks cannot reach the server. Without this setting, the message is refused. | key `fail_open = true`, variable `PIIGHOST_HOOK_FAIL_OPEN=1` | `fail_open` |

## Conversations

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Conversation (thread) | Exchange followed from one message to the next, isolated from the other exchanges. A value keeps the same placeholder over the whole conversation. | conversation identifier, `--thread-id` | `thread_id` |
| Default thread | Shared thread that the application names itself when its conversations do not need to be separated. No integration falls back to it on its own. A call without a conversation identifier is refused, except by the `piighost anonymize` command. | `default` | `DEFAULT_THREAD_ID`, `MissingThreadIdError` |
| Provenance | Author of the first appearance of a value in the conversation, that is the user or the assistant. A value brought by the assistant stays in clear text by default. | no visible form | `MessageRole`, `get_provenance` |
| Conversation memory | Storage of the detections of each message, per conversation. Contains personal data. When kept in the program, it keeps at most 10,000 conversations. Each one is forgotten one day after its last message. | key `[memory]` | `AnyConversationMemory`, `InMemoryConversationMemory` |
| Conversation erasure | Removal of the whole memory of a conversation, for the right to erasure. Returns the number of messages and detections removed. | `Forgotten(messages=…, detections=…)` | `forget_thread` |
| Human correction | Set of detections corrected by a person for a message, which replaces the one from the detector. | no visible form | `anonymize_corrected` |
| Stream decoder | Component that restores a reply sent as it comes, holding back a cut placeholder until it is whole. | "`<<PER`" held back, then "Jean Dupont" | `AsyncPlaceholderStreamDecoder`, `deanonymize_stream` |
| Tool setting | What a tool receives (real values or placeholders) and what the model reads of its result (masked or in clear text). | "Full", "Input only", "Output only", "None" | `ToolCallStrategy` |

## Integrations

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Hook | Command that a program runs at a fixed point of its work. The Claude Code hooks pass the user's request, the tool calls and their results through `piighost`. | `python -m piighost.integrations.claude_code` in `.claude/settings.json` | `handle_hook` |
| Proxy | Server placed between the application and the model provider. The `piighost-api` server offers one compatible with OpenAI and one compatible with Anthropic. The application only changes its base URL. | `/openai/v1`, `/anthropic/v1` | `piighost-api` |

## Deny list and allow list of the configuration

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Deny list | Values always masked, even if the detector misses them. It is written in the `[override]` section of the application's configuration or of the `piighost-api` server's configuration. | key `[override.deny_list]` | `DetectionOverride.deny_list` |
| Allow list | Values never masked, even if the detector finds them. | key `[override.allow_list]` | `DetectionOverride.allow_list` |

Before `piighost` 2.0, the deny list was called `whitelist` and the allow list `blacklist`. A configuration that still uses these names is refused, see DEC-09 in the [decisions](reference/decisions.md).

## Storage and security

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Digest | Short string computed from a text. The same text always gives the same digest, which does not give the text back. The memory recognizes a message already seen this way. | `piighost:<thread_id>:msg:<digest>` | `message_digest` |
| Pepper | Secret that makes the digests of the messages impossible to recompute without it. | variable `PIIGHOST_HASH_PEPPER` | `AnyHasher` |
| Hasher | Component that computes the digest of each message with the pepper. It is always configured with a cipher. | key `[memory.hasher]` | `Sha256Hasher`, `Argon2Hasher` |
| Cipher | Component that encrypts the stored detections, with an AES (*Advanced Encryption Standard*) key in GCM mode. | variable `PIIGHOST_CIPHER_KEY` | `AesGcmCipher` |
| Trace redactor | Placeholder factory applied to the technical traces, so that they contain no data in clear text. | key `[observation_redactor]` | `observation_redactor` |

## Domain documentation identifiers

The identifiers are in English, the same whatever the language of the page.

| Term | Definition | What you see | Technical name |
|---|---|---|---|
| Need | What a profile expects from `piighost`, with its observable criteria. The prefix names the profile (compliance officer, developer, operator, application user). | `DPO-1`, `DEV-10`, `OPS-7`, `USER-6` | [Needs by profile](needs-by-profile.md) |
| Business rule | Rule written as "When…, then…" in a process page. *BR* stands for *business rule*, followed by the domain. | `BR-MSG-05`, `BR-CONV-03` | "Rules to know" sections |
| Acceptance test | Test that checks one criterion of a need. | `AT-DPO-1-2` | [Acceptance tests](tests/acceptance-tests.md), `tests/acceptance/` |
