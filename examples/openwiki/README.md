# OpenWiki brief and writing skills

The files used to generate the French wiki in [`openwiki/`](../../openwiki/quickstart.md) with [OpenWiki](https://github.com/langchain-ai/openwiki) 0.6.1, driven from Claude Code. They are kept here as an example of a custom brief, not as project conventions: the project's own skills live in [`skills/`](../../skills).

| File | Role |
|---|---|
| `INSTRUCTIONS.md` | The brief OpenWiki reads from `openwiki/INSTRUCTIONS.md`: audience (business readers first, then developers), mandatory page structure, business rules numbered `RG-<DOMAIN>-NN`, doc/code discrepancy register, style rules. Written in French. |
| `skills/rediger-doc/` | Writing skill the brief asks the host to use for each page, with one reference per document type (business doc, technical doc, README) and a shared style guide. |
| `skills/custom-humanizer/` | Final-review skill, used in its light "Retoucher" mode. `scripts/verifier_sens.py` compares a text and its rewrite and reports lost or added numbers, inline code and URLs. |

## Reproduce the run

```bash
npm install -g openwiki@0.6.1
openwiki integrations install claude
cp -r examples/openwiki/skills/* ~/.claude/skills/
cp examples/openwiki/INSTRUCTIONS.md openwiki/INSTRUCTIONS.md
```

Restart Claude Code in the repository, then ask: "Initialize OpenWiki for this repository." The skills go to `~/.claude/skills/` rather than the project's `.claude/skills`, which links to the tracked `skills/` folder, and `custom-humanizer` calls its script at that absolute path.

## What to expect

The brief targets applications with screens. PIIGhost is a library with none, so the run read "screen labels" as the visible outputs (tokens, error messages, CLI output, configuration keys) and invented no navigation path. Business procedures therefore often end with "ask the technical team". The doc/code register it produced is in [`openwiki/reference/ecarts-doc-code.md`](../../openwiki/reference/ecarts-doc-code.md).
