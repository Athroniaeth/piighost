---
type: reference
title: Design decisions
description: The decisions that built the PIIGhost de-identification system, in the order they arose, each with its identifier, its context, its reason, its consequences and the place in the code where it lives.
tags: [decisions, conventions, placeholder, detection, conversation, security]
generated: { by: "claude-code", at: "2026-10-03T18:00:00.000Z" }
---

# Design decisions

## In short

The de-identification system was built in steps, and each new need called for a decision. To replace a confidential value with a placeholder, it first had to be found in the text, at a precise position. For the model to still understand the text, the placeholder had to say what type of data it stands for. To tell two people apart, it needed an identifier, and so a way to group the detections of one person. For the user to read their real data, the mapping between each placeholder and its value had to be kept. Then came the conversation, the tools of an agent, streaming and production.

This page tells these decisions in the order they arose. Each one carries a `DEC-NN` identifier and gives its context, what was decided, why, its consequences and the place in the code where it lives. It also cites the business rules that follow from it. The technical documentation describes the components that apply these decisions, in [Pipeline design](../../../docs/en/conception.md). These decisions bind the rest of the library, so changing one calls for a discussion first.

## De-identify a text

**DEC-01. Replace each confidential value with a placeholder.**

- **Context**: a text must go to an AI model without its confidential data, but the model must still be able to answer it.
- **Decision**: each value is replaced with a placeholder, a replacement text. It is neither deleted nor scrambled.
- **Why**: a sentence stripped of its names loses its meaning. With a placeholder in its place, the sentence stays readable, and the model can answer by reusing the placeholder.
- **Consequences**: the rest of the system exists to produce these placeholders, keep them consistent and turn them back into values.

**DEC-02. Find each value and its exact position.**

- **Context**: to replace a value, you need to know where it starts and where it ends in the text.
- **Decision**: a detector returns spans, meaning a start and end position, with a type and a confidence. Two families complement each other. Regular expressions recognize fixed formats (email, IBAN, phone number). Named entity recognition (NER) models recognize free text (name, place). An LLM detector names values without positions, and PIIGhost searches for them in the text itself.
- **Why**: no family covers everything. Several detectors can run together.
- **Consequences**: a value that no detector sees goes out in clear text. A value invented by an LLM, absent from the text, is ignored. A value is masked on its shape alone, without a checksum, so that a value damaged by character recognition is still detected. Regular expressions are in ASCII, and any Unicode space counts as an ordinary space.
- **In the code**: `components/detector/`, `text/normalization.py`. Rules BR-MSG-06, BR-MSG-07, BR-MSG-10.

**DEC-03. Wrap each placeholder in `<<` and `>>`.**

- **Context**: a notation was needed to write a placeholder in the text.
- **Decision**: a placeholder is wrapped in two doubled angle brackets, as in `<<PERSON:1>>`.
- **Why**: this sequence is rare in ordinary text, so a regular expression finds a placeholder easily. It also tells the model that it is reading masked data.
- **Consequences**: a text that already contains this sequence needs a precaution, see DEC-13. A label starts with a letter or `_`, then contains letters, digits, `_`, spaces or hyphens.
- **In the code**: `components/placeholder/streaming.py` (`DEFAULT_PREFIX`, `DEFAULT_SUFFIX`, `LABEL_INNER`).

**DEC-04. Say in the placeholder what type of data it stands for.**

- **Context**: a model that reads `<<1>>` does not know whether it is a person, an address or an email, and answers poorly.
- **Decision**: the placeholder carries the type of the data, its label. The label comes from the NER model, or from the name given to the pattern in the regular expression detector.
- **Why**: with `<<PERSON:1>>`, the model knows it is talking to a person, and can write "Hello `<<PERSON:1>>`".
- **Consequences**: a detector can map the labels of its model to the ones you want to see in the placeholders.
- **In the code**: `components/detector/ner/base.py` (label mapping).

**DEC-05. Give each individual their own identifier.**

- **Context**: two people in the same text must not become the same placeholder, or the model confuses them.
- **Decision**: the placeholder adds an identifier to the type. By default, it is a number counted per type, starting at 1, in order of appearance (`<<PERSON:1>>`, `<<PERSON:2>>`). Another form uses the SHA-256 hash of "type:rank", never of the value.
- **Why**: the number is readable by the model. The hash hides no secret, and nothing can be inferred from it about the value.
- **Consequences**: you need to know which detections refer to the same individual, see DEC-06.
- **In the code**: `components/placeholder/label_counter.py`, `components/placeholder/label_hash.py`. Rule BR-MSG-01.

**DEC-06. Group the detections of one individual.**

- **Context**: the same person appears several times in a text, sometimes written differently. All their occurrences must get the same placeholder.
- **Decision**: detections that share the same value and the same type form an entity, which gets a single placeholder. Two values that differ only in their spaces or their case count as the same. As an option, a search catches the occurrences a detector missed, and an approximate match joins close spellings.
- **Why**: without this grouping, "Jean Dupont" and "jean dupont" would get two placeholders, and the model would think it is talking about two people.
- **Consequences**: on restoration, a value written in several ways comes back in the first spelling encountered.
- **In the code**: `components/linker/`, `components/expander/`, `components/entity_resolver/`, `text/normalization.py` (`value_key`). Rules BR-MSG-02, BR-MSG-03, BR-MSG-12.

**DEC-07. Keep only one span when two detections overlap.**

- **Context**: two detectors can find spans that overlap, for example "Jean" and "Jean Dupont".
- **Decision**: only one span is kept. By default, the surest detection wins, and on a tie, the first declared detector. Another setting keeps the union of the spans.
- **Why**: replacement assumes disjoint spans. Two overlapping replacements would damage the text.
- **Consequences**: this stage cannot be turned off.
- **In the code**: `components/overlap_resolver/`. Rule BR-MSG-05.

**DEC-08. Keep the mapping to restore the real values.**

- **Context**: the user must read the answer with their real data, not with placeholders.
- **Decision**: PIIGhost keeps, for each placeholder, the value it replaces. In the model's answer, each known placeholder is replaced with its value, from the longest placeholder to the shortest.
- **Why**: without a mapping, no restoration is possible. The longest-to-shortest order prevents `<<PERSON:1>>` from replacing the start of `<<PERSON:10>>`.
- **Consequences**: under the GDPR, this is pseudonymization, not anonymization. The mapping is personal data to protect, see DEC-18.
- **In the code**: `components/anonymizer/base.py`. Rule BR-CONV-05.

**DEC-09. Let people correct the detection.**

- **Context**: a detector misses values and masks others by mistake.
- **Decision**: two lists apply to every detection. The whitelist masks a value even if the detector missed it. The blacklist leaves a value in clear text even if the detector found it. A person can also correct the values of a message by hand.
- **Why**: a server or a team knows its own sensitive values, and its false positives.
- **Consequences**: a manual correction applies only to its message, and the two lists still apply on top of it.
- **In the code**: `components/override/`, `pipeline/thread.py`. Rules BR-LIST-01, BR-LIST-02, BR-CONV-07.

**DEC-10. Reread the protected text before sending it, as an option.**

- **Context**: a value missed by every detector goes out in clear text.
- **Decision**: a final check, the guard rail, can reread the already protected text. If it finds confidential data there, the sending is blocked.
- **Why**: it is a second line of defense, with a different tool than the detectors.
- **Consequences**: the guard rail reports a value, but it does not always locate it. It slows down the sending.
- **In the code**: `components/guard/`. Rules BR-MSG-10, BR-MSG-11.

## Keep a conversation

**DEC-11. Keep the same placeholder for the whole conversation.**

- **Context**: a conversation has several messages. If "Jean Dupont" becomes `<<PERSON:1>>` in the first message and `<<PERSON:2>>` in the third, the model thinks it is talking about two people.
- **Decision**: a memory keeps the detections of each message of the conversation. Placeholders are assigned over all the messages, and a value gets its placeholder back each time it reappears. Each conversation has its own placeholders.
- **Why**: running the pipeline again message by message is not enough, because the numbers would change from one message to the next.
- **Consequences**: the memory grows with the conversations, see DEC-19. Several instances of the service must share the same memory to give the same placeholders.
- **In the code**: `pipeline/thread.py`, `conversation_memory/`. Rules BR-CONV-01, BR-CONV-02, BR-CONV-10.

**DEC-12. Require the conversation identifier.**

- **Context**: without an identifier, two users would share the same memory, and one could read the values of the other.
- **Decision**: each call names its conversation. A call without an identifier fails, instead of falling back on a shared conversation.
- **Why**: a leak between conversations must be impossible by accident.
- **Consequences**: an application that really wants a shared conversation must name it itself.
- **In the code**: `pipeline/thread.py`, `integrations/`. Rules BR-CONV-03, BR-AGT-01, BR-AGT-05.

**DEC-13. Neutralize a placeholder typed by the user.**

- **Context**: a user can write `<<PERSON:2>>` themselves to make the value of another person appear in the answer.
- **Decision**: a user text that has the shape of a placeholder is neutralized by an invisible character (U+200B), and is no longer recognized as a placeholder.
- **Why**: only the placeholders issued by PIIGhost must be restorable.
- **Consequences**: the invisible character stays in the restored text.
- **In the code**: `components/anonymizer/span.py`. Rule BR-MSG-09.

**DEC-14. Refuse a placeholder invented by the model.**

- **Context**: a model can write a placeholder in the right format that PIIGhost never issued, by mistake or under an injection.
- **Decision**: by default, the answer or the tool call is refused. Two other settings remove the placeholder or keep it as is.
- **Why**: displaying an invented placeholder, or sending it to a tool, would act on data that does not exist.
- **In the code**: `integrations/_deidentify.py`. Rules BR-CONV-06, BR-TOOL-07, BR-STREAM-06.

**DEC-15. Leave in clear text a value that the assistant mentions first.**

- **Context**: the model can introduce a value itself, a city name for example, that the user never wrote.
- **Decision**: by default, a value first mentioned by the assistant stays in clear text for the whole conversation. Two other settings mask it or ignore it.
- **Why**: this value does not come from the user, so it is not part of their data to protect.
- **In the code**: `integrations/langchain/middleware.py` (`EntityCreateByAssistantStrategy`). Rules BR-CONV-04, BR-AGT-03.

## Let an agent act

**DEC-16. Give the real value to the tools, and the placeholder to the model.**

- **Context**: an agent calls tools, for example to send an email. The tool needs the real address, and the model must never see it.
- **Decision**: by default, the arguments of a tool are restored before the call, and its result is de-identified before it goes back to the model. Three other settings limit this processing.
- **Why**: this is what lets an agent act on real data without exposing it to the model.
- **Consequences**: the result of a tool goes through the full detection of the conversation. The agent history keeps the calls with their placeholders.
- **In the code**: `integrations/langchain/middleware.py` (`ToolCallStrategy.FULL`). Rules BR-TOOL-01, BR-TOOL-05, BR-TOOL-10.

**DEC-17. Restore the answer while it arrives.**

- **Context**: a model can send its answer piece by piece. A placeholder can then arrive cut in two, `<<PER` then `SON:1>>`.
- **Decision**: a decoder holds back a started placeholder until it is complete, then restores it. A lone `<` at the end of a piece is held back too. Past 128 characters without a closing sequence, the held text is released as is.
- **Why**: restoring each piece separately would let cut placeholders through.
- **Consequences**: a stream stopped in the middle of a placeholder shows the held fragment, without restoration.
- **In the code**: `components/placeholder/streaming.py`. Rules BR-STREAM-02 to BR-STREAM-05.

## Go to production

**DEC-18. Protect the stored mapping.**

- **Context**: the mapping between placeholders and values holds the confidential data in clear text, see DEC-08.
- **Decision**: with Redis, the keys go through HMAC then Argon2id with a pepper, and the values are encrypted with AES-GCM. The secrets are read only from the environment, never from a configuration file. Observation traces can be masked.
- **Why**: a storage leak must not hand over the data.
- **Consequences**: the conversation identifier stays readable, so that a conversation can be erased. A storage without encryption emits a warning.
- **In the code**: `crypto/`, `conversation_memory/redis_backend.py`. Rules BR-STO-01, BR-STO-02, BR-STO-03, BR-STO-08.

**DEC-19. Fail on the side that protects.**

- **Context**: a component can break down, and a memory can grow without end.
- **Decision**: each default setting picks the side that protects. An LLM detector whose output is unreadable refuses the message. The Claude Code hooks block if the server does not answer. The in-process memory keeps at most 10,000 conversations, and forgets a conversation after one day without activity.
- **Why**: a failure must never become a leak.
- **Consequences**: an explicit setting lets data through, for those who prefer availability to protection.
- **In the code**: `components/detector/llm.py`, `integrations/claude_code/runner.py`, `conversation_memory/memory.py`. Need DPO-9, rules BR-STO-04, BR-CONV-11.

**DEC-20. Configure a pipeline through a file and through the hub.**

- **Context**: a team must deploy the same pipeline on several servers, without writing code.
- **Decision**: a pipeline is described in a TOML or JSON file. Pattern groups come from the hub, through a reference. A reference pinned to a commit is cached. A tag or `latest` is read again every time.
- **Why**: a pinned reference never changes, while an outdated version would detect less without saying so.
- **In the code**: `config/`, `hub.py`.

## The architecture

**DEC-21. Make each stage a replaceable port.**

- **Context**: each team has its own detectors, its storage and its constraints.
- **Decision**: each stage of the pipeline has an interface, and most have a base template. Only the detector is required. The configuration knows the core of the library, never the reverse.
- **Why**: you replace a stage without touching the others.
- **Consequences**: the core holds no rule specific to a language. Lists of French words or domain terms go in the hub groups.
- **In the code**: `components/*/base.py`. See [Add or replace a pipeline component](../architecture/ports-and-extension.md).

**DEC-22. Make everything asynchronous.**

- **Context**: model detectors and remote servers answer with a delay.
- **Decision**: each stage of the pipeline is asynchronous.
- **Why**: the pipeline waits for a model or a server without blocking the rest of the application.
- **In the code**: `pipeline/base.py`.

The terms are defined in the [Glossary](../glossary.md).
