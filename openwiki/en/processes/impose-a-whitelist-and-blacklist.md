---
type: workflow
title: Impose a whitelist and a blacklist
description: How the whitelist of the configuration (override section) forces the masking of a value the detector misses, how a blacklist keeps a value in clear, who wins when the two contradict each other, and why these lists take precedence over a human correction.
tags: [override, whitelist, blacklist, detection, guard, provenance]
sources:
  - id: openwiki-source-6b7f5f02702990f6448a1a5f
    resource: repo://src/piighost/components/override/detector.py
  - id: openwiki-source-aa2829050fd72de956faf3f4
    resource: repo://src/piighost/components/override/strategy.py
  - id: openwiki-source-169555bcaa5f0efb2e817dc5
    resource: repo://src/piighost/config/models/override.py
  - id: openwiki-source-5ddce4dd4539293afb49cdfd
    resource: repo://src/piighost/pipeline/base.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Impose a whitelist and a blacklist

## In short

- Two lists, written in the `[override]` section of the configuration, correct the detector. The whitelist always masks, the blacklist never masks.
- The configuration is the pipeline's, whether it runs in the application or in the `piighost-api` server.
- These lists come before everything else, including a correction made by hand by a person.
- A blacklisted value goes to the model in clear, and the final check does not block it.
- When both lists target the same value, the whitelist wins by default, so the value is masked.
- A changed list only applies to the new messages of a conversation already under way.

Needs covered: DPO-3, USER-5 and USER-6, described in [Needs by profile](../needs-by-profile.md). The terms are defined in the [glossary](../glossary.md). The full path of a message is in [Protect a message before it is sent to the model](protect-a-message.md).

## For the business

PIIGhost has no screen. The technical team writes the whitelist and the blacklist, in the code or in the `[override]` section of the configuration file of the application or of the `piighost-api` server. The DPO decides their content. The tasks below say what to ask for.

### The path of a message through the lists

```mermaid
flowchart TD
    A["User message"] --> B["Spotting by the detector"]
    B --> C["Blacklist: the value stays in clear"]
    B --> D["Whitelist: the value is masked, even if missed"]
    C --> E{"Do both lists target the same passage?"}
    D --> E
    E -- "conflict setting" --> F["Replacement by a placeholder"]
    F --> G["Final check, which ignores the blacklist"]
    G --> H["Sending to the model"]
```

### Example followed from end to end

The whitelist contains the form "PRJ- followed by four digits", with the type `PROJET`. The blacklist contains "Acme", the company name. The detector reads "Acme" as a person and does not know the case numbers.

| Step | Text |
|---|---|
| User message | Write to Jean Dupont, at Acme, case PRJ-0042. |
| Without the lists | Write to `<<PERSON:1>>`, at `<<PERSON:2>>`, case PRJ-0042. |
| With the lists, received by the model | Write to `<<PERSON:1>>`, at Acme, case `<<PROJET:1>>`. |
| Reply read by the user | Noted for PRJ-0042. |

### Keep a value in clear

Typical case: your company name is read as a person's name, and the model needs it to answer.

1. List the exact values to keep in clear, with their spelling.
2. State whether the value must stay in clear whatever way the detector classifies it. This is the default setting.
3. If a longer value contains it ("Acme Services" for "Acme"), say whether the longer value must also stay in clear.
4. Send the list to the technical team.

**How to check**: have a test sentence protected. For example, "Claire Dubois works at Acme." must give "`<<PERSON:1>>` works at Acme."

### Force the masking of a value

Typical case: your internal code names are never spotted.

1. Describe the exact form of the values, for example "PRJ- followed by four digits".
2. State whether a value first quoted by the assistant must also be masked. By default, no (BR-LIST-05).
3. Send the description to the technical team.

**How to check**: have a sentence that contains a code name protected. It must be replaced by a placeholder like `<<CODE:1>>`.

### Rules to know

**BR-LIST-01.** When a value is in the blacklist, then it is removed from the values to mask and goes to the model in clear.

**BR-LIST-02.** When a value is in the whitelist, then it is masked, even if the detector missed it. If the detector had spotted a piece that overlaps it, the whitelist's detection replaces that piece.

**BR-LIST-03.** When the blacklist targets a value, then the way to apply it follows one of three settings. Example on "Claire Dubois works at Acme, then at Globex SA.", with a detector that reads "Acme" as a person, and a blacklist that contains "Acme" and "Globex" as organizations:

| Setting | Removes | Result |
|---|---|---|
| Same value (default) | any detection of the same text, whatever its position and type | `<<PERSON:1>>` works at Acme, then at `<<ORG:1>>`. |
| Exact | only a detection with the same position and the same type | `<<PERSON:1>>` works at `<<PERSON:2>>`, then at `<<ORG:1>>`. |
| Overlap | any detection that touches the value, even a longer one | `<<PERSON:1>>` works at Acme, then at Globex SA. |

"Same value" is the default because the blacklist names a value, and the type written next to it is only a guess about what the detector will say.

**BR-LIST-04.** When both lists target the same passage, then the conflict setting decides:

| Setting | Result on "Acme" present in both lists |
|---|---|
| The whitelist wins (default) | masked: `<<ORG:1>>` |
| The blacklist wins | in clear: `Acme` |
| Refuse | stop with `Overrides contradict each other on 'Acme': a whitelisted span overlaps a blacklisted one.` |

This default comes from a simple principle. When in doubt, masking protects.

**BR-LIST-05.** When the assistant is the first to quote a whitelisted value, then it stays in clear by default. A "force" setting masks it anyway. The reason is that masking a value the model brought itself takes useful knowledge away from it. The masking also signals to it that this precise value is sensitive.

**BR-LIST-06.** When a person corrects the values of a message by hand, then both lists still apply to the correction and take precedence over it. For example, the user removes "PRJ-0042" from the masked values of their message, but the number stays masked.

**BR-LIST-07.** When the final check rereads the protected text, then it ignores the blacklisted values. Any other value left in clear blocks the sending.

**BR-LIST-08.** When a list changes during a conversation, then a message already analyzed keeps its old result, even when sent again unchanged. For example, on 2026-10-02, "Acme" enters the whitelist. The message sent on 2026-10-01 in the same conversation keeps "Acme" in clear. Only new messages apply the list.

### What the end user sees

Nothing different. The restored reply contains the real values. Only the model sees the difference between a masked value and a value kept in clear.

### Frequently asked questions

**The company name is still masked although it is in the blacklist.** Three possible causes. The value is also in the whitelist (BR-LIST-04). Or the detected text is longer than the listed value, with the "Same value" setting (BR-LIST-03). Or the message had been analyzed before the value was added to the list (BR-LIST-08).

**A whitelisted code name stays in clear.** The assistant probably quoted it first in the conversation (BR-LIST-05). Ask for the "force" setting if the value must always be masked.

**Processing stops with `Overrides contradict each other on …`.** The conflict setting is "Refuse" and a value is in both lists. Remove it from one of the two.

## For developers

The technical guide shows both lists at work in [How to force a detection or keep a value in clear](../../../docs/en/examples/overrides.md).

### Where the rules live

| Rule | Location |
|---|---|
| BR-LIST-01, BR-LIST-03 | `src/piighost/components/override/detector.py:16-42`, `_clear` lines 141-150 |
| BR-LIST-02 | `detector.py:122-139` (`_force`) |
| BR-LIST-04 | `detector.py:84-104` (`apply`), `_refuse_collisions` lines 152-162 |
| BR-LIST-05 | `detector.py:113-120` (`forces_value`), `pipeline/thread.py:322-329` |
| BR-LIST-06 | `pipeline/thread.py:210` (`anonymize_corrected`) |
| BR-LIST-07 | `pipeline/base.py:225-234` (`_cleared_values`), `pipeline/base.py:313-341` (`_guard`) |
| BR-LIST-08 | `pipeline/thread.py:271-287` (`_detect` reapplies nothing on a cached message) |
| Strategies and defaults | `components/override/strategy.py`, `config/models/override.py:26-32` |
| Whitelist and blacklist in the server | `piighost-api` reads the same `[override]` section of its configuration |

Related components: `AnyDetectionOverride` (port, without template), `DetectionOverride` (implementation driven by two detectors), `BlacklistStrategy`, `WhitelistStrategy`, `OverrideConflictStrategy`, `ConflictingOverrideError`.

Position in the pipeline: right after detection, before overlaps and expansion (`pipeline/base.py:364-371`). In the conversation pipeline, before each write to memory (`pipeline/thread.py:276-286`).

### Configure the lists

1. Start from the `[override]` section documented in `docs/en/configuration/toml.md`.
2. Write each list as a full detector, often `type = "exact"` or `type = "regex"`:

```toml
[override]
blacklist_strategy = "value"
conflict_strategy = "whitelist_wins"

[override.whitelist]
type = "regex"
patterns = { CODE = 'PRJ-[0-9]{4}' }

[override.blacklist]
type = "exact"
values = { Acme = "ORG" }
```

3. To also mask the values first quoted by the assistant, add `whitelist_strategy = "force"`.

#### Check

```bash
uv run pytest tests/components/override tests/config/test_guard_override_models.py
```

Then run `piighost anonymize --config <your file> "Claire Dubois works at Acme on PRJ-0042."`. You must see "Acme" in clear and `<<CODE:1>>` in place of the code.

### Pitfalls

- **The lists are full detectors.** A heavy regex list or a model detector runs a computation again on each message, and a second time for the final check (`cleared_values`).
- **`forces_value` runs the whitelist again on each entity value** introduced by the assistant, under `FORCE`.
- **A cached detection does not go through the lists again** (BR-LIST-08). To apply a new list to a conversation under way, clear the conversation (`forget_thread`) or correct the message through `anonymize_corrected`.
- **`ExactMatchDetector` is first of all a test tool.** Used as a whitelist in `DetectionOverride`, it survives human corrections. Used alone as the main detector, it does not.

### Tests

| Test | Covers |
|---|---|
| `tests/components/override/test_override.py` | The three blacklist strategies, the order according to the conflict setting, the refusal, `forces_value` |
| `tests/config/test_guard_override_models.py` | The `[override]` configuration model |
| `tests/config/test_settings.py` | `test_whitelist_forces_a_detection` |
| `tests/pipeline/test_override_integration.py` | The lists take precedence over a human correction (AT-USER-6-3), whitelist and blacklist from end to end (AT-DPO-3-1, AT-DPO-3-2) |

Not covered: the effect of a list change on a message already cached (BR-LIST-08). This behavior was observed by running the pipeline, not read in a test.
