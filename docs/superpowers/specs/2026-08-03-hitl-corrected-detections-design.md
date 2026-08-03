# HITL Corrected Detections Design

Design spec for a human-in-the-loop correction method on the thread pipeline of
the PIIGhost v2 rewrite. Internal design document, French prose, English code
identifiers.

## Context

`ThreadAnonymizationPipeline` (`src/piighost/pipeline/thread.py`) anonymizes each
message of a thread with tokens stable across the thread. It caches each
message's detections in an `AnyConversationMemory`, keyed by the message text;
`remember` replaces any prior entry, and `_detect` reads the cache before running
the detector. Token assignment unions every message's detections
(`_thread_tokens`), so a value keeps one placeholder across the thread.

There is no way today for a human to correct what the detector found on a message
and re-anonymize with that correction.

## Goal

Add one method on `ThreadAnonymizationPipeline` that takes a human-corrected set
of detections for a user message, persists it in place of the auto-detected set,
and re-anonymizes the message with thread-consistent tokens.

## Key decisions

- **Corrected detections provided directly.** The human reviews the detected
  spans (in a front end) and resubmits the corrected `list[Detection]`. The
  method replaces, not deltas: the corrected list is the message's new detection
  set, matching `memory.remember`'s replace semantics.
- **User messages only.** A human corrects their own messages, never the model's.
  The method has no `role` parameter; it records the correction as
  `MessageRole.USER`. Correcting an assistant message is out of scope.
- **The human is authoritative.** The corrected set is stored as given, without
  re-running overlap resolution or occurrence expansion, unlike auto-detection.
- **Thin over the existing flow.** The method persists then delegates to
  `anonymize`, whose `_detect` reads the just-written cache, so no detector runs
  and the thread's token assignment honors the correction.

## Architecture

A new method on `ThreadAnonymizationPipeline`:

```python
async def anonymize_corrected(
    self,
    text: str,
    thread_id: str,
    detections: list[Detection],
) -> Anonymization[PreservationT]:
```

Body:

1. `await self.memory.remember(thread_id=thread_id, message=text,
   detections=detections, role=MessageRole.USER)` replaces this message's cached
   detections with the corrected set, as a user message.
2. `return await self.anonymize(text, thread_id, MessageRole.USER)` re-renders.
   Because `_detect` reads the cache first and finds the just-written entry, it
   returns the corrected detections without running the detector, and
   `_thread_tokens` assigns tokens over the thread's union, so the correction
   holds for this message and feeds the union for the rest of the thread.

The method requires no prior `anonymize` call; a caller may invoke it directly
with text plus a corrected set.

## Review input

No new detection method is added. The review data comes from the first
`anonymize(text, thread_id)` pass: `Anonymization.tokens` maps each anonymized
`Entity` to its token, and each `Entity` carries its `text`, `label`, and
`detections` (spans). A front end shows these, the human removes false positives
and adds missed values, and resubmits the corrected `list[Detection]` to
`anonymize_corrected`.

## Persistence and scope

The correction replaces this message's memory entry only. Since token assignment
unions every message's detections, the correction holds for the corrected message
and influences the rest of the thread through the union, but stays local to the
message:

- removing a value from one message does not remove it if another message in the
  thread still detects it;
- adding a value to one message does not propagate it to other already-cached
  messages that never detected it.

This per-message scope matches the "correct your own message" model.

## Guard

`anonymize_corrected` reuses `anonymize`, so the guard rail (when configured)
runs on the re-rendered output. A value the human added but placed on a span that
leaves clear PII elsewhere could be re-flagged; that is the guard doing its job.

Known limitation: when the human drops a false positive, that value is not in the
`preserved` set the guard exempts (that set holds only detected-but-left-in-clear
entities, such as assistant-provenance ones). So a configured guard whose
detector re-finds the dropped value raises `PIIRemainingError`, overriding the
human's authoritative drop. This is pre-existing `anonymize` behavior, not
introduced here, and it bites only when a guard is configured and its detector
flags the dropped value. Making the guard defer to a human drop would mean
feeding the dropped values into the guard's `expected` set, a follow-up that
touches `anonymize`/`_guard` rather than this thin method.

## Edge cases

- An empty corrected list means the message holds no PII: it renders unchanged,
  and memory stores an empty entry (message seen, no PII).
- The human is authoritative over spans. Rendering is span-based, so an
  inconsistent span is the caller's responsibility.
- Calling the method again with a new corrected set replaces the entry again
  (the replacement is idempotent for a given set).

## Testing

Deterministic, using `ExactMatchDetector` (no model):

- correcting a message to add a missed value tokenizes it on re-render;
- correcting a message to drop a false positive leaves that value in clear on
  re-render;
- the correction enters the thread's token map: an added value is deanonymizable
  from the thread afterward (`deanonymize` on its token restores the value), so
  the correction is reversible thread-wide;
- the correction is local to the message: dropping a value from one message does
  not stop a later message from tokenizing it when the detector detects it there;
- calling the method twice with different corrected sets replaces cleanly, the
  second result reflecting only the second set.

## Out of scope

- Inline correction markers in the message text, and a structured
  force/suppress-list argument (the corrected `list[Detection]` is the channel).
- A public `detect` method (review comes from the first `anonymize` pass).
- Correcting assistant messages, relabeling as a distinct operation, or
  cross-message propagation of a single correction.
- Any change to the base pipeline, the memory port, or the anonymizer.
