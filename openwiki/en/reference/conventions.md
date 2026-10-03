---
type: reference
title: Conventions and technical choices
description: The conventions PIIGhost follows without a need imposing them directly, the shape of placeholders, detection, security by default, restoration, storage and architecture, with the reason for each and where it lives in the code.
tags: [conventions, decisions, placeholder, detection, security]
generated: { by: "claude-code", at: "2026-10-03T18:00:00.000Z" }
---

# Conventions and technical choices

## In short

De-identification called for choices as PIIGhost evolved. It first de-identified a single text, then a whole conversation, then the exchanges of an agent with its tools. Each step set conventions, such as the shape of a placeholder or the behavior of a default setting. This page gathers them so that they do not stay implicit. For each one, it gives the reason for the choice and where it applies in the code, and cites the business rule it supports when there is one. These conventions bind the rest of the library, so changing one calls for a discussion first.

## Placeholders

- **Delimiters `<<` and `>>`**: a placeholder is wrapped in doubled angle brackets. This sequence is rare in ordinary text, so a regular expression finds a placeholder easily. It also tells the model that it reads masked data. Code, `components/placeholder/streaming.py` (`DEFAULT_PREFIX`, `DEFAULT_SUFFIX`).
- **Shape `<<LABEL:n>>`**: the label tells the model what the value is, a person or an email for example. The number tells apart the individuals of one type. It starts at 1 for each label, in order of appearance. Code, `components/placeholder/label_counter.py`.
- **Grammar of a placeholder**: a label starts with a letter or `_`, then holds letters, digits, `_`, spaces or hyphens. A label of several words, as a NER model emits, is therefore accepted. The identifier after the colon is alphanumeric. Code, `components/placeholder/streaming.py` (`LABEL_INNER`).
- **Hashed placeholder**: the shape `<<PERSON:6b86b273>>` is the SHA-256 digest of "label:rank", never of the value. It hides no secret, and nothing can be learned from it about the value. Code, `components/placeholder/label_hash.py`.
- **Same placeholder over the whole conversation**: a value keeps its placeholder from one message to the next, and each conversation has its own placeholders. The model can then follow who is who. Code, `pipeline/thread.py`. Rule BR-MSG-02.
- **Recognizable identity**: the middleware refuses, as soon as it is built, a placeholder shape that does not tell individuals apart, such as `<<PERSON>>`. Without an identity, a value could not be restored. Code, `components/placeholder/tags.py` (`PreservesRecognizableIdentity`).

## Detection

- **No check-digit validation**: a card or an IBAN is masked on its shape alone. A value damaged by character recognition is therefore still detected, at the cost of some false positives. Code, `components/detector/regex.py`. Rule BR-MSG-07.
- **Regular expressions in ASCII**: `\d` matches only the digits 0 to 9, and the shape of a value stays predictable. Code, `components/detector/regex.py` (`re.ASCII`).
- **Unicode spaces normalized**: every Unicode space, no-break or thin, counts as an ordinary space. The length of the text does not change, so positions stay right. Code, `text/normalization.py` (`normalize_spaces`). Rule BR-MSG-06.
- **One value, whatever its spaces and case**: "Jean  Dupont" and "jean dupont" get the same placeholder. Code, `text/normalization.py` (`value_key`). Rule BR-MSG-02.
- **Whole-word search**: "Jean" is not found in "Jeanne". A Unicode hyphen joins two words. Code, `text/boundaries.py`.
- **Overlaps always resolved**: the resolver cannot be turned off, because replacement needs disjoint spans. The surest detection wins, and on a tie, the first declared detector. Code, `components/overlap_resolver/`. Rule BR-MSG-05.
- **No positions from an LLM**: an LLM detector names values, and PIIGhost looks them up in the text itself. A value the model made up, absent from the text, is therefore ignored. The text sent is wrapped in tags, and a tag found in the text is neutralized. Code, `components/detector/llm.py`.

## Security by default

Each default picks the side that protects. An explicit setting allows the opposite.

- **Placeholder typed by the user neutralized**: an invisible character (U+200B) is inserted in the text, so that a user cannot make the value of another appear. Code, `components/anonymizer/span.py`. Rule BR-MSG-09.
- **Placeholder invented by the model refused**: a placeholder of the right shape that was never issued blocks the reply, rather than being shown or silently dropped. Rules BR-CONV-06 and BR-TOOL-07.
- **Conversation identifier required**: a call without an identifier fails, instead of sharing a common conversation. Rule BR-AGT-01.
- **Failed detector refuses the message**: an unreadable output of an LLM detector blocks the message, and the Claude Code hooks block when the server does not answer. Need DPO-9.
- **Bounded memory**: the process memory keeps at most 10,000 conversations, and forgets a conversation after one day without activity. Code, `conversation_memory/memory.py`. Rules BR-STO-04 and BR-CONV-11.

## Restoration

- **From the longest placeholder to the shortest**: `<<PERSON:1>>` does not replace the start of `<<PERSON:10>>`. Code, `components/anonymizer/base.py`.
- **Placeholder cut while streaming**: a placeholder cut between two chunks is held until it is complete, up to 128 characters. A lone `<` at the end of a chunk is held too. Code, `components/placeholder/streaming.py`. Rules BR-STREAM-03 and BR-STREAM-04.
- **Real value to tools**: by default, a tool receives the real value, and the model only sees the placeholder. Code, `integrations/langchain/middleware.py` (`ToolCallStrategy.FULL`).
- **Value introduced by the assistant**: by default, a value the model writes on its own is kept as it is. Code, `integrations/langchain/middleware.py` (`EntityCreateByAssistantStrategy.PRESERVE`).

## Storage and configuration

- **Hashed keys and encrypted values**: with Redis, keys go through HMAC then Argon2id with a pepper, and values are encrypted with AES-GCM. The conversation identifier stays readable, so that a conversation can be erased. Code, `crypto/` and `conversation_memory/redis_backend.py`. Rule BR-STO-03.
- **Secrets in the environment only**: the pepper and the encryption key are never written in a configuration file. Code, `config/`.
- **Hub references**: a reference pinned to a commit is cached. A tag or `latest` is read again every time, so that a stale version is never served. Code, `hub.py`.

## Architecture

- **Everything is asynchronous**: model detectors and remote servers are, and the pipeline awaits them without blocking.
- **One port per step**: each step has an interface, and most have a base template. Only the detector is required. See [Add or replace a component](../architecture/ports-and-extension.md).
- **Configuration coupled one way**: the configuration knows the core of the library, never the other way round. Code, `config/`.
- **A core without rules tied to a language**: lists of French or domain words go in the hub groups, not in the library.

The terms are defined in the [glossary](../glossary.md).
