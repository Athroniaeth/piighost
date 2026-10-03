---
type: reference
title: Open points
description: The decisions taken on the needs by profile and what remains to do to meet them, the fail closed behavior of a detector, the storage form of corrections, models on the hub, with what is already done and what remains to decide.
tags: [backlog, decisions, personas]
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Open points

## In short

- This page tracks the decisions taken on the needs and what remains to do to meet them.
- Each point cites the need concerned (`DPO-9`, `DEV-10`…) and, when it exists, the commit that settled it.
- The gaps between the documentation and the code are in the [gap register](doc-code-gaps.md), not here.

## Decided, to do

Decided on 2026-10-02.

- **DPO-10, storage form of corrections.** Design the export of human validations, to Langfuse for example, with three forms to choose from: placeholders instead of the values, values in clear, input and output fully redacted. The default form is placeholders (decided on 2026-10-02).
- **OPS-6, models on the hub.** The rejection of model configurations is temporary. It needs a format that splits the labels between patterns and model, because each NER model is stronger on some labels.

## Done

Done on 2026-10-02, on the local branches. Nothing is pushed.

- **DPO-9.** `LLMDetector` and `LLMGuardRail` raise `UnreadableOutputError` on unreadable output, and `fail_open=True` restores fail open with a warning (`4d47d65`). The Claude Code hooks exit with code 2 for a prompt or a tool call they cannot de-identify, replace a tool output with a notice, and `PIIGHOST_HOOK_FAIL_OPEN=1` lets the text through (`5ec03d1`).
- **Placeholders with damaged delimiters.** Accepted and documented: a placeholder such as `<< PERSON:1 >>` is not restored and the user reads it as is, without any value leaking.
- **Rights of the OpenWiki job.** It does not rewrite the text of a need or of a business rule. A disagreement with the code becomes a line in the gap register (`INSTRUCTIONS.md`).

- **DEV-10.** `require_thread_id` is removed. The LangChain middleware, the Claude Code hooks and `PIIGhostClient.detect` require a conversation (`piighost` `97b1e78`), and the server responds 400 without `thread_id` (`piighost-api` `7dec988`). The CLI keeps `--thread-id default` for a standalone command.
- **OPS-7.** The in-process memory is bounded by default to 10,000 conversations and a lifetime of one day (`4af48d3`). The Redis memory keeps its optional `ttl`, because its persistence is intended.
- **Documentation.** The reply of a tool goes through full detection, and a cut stream returns its fragment (`3473217`).
- **Acceptance tests.** AT-DPO-1-2, AT-DPO-2-2, AT-DPO-5-2, AT-DPO-6-1, AT-DEV-3-2, AT-OPS-2-1 and AT-OPS-3-1 in `tests/acceptance/` (`21e5ac9`).

## Proposed, not yet decided

- DPO-1: add as criteria "no following turn, no content block and no tool argument returns a value in clear" and "a placeholder typed by the user does not reveal the value of another", already tested.
- OPS-4: add "a malformed key without `PIIGHOST_ALLOW_ANONYMOUS` prevents startup" and "a protected route without a token responds 401".
