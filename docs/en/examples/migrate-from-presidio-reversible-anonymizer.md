---
icon: lucide/arrow-right-left
description: Replace LangChain's archived PresidioReversibleAnonymizer with piighost. Keep Presidio detection, pseudonymize the prompt and restore PII in the LLM reply.
seo_title: Migrate from PresidioReversibleAnonymizer to piighost
---

# Migrate from PresidioReversibleAnonymizer

To migrate from `PresidioReversibleAnonymizer`, wrap your Presidio `AnalyzerEngine` in a `PresidioDetector` and build a `ThreadAnonymizationPipeline` on it. Then call the pipeline's `anonymize` and `deanonymize` with a `thread_id`. Presidio keeps detecting the values, and `piighost` replaces and restores them.

The old class lived in `langchain-experimental`, which LangChain [sunset](https://github.com/langchain-ai/langchain-experimental/issues/87) on 22 May 2026. Its [repository](https://github.com/langchain-ai/langchain-experimental) is archived, so it gets no more fixes.

!!! note "Prerequisites"
    `pip install "piighost[presidio,langchain]"`. Presidio's default `AnalyzerEngine` loads the spaCy model `en_core_web_lg`, as the old class did. The `langchain` extra is only needed for the model call and the middleware.

## Before, with PresidioReversibleAnonymizer

The old class detects with Presidio, replaces each value with a fake one drawn from Faker, and keeps the mapping inside the object.

```python
--8<-- "snippets/migrate_presidio_before.py:before"
```

The LLM reads a made-up name and a made-up email in place of `Patrick Martin`{ .pii } and `patrick@example.com`{ .pii }. `deanonymize()` swaps them back, and `save_deanonymizer_mapping()` writes the mapping to a JSON file if you want to keep it.

## After, with piighost

The same round trip with `piighost` keeps the Presidio engine and replaces the anonymizer object with a thread pipeline.

```python
--8<-- "snippets/migrate_presidio_after.py:after"
```

The output should be:

```text
--8<-- "snippets/migrate_presidio_after.out:after"
```

The LLM reads `<<PERSON:1>>`{ .placeholder } and `<<EMAIL:1>>`{ .placeholder }. The `labels` map renames Presidio's `EMAIL_ADDRESS` to `EMAIL`, and it plays the role of `analyzed_fields`, since a type it does not list is dropped. The conversation memory keeps the mapping under `thread-42`, so the next message of the thread reuses the same placeholders.

## In a LangChain agent

If the old class sat in a LangChain chain in front of an agent, hand the same pipeline to `PIIAnonymizationMiddleware` instead of calling it by hand. The middleware de-identifies each message, restores the reply, and by default gives tools the real values. See [LangChain middleware](../getting-started/langchain.md).

## What changes

- Placeholders replace fake values. `<<PERSON:1>>`{ .placeholder } cannot collide with a real name, where a Faker name can. A Faker factory is ruled out on purpose, see the [FAQ](../community/faq.md#can-i-get-realistic-fake-values-instead-of-tokens).
- The mapping is scoped to a conversation. One old object held a single mapping for every text it saw, while the pipeline keeps one per `thread_id` and erases it with `forget_thread`.
- The mapping is stored in a conversation memory, in RAM by default, or in Redis or SQL, which can encrypt the values. It replaces `save_deanonymizer_mapping()` and `load_deanonymizer_mapping()`. See [Deployment](../deployment.md).
- The methods are asynchronous, so they are awaited.
- Detection is open to other detectors. Presidio can sit next to a regex group of the catalog or a GLiNER2 model, see [Pre-built detectors](detectors.md).
- The `allow_list` argument of `anonymize()` becomes an allow list in the pipeline, see [Deny and allow lists](overrides.md).
- The LangChain middleware also restores tool-call arguments and a streamed reply, which the old class did not do.
