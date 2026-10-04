---
type: guide
title: Needs by profile
description: The needs of the compliance officer, the developer, the operator and the application user, each with its observable criteria, the domain documentation page that delivers it, and the watch points when a model answers badly.
tags: [personas, user-stories, dpo, developer, operator, end-user, vigilance]
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Needs by profile

## In short

The domain documentation lists four profiles that need de-identification, each for a different reason:

- The compliance officer (DPO): they want no confidential data to leave in clear text.
- The developer: they want to integrate `piighost` without rewriting their application.
- The operator: they want to run it in production.
- The application user: they must never notice it.

Each need carries an identifier in English, the same in every language, of the form `DPO-n`, `DEV-n`, `OPS-n` or `USER-n`. It gives criteria you can observe, then points to the domain documentation page that describes it in detail, with its scenario and its rules. The acceptance tests of each need are listed in [Acceptance tests](tests/acceptance-tests.md).

The watch points, at the end of the page, list the unexpected answers of a model and the need that covers them. The terms are defined in the [glossary](glossary.md).

---

## Compliance officer (DPO)

DPO-1: As a DPO, I want no personal data and no secret to leave in clear text toward the LLM, so that I stay compliant with the GDPR and do not expose access credentials.

- The message "Write to Jean Dupont, jean.dupont@exemple.fr" leaves toward the LLM as "Write to `<<PERSON:1>>`, `<<EMAIL:1>>`".
- An API key pasted into a message leaves as a placeholder, as soon as a group of secrets is configured.
- See [Protect a message](processes/protect-a-message.md) and the [watch points](#watch-points). Tests: [AT-DPO-1-…](tests/acceptance-tests.md).

DPO-2: As a DPO, I want to choose the types of protected data, so that I adapt the protection to my activity.

- A configuration that pulls the French group from the hub masks an IBAN and a social security number.
- A pattern specific to the company, a case number for example, is added in one line.
- See [Configure a pipeline](operations/configuration-and-hub.md) and [Protect a message](processes/protect-a-message.md). Tests: [AT-DPO-2-…](tests/acceptance-tests.md).

DPO-3: As a DPO, I want to force the protection of a value, or leave a public term in clear text, without waiting for the detector, so that I impose the company policy.

- A value on the deny list of the configuration (`deny_list` in the section `[override]`, in the application or in `piighost-api`) is masked even if no detector sees it.
- A term on the allow list (`allow_list`) of the same section stays in clear text even when a detector flags it.
- See [Impose a deny list and an allow list](processes/impose-a-whitelist-and-blacklist.md). Tests: [AT-DPO-3-…](tests/acceptance-tests.md).

DPO-4: As a DPO, I want to refuse a text that still contains a piece of data, so that a missed detection does not leave.

- A de-identified text that keeps an e-mail address in clear text is refused instead of being sent.
- See [Protect a message](processes/protect-a-message.md). Tests: [AT-DPO-4-…](tests/acceptance-tests.md).

DPO-5: As a DPO, I want to know where the real values are kept and that they are encrypted at rest, so that I control the pseudonymization.

- With an encrypted Redis memory, the database contains neither "Jean Dupont" nor the message in clear text.
- When encryption is configured but its secrets are missing from the environment, the pipeline refuses to start rather than store in clear text.
- See [Store conversations and protect traces](operations/storage-and-encryption.md). Tests: [AT-DPO-5-…](tests/acceptance-tests.md).

DPO-6: As a DPO, I want to erase a conversation on request, so that I answer the right to erasure.

- After a conversation is erased, restoring its placeholder `<<PERSON:1>>` returns it as is, without "Jean Dupont".
- The API server exposes this erasure on a route.
- See [Follow a conversation](processes/follow-a-conversation.md). Tests: [AT-DPO-6-…](tests/acceptance-tests.md).

DPO-7: As a DPO, I want to observe the pipeline without the traces containing the data, so that I prove the protection.

- A trace shows a placeholder, `<<REDACT>>` for example, where the message contained "Jean Dupont".
- See [Store conversations and protect traces](operations/storage-and-encryption.md). Tests: [AT-DPO-7-…](tests/acceptance-tests.md).

DPO-8: As a DPO, I want to document the impact assessment, so that I justify the processing.

- See [How to document piighost in a DPIA](../../docs/en/dpia.md) and the [Compliance](../../docs/en/compliance.md) page of the technical guide. Tests: [AT-DPO-8-…](tests/acceptance-tests.md).

DPO-9: As a DPO, I want a failed detector to block the message rather than let it through, so that a failure does not become a leak.

- When the model of an LLM detector returns an unreadable output, the message must be refused with an error instead of leaving without detection.
- An explicit setting must let the message through, for whoever prefers availability to protection.
- The Claude Code hooks must likewise block a prompt or a tool call when the server does not answer, and replace a tool output with a notice.
- See the [watch points](#watch-points) and [Open points](reference/open-points.md). Tests: [AT-DPO-9-…](tests/acceptance-tests.md).

DPO-10: As a DPO, I want to choose in which form human corrections are kept, so that their storage does not become a copy of the data.

- A correction exported to an annotation tool, Langfuse for example, is kept in the chosen form. The possible forms are placeholders instead of the values, values in clear text, or input and output fully masked.
- The developer sets this form, the DPO decides it.
- Without an explicit choice, the correction is kept as placeholders. The export then contains no real value.

**Known limit.** The choice of form does not exist in the code yet.

---

## Developer

DEV-1: As a developer, I want to protect the LLM calls of my agent without rewriting its logic, so that I add the protection to an existing project.

- The LangChain middleware is added to the agent in one line.
- The OpenAI-compatible proxy only requires a change of base URL.
- See [Plug the protection into an agent](integrations/agents-and-tools.md). Tests: [AT-DEV-1-…](tests/acceptance-tests.md).

DEV-2: As a developer, I want the reply to be restored automatically, so that I write nothing to put the real values back.

- "Hello `<<PERSON:1>>`", returned by the LLM, reaches the application as "Hello Jean Dupont".
- See [Follow a conversation](processes/follow-a-conversation.md). Tests: [AT-DEV-2-…](tests/acceptance-tests.md).

DEV-3: As a developer, I want a value to keep the same placeholder over the whole conversation, so that the LLM follows the thread.

- "jean.dupont@exemple.fr" is still `<<EMAIL:1>>` three messages later.
- A placeholder from one conversation is not restored in another, even if both issued `<<PERSON:1>>`.
- See [Follow a conversation](processes/follow-a-conversation.md). Tests: [AT-DEV-3-…](tests/acceptance-tests.md).

DEV-4: As a developer, I want my tools to receive the real values while the LLM sees only placeholders, so that the actions run.

- A tool called with `<<EMAIL:1>>` receives "jean.dupont@exemple.fr", and its result goes back to placeholders before the LLM.
- See [Let a tool act](processes/let-a-tool-act.md). Tests: [AT-DEV-4-…](tests/acceptance-tests.md).

DEV-5: As a developer, I want to add my own detectors or values, so that I cover an identifier specific to my business.

- A pattern written in the configuration masks an order number "CMD-2024-0042".
- A custom detector plugs into the pipeline without touching the library.
- See [Add or replace a component](architecture/ports-and-extension.md). Tests: [AT-DEV-5-…](tests/acceptance-tests.md).

DEV-6: As a developer, I want to describe the pipeline in a file and validate it in CI, so that I have it reviewed without reading code.

- Validation succeeds on a correct configuration and fails, naming the faulty key, on a typo.
- See [Configure a pipeline](operations/configuration-and-hub.md). Tests: [AT-DEV-6-…](tests/acceptance-tests.md).

DEV-7: As a developer, I want to test my integration without downloading a model, so that I have fast and reproducible tests.

- A list of known values is de-identified without network or model.
- See [Run and write tests](tests/run-and-write-tests.md). Tests: [AT-DEV-7-…](tests/acceptance-tests.md).

DEV-8: As a developer, I want to decide what to do with a placeholder the LLM invented, so that it does not reach the user as is.

- A `<<PERSON:9>>` never issued is refused, removed or kept, depending on the chosen strategy.
- See [Follow a conversation](processes/follow-a-conversation.md) and [Let a tool act](processes/let-a-tool-act.md). Tests: [AT-DEV-8-…](tests/acceptance-tests.md).

DEV-9: As a developer, I want to restore a streamed reply chunk by chunk, so that I display it without waiting for the end.

- "`<<PER`" then "`SON:1>>`" in two chunks give "Jean Dupont" only once.
- See [Show a streamed reply](processes/show-a-streamed-reply.md). Tests: [AT-DEV-9-…](tests/acceptance-tests.md).

DEV-10: As a developer, I want each conversation to be named explicitly, so that two users never share their placeholders by accident.

- A call without a conversation identifier is refused, by the LangChain middleware, by the Claude Code hooks and by the API server.
- An application whose conversations do not need to be separated passes `"default"`.
- See [Follow a conversation](processes/follow-a-conversation.md) and [Plug the protection into an agent](integrations/agents-and-tools.md). Tests: [AT-DEV-10-…](tests/acceptance-tests.md).

DEV-11: As a developer, I want to choose the fate of a value that the assistant introduces itself, so that I decide whether the LLM keeps what it knows about it.

- By default, "Napoléon", cited first by the assistant, stays in clear text, even when the user repeats it afterwards.
- One setting turns this value into a placeholder, another does not analyze the assistant messages at all.
- See [Follow a conversation](processes/follow-a-conversation.md). Tests: [AT-DEV-11-…](tests/acceptance-tests.md).

---

## Operator

OPS-1: As an operator, I want to deploy a shared de-identification API, so that several applications use a single pipeline and a single model.

- The server starts on a configuration from the hub and answers de-identification requests.
- See the tutorial [Deploy a de-identification API](../../docs/en/getting-started/api-server.md) and [Configure a pipeline](operations/configuration-and-hub.md). Tests: [AT-OPS-1-…](tests/acceptance-tests.md).

OPS-2: As an operator, I want the memory to survive restarts and be shared between instances, so that a conversation does not lose its placeholders.

- Two instances return the same `<<PERSON:1>>` for "Jean Dupont" in the same conversation.
- See [Store conversations and protect traces](operations/storage-and-encryption.md), [Follow a conversation](processes/follow-a-conversation.md) and, for several instances behind a load balancer, [Multi-instance deployment](../../docs/en/multi-instance.md). Tests: [AT-OPS-2-…](tests/acceptance-tests.md).

OPS-3: As an operator, I want to provide the secrets through the environment, so that no key is written in a file.

- When encryption is configured but its secrets are missing, startup fails with a clear message.
- A Redis memory declared without encryption starts, but in clear text, with a security warning.
- See [Store conversations and protect traces](operations/storage-and-encryption.md). Tests: [AT-OPS-3-…](tests/acceptance-tests.md).

OPS-4: As an operator, I want to protect the API with keys, a maximum request size and a rate limit, so that it is neither open nor abused.

- Without a configured key, the server refuses to start, unless anonymous mode is requested explicitly.
- A request that is too large or too frequent is refused.
- See the [server CLI reference](../../docs/en/reference/api-cli.md) and the [API endpoints reference](../../docs/en/reference/api-endpoints.md). Tests: [AT-OPS-4-…](tests/acceptance-tests.md).

OPS-5: As an operator, I want to process a long document without the model truncating its end, so that no value at the end of the text leaves in clear text.

- A value placed beyond the model window is detected when the text is split.
- See [Limitations](../../docs/en/limitations.md) and [Add or replace a component](architecture/ports-and-extension.md). Tests: [AT-OPS-5-…](tests/acceptance-tests.md).

OPS-6: As an operator, I want to load a reviewed configuration from the hub by its reference, so that I do not maintain a local copy.

- A reference pinned to a commit is downloaded at the first startup, then read from the cache.
- A reference without a commit, which can change, is read again at each load and never cached.
- The hub is reached only over HTTP or HTTPS, and a hub configuration that embeds a model is refused.
- See [Configure a pipeline](operations/configuration-and-hub.md). Tests: [AT-OPS-6-…](tests/acceptance-tests.md).

**Known limit.** For now the hub serves only pattern groups. An NER model recognizes some labels better than others. Splitting the labels between patterns and model requires a configuration format that the hub does not have yet.

OPS-7: As an operator, I want the in-process memory to be bounded by default, so that a server that runs for weeks does not keep every value it has seen.

- Without a setting, the memory keeps at most 10,000 conversations, and keeps each one for one day after its last message.
- Both bounds are set in the configuration.
- See [Store conversations and protect traces](operations/storage-and-encryption.md) and [Follow a conversation](processes/follow-a-conversation.md). Tests: [AT-OPS-7-…](tests/acceptance-tests.md).

---

## Application user

This profile never handles `piighost`. They use the application that a developer built with it, and their needs state what this application must guarantee them.

USER-1: As a user, I want to read the reply with my real information, so that I never see a placeholder.

- The user reads "Hello Jean Dupont", never "Hello `<<PERSON:1>>`".
- See [Follow a conversation](processes/follow-a-conversation.md) and [Plug the protection into an agent](integrations/agents-and-tools.md). Tests: [AT-USER-1-…](tests/acceptance-tests.md).

**Known limit.** With the Claude Code hooks, the reply displayed in Claude Code keeps its placeholders, because no hook can rewrite this text. The Anthropic-compatible proxy, for its part, restores the reply.

USER-2: As a user, I want the conversation to stay consistent from end to end, so that the assistant does not mix up two people.

- Two people cited each keep their placeholder from one message to the next, and the reply names them correctly.
- See [Follow a conversation](processes/follow-a-conversation.md). Tests: [AT-USER-2-…](tests/acceptance-tests.md).

USER-3: As a user, I want the actions of the assistant to use my real data, so that the e-mail goes to the right address.

- The sending tool receives "jean.dupont@exemple.fr", not `<<EMAIL:1>>`.
- See [Let a tool act](processes/let-a-tool-act.md). Tests: [AT-USER-3-…](tests/acceptance-tests.md).

**Known limit.** The OpenAI-compatible proxy does not restore the arguments of a tool call when the reply is streamed. See [De-identify an OpenAI client with the proxy](../../docs/en/examples/openai-proxy.md).

USER-4: As a user, I want to see the reply appear as it comes, without any placeholder fragment, so that I read it normally.

- A fragment like "`<<PER`" does not appear during the stream. Only a stream cut in the middle of a placeholder returns this fragment at the end, without any real value.
- See [Show a streamed reply](processes/show-a-streamed-reply.md). Tests: [AT-USER-4-…](tests/acceptance-tests.md).

USER-5: As a user, I want public terms to stay readable, so that the reply keeps its meaning.

- A city name put on the allow list of the configuration stays in clear text, and a meeting date is not masked by a group of generic patterns.
- See [Impose a deny list and an allow list](processes/impose-a-whitelist-and-blacklist.md). Tests: [AT-USER-5-…](tests/acceptance-tests.md).

USER-6: As a user, I want to correct a detection, add a missed name or make readable a term masked by mistake, so that the assistant receives the right text.

- After correction, the added name leaves as a placeholder and the removed term leaves in clear text, in the corrected message.
- The deny list and the allow list of the configuration have the last word, so a term on the deny list stays masked even if the user removes it.
- See [Follow a conversation](processes/follow-a-conversation.md) and [Impose a deny list and an allow list](processes/impose-a-whitelist-and-blacklist.md). Tests: [AT-USER-6-…](tests/acceptance-tests.md).

---

## Watch points

An LLM can answer badly, whether it serves as a detector, a guard rail or the conversation model, the model that answers the user. These cases define what `piighost` must do, and the need that carries it.

| Situation | What `piighost` does | Need |
|---|---|---|
| The detector LLM returns an unreadable output, broken JSON or a missing field | The message is refused with an error, unless fail open is requested | DPO-9 |
| The guard rail LLM returns an unreadable output | The text is refused with an error, unless fail open is requested | DPO-9 |
| The detector LLM cites a value absent from the text | The value is found nowhere in the text and is not kept | DPO-1 |
| The detector LLM misses a value | It leaves in clear text, unless a guard rail rereads the text | DPO-4 |
| The analyzed text contains a tag that imitates the data area of the prompt | The tag is neutralized before it is sent to the detector LLM | DPO-1 |
| The conversation model invents a placeholder, `<<PERSON:10>>` while the conversation only has `<<PERSON:1>>` | Refused by default, removed or kept depending on the strategy | DEV-8 |
| The conversation model changes the case or the digits of a placeholder, `<<Person:1>>` or `<<PERSON:01>>` | It is not restored, and it is treated as an invented placeholder | DEV-8 |
| The conversation model damages the delimiters of a placeholder, `<< PERSON:1 >>` or `PERSON:1` | It is neither restored nor recognized as a placeholder, and the user reads it as is. No value leaks, and this behavior is accepted | USER-1 |
| The conversation model guesses the real value behind a placeholder and writes it | The value is treated as introduced by the assistant | DEV-11 |
| The user types a placeholder themselves, `<<PERSON:2>>` | It does not reveal the value of another person | DPO-1 |
| The reply stream stops in the middle of a placeholder | The fragment is returned as is, without a real value | USER-4 |
| The conversation model cuts or rephrases a placeholder in a tool argument | Only a placeholder written in full is restored, the tool receives the rest as is | DEV-4 |
| The API server is unreachable from the Claude Code hooks | The prompt or the tool call is blocked, the tool output replaced by a notice, unless fail open is requested | DPO-9 |

---

## See also

- [Processes](processes/), the complete scenarios with their rules and their error cases.
- [Glossary](glossary.md), the de-identification terms.
