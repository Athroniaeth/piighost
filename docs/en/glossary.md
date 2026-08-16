---
icon: lucide/book-a
---

# Glossary

Terms used across the `piighost` documentation. Each entry defines the concept by
what it does. Class names stay in English.

PII
:   Personally Identifiable Information. Any value that can identify a person:
    name, address, phone number, email, location, organization, account number.
    `piighost` finds and replaces PII so a downstream LLM never sees the raw
    value.

De-identification
:   Replacing PII with placeholders while keeping the mapping between each value
    and its placeholder, so the original can be restored later. The default
    `piighost` pipeline de-identifies. Under the GDPR this is pseudonymization,
    not anonymization.

Anonymization
:   Removing PII with no way to restore it. Irreversible by definition. A
    redacting placeholder factory anonymizes, since it keeps no mapping back to
    the value.

Placeholder
:   The token that replaces a PII in the anonymized text, for example
    `<<PERSON:1>>`{ .placeholder } or `<<EMAIL:1>>`{ .placeholder }. What a
    placeholder looks like is decided by a placeholder factory.

Placeholder factory
:   The component that produces placeholders. It decides the token shape and what
    the token preserves: a label, a stable identity, both, or nothing. Built-in
    factories include `RedactPlaceholderFactory`, `LabelPlaceholderFactory`,
    `LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`, and
    `MaskPlaceholderFactory`.

Detector
:   The component that finds PII in a text and returns detections. Detectors
    implement the `AnyDetector` protocol and are interchangeable. Three families
    exist, listed under their own entries: regex, NER, and LLM.

Regex detector
:   A detector that recognizes fixed patterns, character strings that follow a
    known structure such as an IBAN or a phone number. Effective on structured
    formats, useless on free text like a first name or a written date.
    `RegexDetector`.

NER detector
:   Named Entity Recognition. An AI model that classifies the words of a text into
    categories decided in advance, such as person, location, or organization.
    Works on free text where a pattern cannot. `SpacyDetector`, `Gliner2Detector`,
    `TransformersDetector`.

LLM detector
:   A detector that prompts a large language model to return the PII it finds as
    structured output. Slower and less deterministic than regex or NER, but able
    to reason about context. `LLMDetector`.

Span
:   A half-open character range `[start, end)` inside a text, mirroring Python
    slice semantics. Every detection carries a `Span` to mark where the PII sits.
    `Span`.

Detection
:   One PII occurrence spotted by a detector: a `Span`, the matched text, a
    label, and a confidence in the range 0 to 1. Detecting `Patrick`{ .pii } as
    `PERSON` at `(0, 7)` with confidence `0.95` is one `Detection`.

Entity
:   A group of detections that refer to the same PII value. Every occurrence of
    the value is one detection. The group shares one placeholder and restores to
    one value. Different from a detection, which is a single occurrence.
    `Entity`.

Linker
:   The component that groups detections into entities. It finds the occurrences
    that refer to the same value, so they share a placeholder. Linking
    `Patrick`{ .pii } at `(0, 7)` and `patrick`{ .pii } at `(34, 41)` yields one
    entity. `ExactEntityLinker`.

Entity resolver
:   The component that reconciles entity conflicts, for example two groups that
    should be one when their values are close. `MergeEntityResolver` unions
    overlapping groups, `FuzzyEntityResolver` merges near-duplicate values,
    `SeparateEntityResolver` leaves each group as is.

Guard rail
:   A component that re-checks the anonymized text for PII the pipeline missed. It
    runs after replacement and raises if a residual PII remains. A guard can
    re-run a detector (`DetectorGuardRail`) or query an LLM (`LLMGuardRail`).

Thread
:   A conversation scope identified by a `thread_id`. Memory is isolated per
    thread, so two parallel conversations never share PII state. A placeholder
    stays stable across all the messages of one thread.

thread_id
:   The string that identifies a thread. The thread pipeline and the middleware
    use it to scope memory and to route each message to the right conversation.

Conversation memory
:   The store that accumulates a thread's entities across messages, so a value
    seen in one message keeps its placeholder in the next.
    `InMemoryConversationMemory` holds it in the process.
    `RedisConversationMemory` persists it in Redis, with values encrypted by a
    cipher and keys hashed.

Recognizer
:   The token grammar the middleware uses to find a pipeline's placeholders in an
    LLM response, without reaching into the anonymizer. A pipeline exposes it as
    `recognizer`, a `BaseDelimitedPlaceholderFactory` or `None`.

Placeholder preservation tag
:   A phantom type on a placeholder factory that states what its tokens preserve:
    `PreservesNothing`, `PreservesLabel`, `PreservesIdentity`, or
    `PreservesLabeledIdentity`. The middleware requires `PreservesIdentity` so it
    can restore values, and rejects a factory that does not, at type-check time.

Pepper
:   A secret that keys a hasher, read from the `PIIGHOST_HASH_PEPPER` environment
    variable. Hashing a low-entropy PII without a secret leaves it
    brute-forceable, so the pepper is mandatory. Used by `Sha256Hasher` and
    `Argon2Hasher`.

Cipher
:   A component that reversibly encrypts and decrypts bytes, so a store keeps
    ciphertext instead of plaintext. A leak of the store yields nothing without
    the key, held outside it. `RedisConversationMemory` uses one to encrypt
    persisted values. `AesGcmCipher` is the built-in AES-GCM backend.
