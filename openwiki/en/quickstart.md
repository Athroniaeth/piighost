---
type: guide
title: Where to start
description: Entry point of the piighost domain documentation, which routes by need (understand a protection rule or change the code), summarizes the path of a message and lists the pitfalls that cut across several processes.
tags: [quickstart, overview, routing, pii, de-identification]
sources:
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-edd617907d8703b014c2a6c7
    resource: repo://src/piighost/cli/__init__.py
  - id: openwiki-source-9703fc61b3e278e6ef8403ff
    resource: repo://src/piighost/integrations/claude_code/hooks.py
  - id: openwiki-source-85881a85af445f438a8d7d5f
    resource: repo://src/piighost/integrations/langchain/middleware.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Where to start

## In short

`piighost` hides the confidential data of a text before an AI model reads it, then puts the real values back in the reply. It is a Python library, with no graphical interface. It plugs into LangChain, Pydantic AI, LlamaIndex or Claude Code, or is used remotely through the `piighost-api` server. It is configured with a TOML or JSON file and the `piighost` command. The legal and technical reasons to de-identify are explained in [Why de-identify?](../../docs/en/why-anonymize.md).

**The path of a message:**

1. The user writes a message with their real data, for example their name and email.
2. `piighost` finds the sensitive values, for example names, emails, phone numbers or secrets.
3. It replaces them with placeholders. A placeholder is a stand-in text, such as `<<PERSON:1>>`, which stays the same over the whole conversation.
4. The model replies with these placeholders.
5. `piighost` puts the real values back in the displayed reply.

**What this domain documentation is.** It describes what `piighost` must do. How to use it is in the technical documentation. It defines:

- the needs of each profile, that is the compliance officer, the developer, the operator and the application user.
- the rules each process follows, each with its identifier, such as `BR-MSG-05`.
- the acceptance tests that check each need.
- where in the code each rule applies.

**Its goal.** De-identifying a conversation with an LLM is still a new practice, and its rules are written down nowhere. This documentation writes them down, so that they can be discussed, checked and improved together. Anyone can propose a need or challenge a rule.

**How to read it.** Start with [Needs by profile](needs-by-profile.md) to find what concerns your profile. When they disagree, the code and the tests are right. The terms are defined in the [glossary](glossary.md).

## I want to understand…

| Business need | Page to read |
|---|---|
| What each profile expects from `piighost`, and how to check it | [Needs by profile](needs-by-profile.md) |
| What the model really sees of a message | [Protect a message before it is sent to the model](processes/protect-a-message.md) |
| Why a name stayed in clear text, or half of it | [Protect a message before it is sent to the model](processes/protect-a-message.md#frequently-asked-questions) |
| How a person keeps the same placeholder from one message to the next | [Follow a conversation and restore the reply](processes/follow-a-conversation.md) |
| What happens when you correct a message by hand | [Follow a conversation and restore the reply](processes/follow-a-conversation.md#correct-a-detection) |
| How to erase a conversation (right to erasure) | [Follow a conversation and restore the reply](processes/follow-a-conversation.md) |
| Keep the company name in clear text, or always mask an internal code | [Impose a deny list and an allow list](processes/impose-a-deny-list-and-an-allow-list.md) |
| What a tool of the agent receives, and what the model reads of its result | [Let a tool act on the real values](processes/let-a-tool-act.md) |
| Why a placeholder appears while a reply is displayed | [Show a streamed reply](processes/show-a-streamed-reply.md) |
| What each actor sees depending on the tool used (LangChain, Claude Code…) | [Plug the protection into an agent and its tools](integrations/agents-and-tools.md) |
| What happens when a model answers badly | [Needs by profile, watch points](needs-by-profile.md#watch-points) |
| Where the conversation data is stored, and whether it is encrypted | [Store conversations and protect traces](operations/storage-and-encryption.md) |
| Why `piighost` works this way, decision by decision | [Design decisions](reference/decisions.md) |
| The meaning of a term or an acronym | [Glossary](glossary.md) |
| What is decided and remains to be done | [Open points](reference/open-points.md) |

## Why piighost works this way

Each rule follows from a design decision. The [Design decisions](reference/decisions.md) page explains them in the order they arose, with an example for each.

- **De-identify a text**:
    - DEC-01: Replace each confidential value with a placeholder.
    - DEC-02: Find each value and its exact position.
    - DEC-03: Wrap each placeholder in `<<` and `>>`.
    - DEC-04: Say in the placeholder what type of data it stands for.
    - DEC-05: Give each entity its own identifier.
    - DEC-06: Group the detections of the same entity.
    - DEC-07: Keep a single span when two detections overlap.
    - DEC-08: Keep the mapping to restore the real values.
    - DEC-09: Let people correct the detection.
    - DEC-10: Reread the protected text before sending, as an option.
- **Hold a conversation**:
    - DEC-11: Keep the same placeholder for the whole conversation.
    - DEC-12: Require the conversation identifier.
    - DEC-13: Neutralize a placeholder typed by the user.
    - DEC-14: Refuse a placeholder the model made up.
    - DEC-15: Leave unmasked a value the assistant mentions first.
- **Let an agent act**:
    - DEC-16: Give the real value to tools, and the placeholder to the model.
    - DEC-17: Restore the reply while it arrives.
- **Go to production**:
    - DEC-18: Protect the stored memory.
    - DEC-19: Prefer protection over availability.
    - DEC-20: Configure a pipeline from a file and from the catalog.
- **The architecture**:
    - DEC-21: Make each step a replaceable port.
    - DEC-22: Make the steps that wait asynchronous.

## Change the code

To change the code, the technical documentation says which pages to read and which files to open. See [Change piighost's code](../../docs/en/community/changing-the-code.md).

## The domain documentation groups

- **Needs**:
    - [Needs by profile](needs-by-profile.md)
- **Processes**:
    - [Protect a message](processes/protect-a-message.md)
    - [Follow a conversation](processes/follow-a-conversation.md)
    - [Impose a deny list and an allow list](processes/impose-a-deny-list-and-an-allow-list.md)
    - [Let a tool act](processes/let-a-tool-act.md)
    - [Show a streamed reply](processes/show-a-streamed-reply.md)
- **Integrations**:
    - [Plug the protection into an agent and its tools](integrations/agents-and-tools.md)
- **Operations**:
    - [Configure a pipeline by file, catalog and command line](operations/configuration-and-catalog.md)
    - [Store conversations and protect traces](operations/storage-and-encryption.md)
- **Architecture**:
    - [Add or replace a pipeline component](architecture/ports-and-extension.md)
- **Tests**:
    - [Run and write tests](tests/run-and-write-tests.md)
    - [Acceptance tests](tests/acceptance-tests.md)
- **Reference**:
    - [Glossary](glossary.md)
    - [Design decisions](reference/decisions.md)
    - [Open points](reference/open-points.md)

## Cross-cutting watch points

1. **The conversation identifier decides how placeholders are shared.** A call without an identifier is refused, by LangChain, the Claude Code hooks and the server. An application that names `default` shares its placeholders between all its users. Only the `piighost anonymize` command falls back to `default`, to try out a single text. See [Follow a conversation](processes/follow-a-conversation.md#rules-to-know).
2. **Correcting an old message can renumber the placeholders**, and a reply of the model can then be restored with the name of another person. See [Follow a conversation](processes/follow-a-conversation.md#rules-to-know).
3. **Real values stay stored outside the model.** The model only sees placeholders, but two places keep the real values. `piighost`'s memory keeps them in clear text if its storage is not encrypted. The history the agent records, with LangGraph or Pydantic AI, keeps the text of the messages restored. Some texts do not go through `piighost` either. This is the case of the result of a Claude Code tool that `piighost` does not read, such as Grep. It is also the case of the result of a tool whose setting sends it to the model in clear text, see [Let a tool act](processes/let-a-tool-act.md). Encrypt the memory, and protect the agent's history as personal data. See [Store conversations](operations/storage-and-encryption.md) and [Plug the protection into an agent](integrations/agents-and-tools.md#pitfalls).
4. **The technical traces carry the text in clear by default.** Configure a trace redactor before you send them to a third-party service. See [Store conversations and protect traces](operations/storage-and-encryption.md#redact-the-traces).
5. **Erasing a conversation does not clear the other server instances right away.** The storage and the instance that receives the request are cleared. The other instances keep a copy of the values in their placeholder cache, until the lifetime of that cache ends. With no lifetime set, the copy stays until the full cache evicts it. See [Store conversations](operations/storage-and-encryption.md#rules-to-know).
6. **An LLM detector or guard rail refuses the message when it cannot read the answer of its own LLM.** The message does not leave, and the application gets an error. The `fail_open` setting lets the message leave without that detection or without that check. See the [watch points](needs-by-profile.md#watch-points) of [Needs by profile](needs-by-profile.md) and DEC-19.
