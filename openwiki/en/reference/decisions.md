---
type: reference
title: Design decisions
description: The decisions that built the piighost de-identification system, in the order they arose, each explained with an example, and the place in the code where it lives.
tags: [decisions, conventions, placeholder, detection, conversation, security]
generated: { by: "claude-code", at: "2026-10-03T18:00:00.000Z" }
---

# Design decisions

## In short

The de-identification system was built in steps, and each new need called for a decision. To replace a confidential value with a placeholder, the system first had to find it in the text, at a precise position. For the model to still understand the text, the placeholder had to say what type of data it stands for. To tell two people apart, the placeholder needed an identifier. So the system had to know which detections refer to the same person. For the user to read their real data, the mapping between each placeholder and its value had to be kept. Then came the conversation, the tools of an agent, streaming and production.

This page presents these decisions in the order they arose. Each one carries a `DEC-NN` identifier. It explains the problem, the choice made and what it changes, with an example when one helps. It ends with the place in the code where it is implemented, and the business rules that follow from it. Together, these decisions make up the pipeline, the sequence of steps that goes from the original text to the protected text. The technical documentation describes the components of this pipeline, in [Pipeline design](../../../docs/en/conception.md). The rest of the library depends on these decisions, so discuss any change before making it.

## De-identify a text

### DEC-01: Replace each confidential value with a placeholder

A text must go to an AI model without its confidential data. Yet the model must still be able to answer it. Deleting the data does not work, because a sentence stripped of its names loses its meaning. "Tell Jean Dupont his appointment has moved" would become "Tell his appointment has moved", and the model would no longer know whom to tell.

So `piighost` replaces each value with a placeholder, a short text that stands in its place. By default, the value is neither deleted nor masked letter by letter. The sentence stays readable, and the model can answer by reusing the placeholder. The rest of the system exists to produce these placeholders, keep them consistent and turn them back into values.

### DEC-02: Find each value and its exact position

To replace a value, you need to know where it starts and where it ends in the text. That is the job of a detector. Each value it finds is called a detection. A detection gives a span, a start and end position, with the type of the data and a confidence score. This score is a number between 0 and 1 that says how sure the detector is.

No detector finds everything, so several can run together. Two families complement each other:

- Regular expressions: these are patterns that recognize fixed formats, such as an email, an IBAN or a phone number.
- NER models: these are AI models trained to recognize, in free text, the names of people, places or organizations.

An LLM detector works differently. An LLM is a large language model, queried like an assistant. It names values without giving their position, and `piighost` then finds them in the text on its own. A value the LLM makes up is therefore ignored, because it is not in the text.

This way of detecting has three limits. First, a value no detector sees goes out unmasked. Second, a regular expression recognizes a value by its shape alone. It does not verify the check digits, the verification digits an IBAN carries. An IBAN damaged by character recognition (OCR) is thus still detected, even if its check digits have become wrong. Third, a regular expression only recognizes basic digits and Latin letters. An Arabic-Indic digit, for example, is not read as a digit. Any Unicode space, such as a non-breaking space, does count as an ordinary space.

Implemented in `components/detector/` and `text/normalization.py`. Rules BR-MSG-06, BR-MSG-07 and BR-MSG-10 follow from it.

### DEC-03: Wrap each placeholder in `<<` and `>>`

A placeholder needs a form that stands out in the text. `piighost` wraps it in double angle brackets, as in `<<REDACT>>`.

This sequence of characters is rare in ordinary text. A program therefore finds each placeholder easily, with a regular expression. The brackets also tell the model that it is reading masked data, not a word of the sentence.

Nothing stops a user from typing this sequence themselves, though. `piighost` neutralizes a placeholder typed by hand, see DEC-13.

Implemented in `components/placeholder/streaming.py` (`DEFAULT_PREFIX`, `DEFAULT_SUFFIX`).

### DEC-04: Say in the placeholder what type of data it stands for

If every value becomes `<<REDACT>>`, the model no longer knows what it reads. In "Summarize the exchange between `<<REDACT>>` and `<<REDACT>>`", it does not know whether these are two people, two companies or two email addresses. So it answers badly.

So the placeholder states the type of the data, called the label, as in `<<PERSON>>` or `<<EMAIL>>`. With `<<PERSON>>`, the model knows it is a person. It can write "Hello `<<PERSON>>`".

The label comes from the detector. For a NER model, it is the category the model gives. For a regular expression, it is the name you give it, for example `EMAIL`. A detector can also translate its model's labels into the ones you want to see in the placeholders.

A label is written in unaccented letters, digits, `_`, spaces or hyphens, and starts with a letter or `_`. `DATE_OF_BIRTH` works, `PRÉNOM` does not.

One problem remains. Two people still get the same placeholder, see DEC-05.

Implemented in `components/detector/ner/base.py` (label translation) and `components/placeholder/streaming.py` (`LABEL_INNER`).

### DEC-05: Give each entity its own identifier

With `<<PERSON>>`, two people in the same text get the same placeholder. "Summarize the exchange between `<<PERSON>>` and `<<PERSON>>`" no longer says who spoke, and the model mixes them up.

So the placeholder adds an identifier after the label, as in `<<PERSON:1>>` and `<<PERSON:2>>`. By default, it is a number counted per label, from 1, in order of appearance. The model reads it easily.

Another form replaces the number with a fingerprint, as in `<<PERSON:a1b2c3d4>>`. A fingerprint is a string of characters computed from a text, here with the SHA-256 algorithm. `piighost` computes it from the label and the sequence number, never from the value. It needs no secret key, and reveals nothing about the value. Its only purpose is that two neighboring placeholders do not look consecutive.

To assign these identifiers, you need to know which detections refer to the same person or the same value, see DEC-06.

Implemented in `components/placeholder/label_counter.py` and `components/placeholder/label_hash.py`. Rule BR-MSG-01 follows from it.

### DEC-06: Group the detections of the same entity

The same person often appears several times in a text, sometimes written differently. All their occurrences must get the same placeholder. Otherwise, "Jean Dupont" and "jean dupont" would get two placeholders, and the model would think it is reading about two people.

So `piighost` tells two notions apart:

- The detection: one occurrence found in the text, at a precise position. It comes from the detector, see DEC-02.
- The entity: the person or the value itself, which brings together all its detections. The entity is what gets a placeholder.

In "Jean Dupont called. Call Jean Dupont back tomorrow.", the detector returns two detections, one per occurrence. They form a single entity, and both occurrences become `<<PERSON:1>>`.

`piighost` groups into one entity the detections that have the same value and the same label. Two values that differ only in spacing or capitalization count as the same value.

Two options go further. One option searches the text for other occurrences of a value already found, in case a detector missed them. Another brings together close spellings, such as "Jean Dupont" and "Jean Dupond", through approximate matching. This matching can also bring two truly different people under one placeholder.

An entity keeps only one spelling. When the reply is restored (see DEC-08), the entity comes back with the spelling that appeared first. If "Jean Dupont" appears before "jean dupont", both come back written "Jean Dupont".

Implemented in `components/linker/`, `components/expander/`, `components/entity_resolver/` and `text/normalization.py` (`value_key`). Rules BR-MSG-02, BR-MSG-03 and BR-MSG-12 follow from it.

### DEC-07: Keep a single span when two detections overlap

Two detectors can find spans that overlap. One finds "Jean", the other "Jean Dupont". `piighost` can only replace spans that do not overlap. If any remain when replacing, it refuses the text rather than leave a piece of it unmasked.

So a single span is kept. By default, the detection with the highest confidence score wins. On an equal score, the detection that starts earliest wins, then the shortest. The order of the detectors only breaks a tie between two detections of the exact same span.

This setting has a cost. If "Jean" has the best score, only "Jean" is replaced, and "Dupont" goes out unmasked. The other setting, merging, avoids this leak. It keeps a single span that covers both, here "Jean Dupont", with the label of the surest detection.

This step cannot be turned off.

Implemented in `components/overlap_resolver/`. Rule BR-MSG-05 follows from it.

### DEC-08: Keep the mapping to restore the real values

The user must read the reply with their real data, not with placeholders. So `piighost` records the value each placeholder replaces. This table is called the mapping. Without it, no restoration is possible.

In the model's reply, each known placeholder is replaced with its value. "Hello `<<PERSON:1>>`" becomes "Hello Jean Dupont" again. A restored value is never examined a second time. A real value that looks like a placeholder is therefore shown as is.

Another approach does without a mapping. Google Sensitive Data Protection (formerly Cloud DLP) can encrypt the value itself into the placeholder, with a key. The placeholder starts with a name chosen by the team, followed by the length of the encrypted text, then that text, in the form `PHONE_TOKEN(36):AYCL…`. Restoring the value takes the whole placeholder and the same key. No value is stored.

`piighost` chose the mapping for four reasons:

- The placeholder stays short and readable: the model easily copies `<<PERSON:1>>`. A placeholder encrypted with AES-SIV is a long string of characters, harder to copy without a mistake.
- The placeholder does not hold the value: an encrypted placeholder holds it. The placeholders sent to the model stay in its logs, and a leak of the key makes them all readable. A `piighost` placeholder reveals nothing without the conversation's memory.
- The placeholder holds for one conversation only: by default, with the same key, a value always gives the same placeholder. Someone can then link every conversation it appears in. With `piighost`, `<<PERSON:1>>` can stand for another person in another conversation, see DEC-11.
- A conversation can be forgotten: erasing its mapping makes its placeholders impossible to restore, once every process of the service has forgotten it. With a single key for the whole service, an encrypted placeholder stays decryptable as long as that key exists.

This choice has a cost. `piighost` must keep a memory that holds the values of each conversation. It is not a mere cache, because it cannot be rebuilt. Losing it prevents restoring the conversation's placeholders. This memory must be protected (DEC-18) and bounded, see DEC-19. If the service runs on several servers, it must be shared between them (DEC-11).

The real values can be recovered. Under the GDPR, this is therefore pseudonymization, not anonymization. The mapping is itself personal data to protect, see DEC-18.

Implemented in `components/anonymizer/base.py`. Rule BR-CONV-05 follows from it.

### DEC-09: Let people correct the detection

A detector makes two kinds of mistakes. It misses some values, and it masks others by mistake. A server or a team knows its own sensitive values, and the words the detector masks by mistake.

So two lists, set by the server, override the detector:

- The deny list (`deny_list` in the configuration): it masks a value, even if the detector missed it.
- The allow list (`allow_list`): it leaves a value unmasked, even if the detector found it.

Before `piighost` 2.0, these lists were called `whitelist` and `blacklist`, and the whitelist forced masking. Most readers take a whitelist to allow, and a list read the wrong way round leaves in clear the values it was written to mask. Version 2.0 takes the names Presidio uses. A configuration that still uses the old names is refused at load time, never read under the new meaning. A deny list holding the client code `CLI-4821` masks it even when the detector misses it. An allow list holding "Doctor" keeps this word from being taken for a name. If a value is on both lists, it is masked by default.

A person can also correct the values of a message by hand. This correction holds for that message only, and the two lists still apply on top of it.

Implemented in `components/override/` and `pipeline/thread.py`. Rules BR-LIST-01, BR-LIST-02 and BR-CONV-07 follow from it.

### DEC-10: Reread the protected text before sending, as an option

A value every detector missed goes out unmasked. A final check, called the guard rail, can reread the already de-identified text before it is sent. If it still finds confidential data there, the text is not sent, and the application gets an error.

The guard rail is a second line of defense. Its main benefit is that it can use a different tool from the detectors. Take a classification model, a model that sorts a text into a category such as "safe" or "unsafe". It can tell that a text holds confidential data, without being able to say where it is. So it cannot serve as a detector, because a detector must give the position of each value (DEC-02). It can serve as a guard rail, though.

The guard rail corrects nothing. It reports a leak and blocks the sending, but does not replace the value, because it does not always know where it is. A model that can locate values usually serves as a detector. A guard rail can still rerun a stronger detector than the pipeline's, to catch what the first one missed. The guard rail also makes sending slower.

Implemented in `components/guard/`. Rules BR-MSG-10 and BR-MSG-11 follow from it.

## Hold a conversation

### DEC-11: Keep the same placeholder for the whole conversation

A conversation has several messages. If "Jean Dupont" becomes `<<PERSON:1>>` in the first message and `<<PERSON:2>>` in the third, the model thinks it is reading about two people. De-identifying each message on its own is therefore not enough, because the numbers would change from one message to the next.

`piighost` keeps one memory per conversation, which holds the detections of each message. The numbers are counted over the whole conversation, not message by message. So "Jean Dupont" keeps `<<PERSON:1>>` each time he comes back. Each conversation has its own placeholders, so `<<PERSON:1>>` can stand for two different people in two conversations.

The memory grows with the conversations, see DEC-19. If the service runs on several servers, they must share the same memory to give the same placeholders.

Implemented in `pipeline/thread.py` and `conversation_memory/`. Rules BR-CONV-01, BR-CONV-02 and BR-CONV-10 follow from it.

### DEC-12: Require the conversation identifier

Each conversation has its own memory, looked up by the conversation's identifier. Without an identifier, two users would share the same memory, and one could read the other's values.

So every de-identification or restoration request must give the identifier of its conversation. A request without an identifier fails, instead of falling back to a shared conversation. A leak between conversations cannot happen by accident. An application that really wants a shared conversation gives the same identifier to all its requests, for example `default`. Only the `piighost anonymize` command, meant for trying out a single text, falls back to `default` when it is given no identifier. The OpenAI and Anthropic proxies of the `piighost-api` server do not fall back to a shared conversation either. A request without an identifier gets an ephemeral conversation there, its own, erased at its end.

Implemented in `pipeline/thread.py` and `integrations/`. Rules BR-CONV-03, BR-AGT-01 and BR-AGT-05 follow from it.

### DEC-13: Neutralize a placeholder typed by the user

A user can write `<<PERSON:2>>` in their own message. Without a safeguard, this text would be restored in the reply, and would show the value of another person in the conversation.

So `piighost` neutralizes any user text shaped like a placeholder. It slips in an invisible character, the zero-width space (U+200B), and the text is no longer recognized as a placeholder. Only the placeholders `piighost` issued can be restored.

The user sees their text again as they typed it. The invisible character stays in it, though, and a copy and paste carries it along.

Implemented in `components/anonymizer/span.py`. Rule BR-MSG-09 follows from it.

### DEC-14: Refuse a placeholder the model made up

A model can write a well-formed placeholder that `piighost` never issued, such as `<<PERSON:7>>` in a conversation with only two people. It does so by mistake, or because a malicious text told it to. That attack is called a prompt injection, the prompt being the text of instructions given to the model.

This placeholder matches no value. Shown to the user, it would mislead them. Sent to a tool (see DEC-16), it would make the agent act on data that does not exist. So by default, the reply or the tool call is refused. Two other settings drop the placeholder, or keep it as is.

Implemented in `integrations/_deidentify.py`. Rules BR-CONV-06, BR-TOOL-07 and BR-STREAM-06 follow from it.

### DEC-15: Leave unmasked a value the assistant mentions first

The model can mention a value the user never wrote. For example, it suggests "Lyon" for a meeting. This value does not come from the user, so it is not part of their data to protect.

By default, a value the assistant mentions first stays unmasked for the whole conversation. It stays unmasked even if the user writes it later, and even if it is on the deny list (see DEC-09), unless that list is set to force masking.

Two other settings exist. The first masks this value like user data. The second does not analyze the assistant's messages at all, which saves the detection.

Implemented in `integrations/langchain/middleware.py` (`EntityCreateByAssistantStrategy`). Rules BR-CONV-04 and BR-AGT-03 follow from it.

## Let an agent act

### DEC-16: Give the real value to tools, and the placeholder to the model

An agent calls tools, for example to send an email. The tool needs the real address. The model must never see it.

By default, `piighost` restores a tool's arguments before the call. The model asks to write to `<<EMAIL:1>>`, and the tool receives the real address. The tool's result is then de-identified before it goes back to the model. An agent can thus act on real data without showing it to the model.

Three other settings exist. One only restores the arguments. Another only de-identifies the result. The last does neither. With the first and the last, the tool's result reaches the model unmasked.

A tool's result goes through the same detection as the messages of the conversation. In the history the agent records, tool calls stay as placeholders. The text of the messages, though, is recorded restored, so with the real values.

Implemented in `integrations/langchain/middleware.py` (`ToolCallStrategy.FULL`). Rules BR-TOOL-01, BR-TOOL-05 and BR-TOOL-10 follow from it.

### DEC-17: Restore the reply while it arrives

A model can send its reply piece by piece, as a stream. A placeholder can then arrive cut in two, `<<PER` in one piece then `SON:1>>` in the next. Restoring each piece on its own would let these cut placeholders through, and the user would see them.

So `piighost` holds back a partial placeholder until it is complete, then restores it. A lone `<` at the end of a piece is held back too, because it can open a placeholder. A `<<` left open for more than 128 characters can no longer be a placeholder. The held text is then shown as is.

If the stream stops in the middle of a placeholder, the held fragment is shown as is, without restoration.

Implemented in `components/placeholder/streaming.py`. Rules BR-STREAM-02 to BR-STREAM-05 follow from it.

## Go to production

### DEC-18: Protect the stored memory

A conversation's memory keeps the detections of each message, so the confidential data in clear text, see DEC-11. A storage leak must not give this data away.

This memory can live in Redis, a database shared between servers, or in a SQL database. `piighost` can then protect what it stores, if both protections are configured together:

- The keys: each message is stored under its fingerprint, computed with a pepper, a secret added before the computation. The fingerprint uses HMAC-SHA256, or Argon2id, which is slower to attack.
- The values: the detections of each message are encrypted with AES-GCM, a standard encryption.

Without these two protections, the memory is stored in clear text, and `piighost` emits a warning. Secrets are read only from the server's environment variables, never from a configuration file. The conversation identifier stays readable, so that a conversation can be erased.

Observation traces follow each step of the pipeline. By default, they hold the text in clear. A setting masks them with placeholders. Without this setting, `piighost` emits a warning as soon as the traces are actually sent.

Implemented in `crypto/`, `conversation_memory/redis_backend.py` and `conversation_memory/sqlalchemy_backend.py`. Rules BR-STO-01, BR-STO-02, BR-STO-03 and BR-STO-08 follow from it.

### DEC-19: Prefer protection over availability

A component can break down, and a memory can grow without limit. A breakdown must never become a leak. So each default setting picks the side that protects:

- An LLM detector or guard rail whose output is unreadable refuses the message, instead of letting it go out without detection or without a check.
- The Claude Code hooks, the points where `piighost` rereads what the Claude Code coding assistant sends, block the action if the `piighost-api` server does not answer.
- The built-in memory, which lives in the application without a database, holds at most 10,000 conversations. It forgets a conversation one day after its last message.

A forgotten conversation loses its placeholders. A placeholder it held is then shown as is, without restoration.

Each protection can be lifted by an explicit setting, for those who prefer availability to protection. The LLM detector and the hooks then let the text through, and the memory has no limit.

Implemented in `components/detector/llm.py`, `components/guard/llm.py`, `integrations/claude_code/runner.py` and `conversation_memory/memory.py`. It meets need DPO-9, and rules BR-STO-04 and BR-CONV-11 follow from it.

### DEC-20: Configure a pipeline from a file and from the catalog

A team must be able to deploy the same pipeline on several servers, without writing code. So a pipeline is described in a TOML or JSON file.

`piighost` ships no regular expression itself. Groups of regular expressions, specific to a country or a profession, come from the catalog, `piighost`'s shared registry. Without a catalog group, no email or IBAN is recognized by regular expression. The catalog also provides complete configurations.

The file names a group by a reference. A reference can point to a frozen version, by its identifier, as in `:2f602547`. This version never changes, so `piighost` keeps a local copy. A reference by name, or `latest` for the newest version, can change. So `piighost` downloads it at each load, because a stale copy would detect fewer values without saying so.

Implemented in `config/` and `catalog.py`.

## The architecture

### DEC-21: Make each step a replaceable port

Each team has its own detectors, its storage and its constraints. So each step of the pipeline is a port, an interface you can replace. You change the detector or the storage without touching the other steps. Most steps also provide a shared skeleton that a new component fills in. Only the detector is required.

The configuration file knows how to build each component, but no component depends on this file. So you can use `piighost` from code, without any configuration. The core of the library holds no rule specific to a language. Lists of French words or of a profession go in the catalog groups.

Implemented in `components/*/base.py`. See [Add or replace a pipeline component](../architecture/ports-and-extension.md).

### DEC-22: Make the steps that wait asynchronous

Model detectors and remote servers take time to answer. So the steps that wait for them are asynchronous, which means they let the application handle other requests while they wait. This is the case for detection, the lists and the guard rail. The steps that only compute, such as grouping or replacement, stay ordinary.

Implemented in `pipeline/base.py`.

The terms are defined in the [Glossary](../glossary.md).
