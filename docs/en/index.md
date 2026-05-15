---
icon: lucide/shield
---

# PIIGhost

`piighost` is a library for building **PII anonymization pipelines**. It sits as a layer on top of any regex, NER, or LLM you plug in, designed to work with conversational agents, so you can use a hosted LLM (GPT, Claude, Gemini) without ever sending it the raw data of your users. `piighost` spots PII like names, emails, addresses, anything the model does not need to see, swaps them for placeholders (for example `Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder }, `patrick@acme.com`{ .pii } becomes `<<EMAIL:2>>`{ .placeholder }, `Paris`{ .pii } becomes `<<LOCATION:1>>`{ .placeholder }) the LLM can still reason about, and restores the real values for your tools and your end users. The same PII keeps the same placeholder across an entire conversation, even when it spans multiple messages or tool calls, and your agent code does not change.

On top of the core pipeline, `piighost` ships extra layers to harden each step, like composable detectors with confidence arbitration for **detection**, a tolerant linker for **correction** of typos and case variants, and output guardrails (regex or LLM-based) for **safety** when the LLM accidentally generates fresh PII in its response.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant M as piighost
    participant L as LLM
    participant T as Tool

    U->>M: "Email Patrick at patrick@acme.com"
    M->>L: "Email <<PERSON:1>> at <<EMAIL:1>>"
    L->>M: tool_call(send_email, to=<<EMAIL:1>>)
    M->>T: send_email(to="patrick@acme.com")
    T-->>M: "Sent."
    M-->>L: "Sent."
    L-->>M: "Done, your email to <<PERSON:1>> has been sent."
    M-->>U: "Done, your email to Patrick has been sent."
```

*Full agent loop. The user and the tool see the real values; the LLM only ever sees placeholders.*
{ .figure-caption }

## Why piighost?

When you put an LLM feature into production, you typically pick from three families of providers, each with its own trade-off.

- **Hosted cloud outside the EU** (OpenAI, Anthropic, Google), the best models, but every byte of context, raw user PII included, leaves your jurisdiction.
- **EU-sovereign cloud** (Mistral AI, OVHcloud, Scaleway), legal guarantees on data residency, but you give up part of the state of the art.
- **Self-hosting open weights**, full control, but infrastructure to maintain and one notch behind the SOTA.

The only clean way to decouple the LLM from content sensitivity is to **anonymize upstream**. Once PII never reach the model, picking a provider stops being a privacy decision and goes back to being a question of quality, cost, and latency. That is exactly the slot `piighost` fills.

The legal detail (CLOUD Act, FISA 702, Schrems II) and the full provider-spectrum table live in [Why anonymize?](why-anonymize.md).

## Use cases

Five families of scenarios where `piighost` fits naturally, from the most defensive (protecting the user) to the most integrated (tool-enabled agents).

**1. Protecting users from third-party LLM providers.** Cloud APIs can store, cross-reference, and exploit PII: commercial profiling, legal requisitions, training on conversations, targeting of journalists, whistleblowers, or politicians.

*Example: a consumer medical assistant whose conversations should never leave your infrastructure with the patient's name attached.*

**2. Structured extraction without JSON leakage.** When an LLM extracts fields into a schema, PII reappear as-is in the output. With `piighost`, the model only manipulates placeholders; deanonymization restores the real values client-side.

*Example: extracting a notarial deed into a JSON (parties, assets, amounts) without the LLM ever accessing the real identities.*

**3. Document redaction.** Produce a shareable version of a confidential document while protecting natural persons, keeping the text readable and usable.

*Example: anonymizing a judgment before open-access publication.*

**4. Enterprise RAG over private documents.** A classic RAG pipeline on a cloud LLM effectively limits you to already-public documents: the moment you feed an internal contract, an HR file, or a strategic note into it, the provider ingests it. By anonymizing retrieved chunks before sending them to the model, you can index genuinely private documents while keeping a hosted LLM.

*Example: an internal legal knowledge base (contracts, annotated case law) queried through a cloud LLM without client names, amounts, or sensitive clauses leaving your infrastructure.*

**5. Agents with internal tools.** The LLM reasons on placeholders; the tools (CRM, email, DB) receive the real values at call time. The model never sees the PII, and the tools work normally.

*Example: a sales agent that queries the CRM and sends emails without the LLM ever having read the client names.*

**6. Bias reduction.** LLMs inherit biases from their training data (gender, ethnicity, age). Anonymising a first name, last name, or location before sending a text to the model prevents those biases from influencing a decision: the LLM judges only the content.

*Example: CV screening where first names, last names, and addresses are replaced with placeholders to neutralise discriminatory bias on the candidate's profile.*

---

## Problem statement

Today, with the rise of LLMs, protecting sensitive data takes on a new dimension. Companies hosting these models
can potentially exploit the data their users send them, and relying solely on GDPR offers a legal guarantee but
not a technical one. At the same time, proprietary models (GPT, Claude, Gemini) remain significantly more capable
than their open-source counterparts: you shouldn't have to choose between performance and privacy. Anonymizing
PII before they reach the LLM lets you benefit from the most capable models while keeping control over your users'
data.

!!! info "What is a PII?"
    A *PII* (**P**ersonally **I**dentifiable **I**nformation) is any piece of data that can identify a person:
    name, address, phone number, email, location, organization… Anonymizing them in AI agent conversations has
    become a privacy concern in its own right: an LLM hosted by a third party should not see your users' sensitive
    data.

!!! tip "New to these terms?"
    See the [Glossary](glossary.md) for definitions of NER, span, entity linking, middleware, placeholder, and more.

On paper, anonymizing PII is straightforward: pick a detector (regex for emails, NER model for names), swap matches for placeholders, send the result to the LLM. In practice, four problems show up almost immediately.

**Placeholder consistency.** The goal is to replace `Patrick`{ .pii } with a placeholder like `<<PERSON:1>>`{ .placeholder }, which tells the LLM two things: a person was hidden here, and every occurrence of `<<PERSON:1>>`{ .placeholder } refers to the same person. If `Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } at the start and `<<PERSON:3>>`{ .placeholder } at the end, the LLM can no longer reason about the fact that it is the same individual.

**Variants missed by the detector.** The NER picks up `Patrick Dupont`{ .pii } at the top of the text but misses a bare `Patrick`{ .pii } two sentences later. Or it catches `Patrick`{ .pii } but not lowercase `patrick`{ .pii }. Or not `Patriick`{ .pii } with a typo.

**Overlap between detectors.** Two NERs chained for higher recall can claim the same span with different labels (one says `PERSON`, the other says `ORG` because it mistook it for a company name). Without arbitration, the final replacement hits the same position twice and corrupts the text.

**Cross-message persistence.** Once the LLM has seen `<<PERSON:1>>`{ .placeholder } in message 1, message 2 must reuse the same placeholder. Without shared memory, `Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } then `<<PERSON:7>>`{ .placeholder } depending on the turn, and the LLM loses track.

`piighost` addresses the first three with three pipeline components (span resolution, entity
linking, entity merging), and the fourth with the conversational layer (`ThreadAnonymizationPipeline`).
Each component has a **trade-off**: span resolution may discard a legitimate
detection on a false conflict, fuzzy linking may group two distinct entities by mistake, and so on.
If your detections are already clean (or if you prefer to handle these cases yourself), each component can be
**disabled individually** via a `Disabled*` instance that turns it into a passthrough. See
[Extending PIIGhost](extending.md) for the per-section details.

### The conversational case (AI agents)

Using anonymization inside AI agents introduces several additional constraints:

- **Transparency**: the user sends their message in plaintext and receives the response in plaintext, without
  having to worry about anonymization.
- **External tool usage**: the agent must be able to call a tool (e.g. fetching the weather for a city mentioned
  in the conversation) with the real values, without the LLM itself seeing them.
- **Cross-message persistence**: an entity anonymized in the first message must stay anonymized the same way in
  every subsequent message, on both the user and agent side, so that the agent can reason about PII identity
  across the whole conversation.

---

## Solution

`piighost` combines existing building blocks to offer PII detection and anonymization that is at once accurate,
consistent, and easy to integrate:

- **Hybrid detection**: compose one or more NER backends and regex via `CompositeDetector` to get the best of
  both worlds.
- **Entity linking**: automatically groups variants (case, typos, partial mentions) to guarantee consistent
  placeholders.
- **Bidirectional anonymization**: every anonymization is cached and can be reversed on the fly, including on
  text produced by an LLM that never saw the real values.
- **LangChain middleware**: transparent integration into a LangGraph agent, without modifying your agent code.
  The LLM only sees placeholders, tools receive the real values, and the user sees the deanonymized response.

---

## How it works

The core of the library is a 5-stage pipeline, each stage pluggable via an interface:

```mermaid
flowchart LR
    A[Text] --> B[1. Detect]
    B --> C[2. Resolve Spans]
    C --> D[3. Link Entities]
    D --> E[4. Resolve Entities]
    E --> F[5. Anonymize]
    F --> G[Anonymized text]
```

1. **Detect**: multiple detectors (NER, regex) spot PII candidates.
2. **Resolve Spans**: arbitrate overlaps and nesting between detections.
3. **Link Entities**: group occurrences of the same entity (including typos and case variations).
4. **Resolve Entities**: merge groups that are inconsistent across detectors.
5. **Anonymize**: replace with placeholders via a pluggable factory.

See [Architecture](architecture.md) for the details of each stage.

---

## Why not an existing solution?

Other libraries cover part of the scope:

- **[Microsoft Presidio](https://github.com/microsoft/presidio)**: rich catalogue of built-in recognizers
  (credit cards validated with Luhn, IBANs with checksum, SSNs, passports, emails, phone numbers) enriched by
  keyword-based context scoring, with an NER engine backed by spaCy / stanza / transformers. No native
  cross-message linking and no bidirectional LangChain middleware. Excellent as a raw detection engine, but
  leaves the developer responsible for orchestrating the conversational case.
- **spaCy extensions / custom regex**: good for batch processing pipelines, but do not handle the
  anonymization/deanonymization round trip across a conversation.

`piighost`'s differentiator: **persistent cross-message linking** and a **bidirectional middleware**
(text → placeholders → LLM → text → tools → placeholders → user) that works out of the box in LangGraph.

At a glance, feature parity vs alternatives:

<div class="wide-table" markdown="1">

|                                                  | **piighost**            | LangChain                    | Microsoft Presidio             |
|--------------------------------------------------|-------------------------|------------------------------|--------------------------------|
| Interchangeable detectors (NER, regex, LLM…)     | ✅                      | ⚠️ regex / Presidio only     | ⚠️ tied to spaCy / recognizers |
| Composing multiple detectors                     | ✅                      | ❌ one strategy per instance | ⚠️ partial                     |
| Cross-message entity linking                     | ✅                      | ❌                           | ❌                             |
| Case / typo tolerance                            | ⚠️ approximate matching | ❌                           | ❌                             |
| Reversible anonymization (deanonymize)           | ✅                      | ❌ block / mask only         | ⚠️ separate API                |
| LangChain / LangGraph middleware                 | ✅                      | ✅                           | ❌                             |
| Deanonymizes / re-anonymizes tool calls          | ✅                      | ❌                           | ❌                             |
| Async-first API                                  | ✅                      | ⚠️                           | ⚠️                             |
| Customizable placeholder format                  | ✅                      | ⚠️ template only             | ⚠️ template only               |

</div>

---

## Preview

Input:

> `Patrick`{ .pii } lives in `Paris`{ .pii }. `Patrick`{ .pii } loves `Paris`{ .pii }.

Output:

> `<<PERSON:1>>`{ .placeholder } lives in `<<LOCATION:1>>`{ .placeholder }. `<<PERSON:1>>`{ .placeholder } loves `<<LOCATION:1>>`{ .placeholder }.

Both occurrences of `Patrick`{ .pii } are linked, same for `Paris`{ .pii }. In a conversation, subsequent messages
reuse the same placeholders, and deanonymization is automatic for the end user.

For installation and the first full example, see [Installation](getting-started/installation.md) then [First pipeline](getting-started/first-pipeline.md).

---

## Navigation

Each page follows a specific role from the [Diátaxis framework](https://diataxis.fr/): tutorial to learn, how-to to solve a task, reference to look up the API, explanation to understand design choices.

<div class="grid cards" markdown>

-   :lucide-rocket: __Get started__

    ---

    Install and take piighost for a spin.

    - [Installation](getting-started/installation.md)
    - [Quickstart](getting-started/quickstart.md)
    - [First pipeline](getting-started/first-pipeline.md)
    - [Conversational pipeline](getting-started/conversation.md)
    - [LangChain middleware](getting-started/langchain.md)
    - [Remote client](getting-started/api-client.md)
    - [Basic usage](examples/basic.md)

-   :lucide-wrench: __Usage__

    ---

    Recipes for specific use cases.

    - [LangChain integration](examples/langchain.md)
    - [Pre-built detectors](examples/detectors.md)
    - [Extending PIIGhost](extending.md)
    - [Testing](examples/testing.md)
    - [Deployment](deployment.md)

-   :lucide-book-open: __Reference__

    ---

    The full API documentation.

    - [Anonymizer](reference/anonymizer.md)
    - [Pipeline](reference/pipeline.md)
    - [Middleware](reference/middleware.md)
    - [Detectors](reference/detectors.md)

-   :lucide-layers: __Concepts__

    ---

    Understand the design choices.

    - [Architecture](architecture.md)
    - [Glossary](glossary.md)
    - [Limitations](limitations.md)
    - [Security](security.md)

-   :lucide-users: __Community__

    ---

    Participate, report, discuss.

    - [Contributing](community/contributing.md)
    - [Code of conduct](community/code-of-conduct.md)
    - [Bug reports](community/bug-reports.md)
    - [FAQ](community/faq.md)

</div>
