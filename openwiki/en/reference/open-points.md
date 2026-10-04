---
type: reference
title: Open points
description: The decisions taken on the needs and what remains to do to meet them, the storage form of corrections and models on the hub, then the proposals that remain to decide.
tags: [backlog, decisions, personas]
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Open points

## In short

- This page tracks the decisions taken on the needs and what remains to do to meet them.
- Each point cites the need concerned, such as `DPO-10` or `OPS-6`.
- What is done is not listed here. The need and its acceptance tests show it, and the git history keeps the detail.

## Decided, to do

Decided on October 2, 2026.

- DPO-10: design the export of human validations, to Langfuse for example. Three forms will be available, placeholders instead of the values, values in clear, or input and output fully masked. The default form is placeholders.
- OPS-6: accept model configurations on the hub. Their current rejection is temporary. It needs a format that splits the labels between patterns and model, because each NER model is stronger on some labels.

## Proposed, not yet decided

These proposals add criteria to existing needs. Each criterion describes a behavior that tests already check. What remains to decide is whether it goes into the text of the need.

- DPO-1: add two criteria.
    - No value goes back to the model in clear, neither in later turns of the conversation, nor in a message split into several blocks, nor in the argument of a tool call.
    - A placeholder the user types themselves, such as `<<PERSON:2>>`, does not reveal the value of another person.
- OPS-4: add two criteria.
    - The `piighost-api` server refuses to start if an API key is malformed, unless `PIIGHOST_ALLOW_ANONYMOUS` is set.
    - A protected route called without a key answers 401.
