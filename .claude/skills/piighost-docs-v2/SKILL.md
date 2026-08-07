---
name: piighost-docs-v2
description: Use when writing or reviewing PIIGhost user-facing prose, the intro/pitch of README.md or README.fr.md, or any docs/en or docs/fr page. Triggers on choosing anonymisation vs dé-identification wording, prose that narrates instead of explaining, semicolons or em dashes in French, PIIGhost written in bold instead of code font, or an abstract explanation with no concrete example.
---

# PIIGhost docs voice (v2)

## Overview

This is the **voice layer** for PIIGhost documentation: how the text reads and which words it uses. It complements `piighost-docs`, which owns the **plumbing** (Zensical build, CSS classes, Mermaid, tables, nav, EN/FR mirroring). When the two disagree on wording or tone, this skill wins. For anything mechanical, defer to `piighost-docs`.

**Core principle: write an efficient reference, not a novel.** The reader wants to know what the thing does and why, in as few words as possible. Cut every sentence that only announces or dramatises.

## When to use

- Writing or rewriting the intro/pitch of `README.md` / `README.fr.md`.
- Writing or reviewing prose on any `docs/en` or `docs/fr` page.
- Deciding between "anonymisation" and "dé-identification".
- Reviewing a draft that feels padded, abstract, or over-narrated.

Not for: CSS, Mermaid syntax, nav config, build commands, table markup. Use `piighost-docs`. Not for AI-tell cleanup at the sentence level. Use the `humanizer` skill.

## Where each kind of content goes (Diátaxis)

PIIGhost docs follow Diátaxis (https://diataxis.fr). Four content modes, each answering a different user need. **One page serves one mode.** Do not fold reference into a tutorial, or an explanation into a how-to.

| Mode | User need | Where in PIIGhost | Example |
|---|---|---|---|
| Tutorial | learn by doing, first contact | `docs/*/getting-started/` | quickstart, installation |
| How-to guide | accomplish one task | `docs/*/examples/` | "dé-identifier un thread multi-messages" |
| Reference | look up a fact fast | `docs/*/reference/` | API surface, config keys |
| Explanation | understand why | concept pages (`architecture`, `why-…`, `placeholder-factories`, `tool-call-strategies`, `security`, `limitations`) | why de-identify at all |

Two axes place the modes: practical (tutorial, how-to) versus theoretical (reference, explanation), and study (tutorial, explanation) versus work (how-to, reference). Diagnostic: if a page both teaches a concept and enumerates every option, it is two pages. Split it.

### How to write in each mode

Each mode has its own stance and its own bans. Match the page to its mode before polishing sentences.

**Tutorial (learning).** Stance: a teacher beside the learner, first person plural (« nous allons », « on obtient »). You own the learner's success.
- Do: state the learning goal up front, give a visible result after every step (« la sortie ressemble à... »), keep steps concrete and repeatable, test every instruction against real failures.
- Don't: explain theory, offer choices or alternatives, dump peripheral detail. Minimise explanation and link out. « A tutorial is not the place for explanation. »

**How-to guide (task).** Stance: a peer helping someone who already knows the goal.
- Do: title « Comment [but précis] », use conditional imperatives (« si vous voulez X, faites Y »), keep only the steps the goal needs, order by dependency, seek flow.
- Don't: teach, inline full reference, add history or theory. « Practical usability is more helpful than completeness. »

**Reference (lookup).** Stance: a neutral map. « Describe and only describe. » Consulted, not read.
- Do: state facts objectively, mirror the structure of the code, keep patterns consistent, add short illustrative examples and warnings.
- Don't: instruct, explain, give opinion, use elegant variation. Consistency beats elaborate vocabulary here (this overrides variety, not the terminology and no-semicolon rules).

**Explanation (understanding).** Stance: a discussion that permits reflection, answering « pourquoi ».
- Do: give context and design decisions, weigh alternatives and trade-offs, make connections, state a viewpoint when useful.
- Don't: give procedural steps, replicate reference detail, stay at task eye-level. Bound the topic by repeatedly asking « pourquoi ? ».

### Never let a page drift between modes

The common failure is drift: a quickstart that starts explaining internals, a reference that starts teaching, an explanation that turns into a how-to. When you feel a page reaching into another mode, cut the intruding content and link to the page that owns it.

### Two levels of quality (Diátaxis)

Functional quality (accurate, complete, consistent) is measurable and comes first. Deep quality (flow, reads well, anticipates the reader) is judged and builds on top. Get the facts right before polishing the voice. The voice rules below serve deep quality, they never excuse an inaccurate page.

## The README is a signpost, not the docs

**Goal: a short README that drops the reader into the Zensical docs fast.** Everything deep lives in the docs. The README is the front door, not a room.

The README carries only:

- one paragraph on what `piighost` prevents, opening on the problem (les PII atteignent le LLM), not the architecture.
- one runnable minimal example or a single sequence diagram, just enough to make the mechanism click.
- a short links block into the four Diátaxis buckets (getting started, examples, reference, concepts).

Keep out of the README: detector catalogs, config reference, migration notes, the threat model, option-by-option comparisons. Those are docs pages. When tempted to explain a second concept in the README, link to the docs page instead.

## What a good doc page looks like (deepagents model)

Reference example: https://docs.langchain.com/oss/python/deepagents.

- **Descending pyramid.** What it is, then how to use it, then how it works. The reader can stop at any depth and still leave with something.
- **Lead with capability, not theory.** Open on what the reader can now do, with concrete action verbs. Save the rationale for lower on the page.
- **Code first, prose follows.** Show a runnable snippet, then explain it. Never make the reader wade through three paragraphs before the first line of code.
- **Skimmable.** Hierarchical headings, one or two sentence paragraphs, parallel-grammar lists, a callout for a single caveat, at most one diagram that mirrors the section structure.
- **Link out instead of inlining.** An overview page settles *what* and *why*, then links to the *how*. One page, one job.

### Quickstart shape (deepagents model)

The deepagents quickstart is a good tutorial skeleton. Reuse it for `getting-started/`:

1. Goal hook plus concrete deliverable: « Construire votre premier pipeline en quelques minutes. Vous allez dé-identifier une conversation avant qu'elle n'atteigne le LLM. »
2. Prerequisites as a single note.
3. Numbered steps, each a complete copy-paste block, building one component at a time. Offer parallel tabs for interchangeable choices (pip vs uv, one detector vs another) rather than repeating the whole snippet.
4. Show the expected output after the run.
5. A short « Comment ça marche » only after the reader has a working result.
6. Close on an escalation of next-step links (personnaliser, mémoire de conversation, déploiement).

## Terminology: dé-identification, not anonymisation

PIIGhost keeps the mapping between a value and its placeholder so it can restore the value. Under the RGPD that is **pseudonymisation**, not anonymisation. So in prose:

- Use **dé-identifié / dé-identification** for what the pipeline does by default.
- Reserve **anonymisation** for genuinely irreversible removal (no restoration possible). Say so explicitly when you use it.
- When the reversible nature matters (privacy claims, RGPD scope), state it in a `!!! note` (docs) or `> [!NOTE]` (README).

**Do not retro-edit existing docs for this yet.** The rule governs new and rewritten text. Migrating `why-anonymize.md`, existing pages, and page slugs is a separate, deliberate task.

## Hard rules for French prose

| Rule | Why | Wrong | Right |
|---|---|---|---|
| No semicolon | Splits into two clean sentences reads better | `...à leur place ; l'utilisateur voit...` | `...à leur place. L'utilisateur voit...` |
| No em dash | House style | `Le détecteur lit le texte — puis renvoie...` | `Le détecteur lit le texte, puis renvoie...` |
| No mid-sentence colon for apposition | Colon is for lists only | `des motifs : des chaînes qui...` | `des motifs, c'est-à-dire des chaînes qui...` |
| `piighost` in code font, lowercase | It is the package name, not a brand splash | `**PIIGhost** est une librairie...` | `` `piighost` est une librairie...`` |
| One term per concept | No elegant variation | alterner « jeton », « token », « marqueur » | choisir *placeholder* et s'y tenir |

Code identifiers stay in English, plain inline code, no colour tag: `ThreadAnonymizationPipeline`, `abefore_model`.

## Efficient, not a novel

Cut narration and scene-setting. The text explains, it does not announce that it is about to explain.

- Drop opener throat-clearing: no « Le principe est simple. », « Plongeons dans... », « Il faut savoir que... ».
- Drop padding tails that restate the sentence: « ce qui permet de raisonner sur les relations entre entités sans jamais manipuler la donnée réelle » collapses to « ce qui permet au modèle de suivre le fil ».
- Describe the real mechanism, not the felt effect: « Quand le LLM retourne des placeholders, `piighost` réinjecte les vraies valeurs » beats « Quand la réponse revient... ».
- One idea per paragraph. If a paragraph has two, split or cut.

## Ground abstractions in one concrete example

Abstract prose reads as flou. Anchor an explanation with a single running example and reuse it throughout.

- Pick one PII and its placeholder, e.g. `jean@mail.com` becomes `<<EMAIL:1>>`, and carry it across the whole passage.
- Tell the trajectory in real order: incoming message, dé-identification, LLM, response, restoration. Show who sees what and when.
- Name the benefit next to the capability: "l'application reste fonctionnelle", "l'utilisateur ne voit jamais la dé-identification".

## Common mistakes (from real drafts)

| Symptom | Fix |
|---|---|
| Reads like a story with a narrator | Delete announcing sentences. State the fact directly. |
| Reader says "c'est flou" | Add one concrete running example (`jean@mail.com` ↔ `<<EMAIL:1>>`). |
| "anonymisation" used for the default pipeline | Replace with "dé-identification". Keep "anonymisation" for irreversible only. |
| Semicolons in French prose | Split into two sentences. |
| `PIIGhost` in bold in body text | Write `` `piighost` `` in code font. |
| Same concept named three different ways | Pick one term, use it everywhere. |

## See also

- `piighost-docs` — the plumbing: Zensical build, `.placeholder` / `.pii` tagging, Mermaid captions, `.wide-table` / `.security-table`, nav, EN/FR mirroring.
- `humanizer` — sentence-level AI-tell removal (rule of three, negative parallelism, filler).
- `README.fr.v2.md` — reference application of this voice on the intro/pitch.
- https://diataxis.fr — the documentation architecture this skill adopts (four modes, one need per page).
- https://docs.langchain.com/oss/python/deepagents — reference example of a good overview page (pyramid, capability-first, code-first, skimmable, links out).
