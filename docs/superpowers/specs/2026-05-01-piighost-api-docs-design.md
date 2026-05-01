# piighost-api documentation bootstrap — design spec

## Goal

Stand up a first iteration of bilingual (EN + FR) documentation for the
`piighost-api` repo, matching the structure and tooling already used by
the `piighost` library: zensical with two configs, mirrored
`docs/en/` and `docs/fr/` trees, dual `README.md` / `README.fr.md`.
Five starter pages, no deploy, local `zensical serve --dev` only.

## Use case

`piighost-api` ships an HTTP API and a Typer CLI. Today the only doc
artefact is a single English `README.md`, which mixes installation,
pipeline configuration, Docker setup, and REST endpoint examples. As
the API surface grows (the new `dataset` subcommand, multiple deploy
targets, several extras), one README is no longer enough, and the
French audience has no entry point at all. This spec lays a doc
foundation that mirrors `piighost` so future iterations can grow inside
the same conventions.

## Non-goals

- Public hosting on GitHub Pages or any other static host. The first
  iteration is local-only via `zensical serve --dev`. Deploy will be a
  separate spec.
- Concepts / architecture / advanced reference pages. The starter set
  is deliberately small.
- Re-documenting the `piighost` library (Anonymizer, Pipeline,
  detectors). Cross-links into the existing `piighost` docs replace
  inline copies.
- Migrating CI badges to point at a deployed doc URL. Placeholder
  links until deploy lands.

## Architecture

The piighost-api repo gains the same dual-config zensical layout as
piighost:

```
piighost-api/
├── README.md                 (refactored, EN, mirrors piighost README pattern)
├── README.fr.md              (new, FR mirror)
├── zensical.toml             (new, EN config)
├── zensical.fr.toml          (new, FR config)
└── docs/
    ├── en/
    │   ├── index.md
    │   ├── getting-started/
    │   │   ├── installation.md
    │   │   └── quickstart.md
    │   └── reference/
    │       ├── endpoints.md
    │       └── cli.md
    └── fr/
        ├── index.md
        ├── getting-started/
        │   ├── installation.md
        │   └── quickstart.md
        └── reference/
            ├── endpoints.md
            └── cli.md
```

Each EN page has a 1-to-1 FR mirror (the `piighost-docs` skill enforces
this). Build is local only:

```
uv tool run zensical serve --dev                        # EN
uv tool run zensical serve --dev --config zensical.fr.toml  # FR
```

## Page contents

### `index.md` (landing)

Two paragraphs and a sequence diagram. The first paragraph names the
project and contrasts it with the `piighost` library: the lib
embeds in your Python process, the API hosts a single pipeline behind
HTTP so multiple processes (chat backend, batch jobs, notebooks) hit
one inference endpoint without re-loading models. The second
paragraph lists the differentiators: thread-scoped memory, API key
auth, Redis cache, configurable pipeline, async client. A Mermaid
sequence diagram shows a chat backend hitting `POST /v1/anonymize`
followed by `POST /v1/deanonymize`. Caption under the diagram per the
`piighost-docs` figure-caption pattern.

### `getting-started/installation.md`

Three install paths in order: `uv add piighost-api` for Python, the
GHCR Docker image for self-hosted, and the `pip install piighost-api`
fallback. Then a sub-section per extra (`langfuse`, `opik`, `dataset`)
explaining what each pulls in and when to use it. Closes with a
sentence pointing at `quickstart.md` for the next step. No long
prose; keep it scannable.

### `getting-started/quickstart.md`

The shortest "from zero to first response" path:

1. Write a minimal `pipeline.py` (regex-only detector, no NER).
2. `piighost-api serve pipeline:pipeline --port 8000`.
3. `curl -X POST http://localhost:8000/v1/anonymize ...`.
4. Output explained.

Mention setting `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (and
`OPIK_API_KEY` as an alternative) is optional. A small box at the end
points at the Docker quickstart in `installation.md` for the
container path.

### `reference/endpoints.md`

One section per endpoint. Each section has:

- HTTP method + path (in a heading)
- One-line description
- Request schema (msgspec struct fields, types, defaults)
- Response schema
- A working `curl` example
- Notes on auth (API key header) and on caching behaviour where
  relevant (e.g. `POST /v1/anonymize` short-circuits the cache)

Endpoints covered:
- `GET /` — index
- `GET /health` — health check
- `GET /v1/config` — labels + factory in use
- `POST /v1/detect` — model-only detection (no anonymisation)
- `PUT /v1/detect` — HITL override of detections
- `POST /v1/anonymize`
- `POST /v1/deanonymize` (cached path)
- `POST /v1/deanonymize/entities` (token-replacement path)

### `reference/cli.md`

Typer CLI reference. Three sub-sections, one per command:

- `piighost-api serve` — args, flags, env vars (`PIIGHOST_PIPELINE`,
  uvicorn pass-through), restart semantics
- `piighost-api dataset extract` — flags, `--mode all|hitl|model-only`
  semantics, `.env` auto-loading via python-dotenv, JSONL schema
- `piighost-api dataset metrics` — flags, `--source` filter,
  `--match-mode strict|lenient`, output formats (table / csv / json)

Closes with a one-line cross-link to `piighost-api dataset extract`'s
JSONL schema (defined in `endpoints.md` could leak into here; keep the
canonical definition here under `dataset extract`).

## Zensical configs

Both configs are the project root, alongside `pyproject.toml`. They
follow the piighost shape:

`zensical.toml` (EN):

```toml
[project]
site_name = "PIIGhost API"
site_url = "https://athroniaeth.github.io/piighost-api/"
site_description = "REST API server for piighost PII anonymization."
site_author = "PIIGhost"
copyright = "Copyright &copy; 2026 PIIGhost contributors"
repo_url = "https://github.com/Athroniaeth/piighost-api"
repo_name = "Athroniaeth/piighost-api"
edit_uri = "edit/master/docs/en/"
docs_dir = "docs/en"

nav = [
  { "Home" = "index.md" },
  { "Get started" = [
    { "Installation" = "getting-started/installation.md" },
    { "Quickstart" = "getting-started/quickstart.md" },
  ]},
  { "Reference" = [
    { "REST endpoints" = "reference/endpoints.md" },
    { "CLI" = "reference/cli.md" },
  ]},
]
```

`zensical.fr.toml` (FR): same shape, `docs_dir = "docs/fr"`,
`edit_uri = "edit/master/docs/fr/"`, French nav titles, French
description.

The `site_url` is a placeholder — no deploy yet, the URL becomes
authoritative when the GitHub Pages workflow lands in a future spec.

## README refactor

`README.md` is reduced to mirror piighost's pattern:

- Header with badges (Python required version, pytest, ruff, uv).
  Drop the very long inline pipeline example currently at the top.
- Cross-link line: `[README EN](README.md) - [README FR](README.fr.md)`
- Cross-link line: `[Documentation EN](https://...) - [Documentation FR](https://.../fr/)`
  (placeholder URLs until deploy)
- Two-paragraph elevator pitch (same content as `docs/en/index.md`)
- One Mermaid sequence diagram (same as `docs/en/index.md`)
- A short "Quick start" section that points at the docs rather than
  duplicating them
- A short "Features" bullet list (the existing one is fine)

`README.fr.md` is a verbatim FR mirror.

## Conventions and constraints

- The `piighost-docs` skill (declared in `~/.claude/CLAUDE.md`) applies
  to every page. EN/FR mirroring is mandatory.
- Mermaid diagrams use the project's existing style (no custom
  `<figcaption>` HTML for the simplest cases; piighost uses
  `<figure>` + `<figcaption>` blocks for non-trivial diagrams; mirror
  whatever piighost does on a per-page basis).
- No `.placeholder` / `.pii` / `.security-table` styling on these
  starter pages (they target text-heavy reference content). Future
  pages can add styling when needed.
- Do not commit a `stylesheets/` directory yet. If a page needs custom
  CSS later, add it then.
- All commit messages follow the `docs(...)` Conventional Commits
  prefix.

## Verification

After implementation, the following must succeed locally:

1. `uv tool run zensical serve --dev` starts an HTTP server with the
   English nav, all five pages reachable, no broken links.
2. `uv tool run zensical serve --dev --config zensical.fr.toml` starts
   an HTTP server with the French nav, same pages reachable, no
   broken links.
3. Each EN page has a French sibling at the same relative path.
4. The dual README files cross-link each other and link the (placeholder)
   doc URLs.

No automated test for now. Doc rendering is verified by eye in the
local preview.

## Out of scope (future iterations)

- Public deploy via GitHub Pages workflow (`piighost` has it; copy when
  ready, separate spec).
- `architecture.md`, `glossary.md`, `deployment.md`, `security.md`,
  `extending.md` — only when the corresponding code surface stabilises.
- Auto-generated reference from msgspec structs or from the OpenAPI
  spec exposed by Litestar at `/schema/swagger`. The first iteration
  hand-writes endpoint docs; we evaluate auto-generation later.
- Stylesheets, themes, custom shortcodes.
- Translation tooling. The FR mirror is hand-maintained; if drift
  becomes a problem we add tooling later.
