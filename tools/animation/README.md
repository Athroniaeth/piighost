# Chat de-identification animation

Source for the animation shown on the documentation home page and in the
READMEs: a chat where PII values are replaced by placeholders before reaching
the model, then restored for the user and for the tool calls.

## Files

- `generate_animation.py` renders the animation as two self-contained SVG files
  (light + dark), pure CSS keyframes and no JavaScript. Glyph widths are
  measured from the vendored fonts, so the geometry is exact for the chosen
  language, and changing the text recomputes it.
- `svg2gif.py` rasterizes an animated SVG to an animated GIF. GitHub strips the
  CSS animation out of an inline SVG, so the READMEs need a GIF, while the
  documentation site keeps the animated SVG.
- `fonts/` holds Space Grotesk Medium and JetBrains Mono Regular, both under the
  SIL Open Font License, with the license texts alongside.

## Regenerate

Both scripts carry PEP 723 inline metadata, so `uv run` resolves their
dependencies on its own.

```bash
# Animated SVGs, one light/dark pair per language
uv run --no-project tools/animation/generate_animation.py --lang en --out docs/en/assets
uv run --no-project tools/animation/generate_animation.py --lang fr --out docs/fr/assets

# GIFs for the READMEs, page background baked in per colour scheme
uv run --no-project tools/animation/svg2gif.py docs/en/assets/deid-chat-light.svg docs/assets/deid-chat-light.gif    --bg "#FFFFFF"
uv run --no-project tools/animation/svg2gif.py docs/en/assets/deid-chat-dark.svg  docs/assets/deid-chat-dark.gif     --bg "#151A24"
uv run --no-project tools/animation/svg2gif.py docs/fr/assets/deid-chat-light.svg docs/assets/deid-chat-fr-light.gif --bg "#FFFFFF"
uv run --no-project tools/animation/svg2gif.py docs/fr/assets/deid-chat-dark.svg  docs/assets/deid-chat-fr-dark.gif  --bg "#151A24"
```

`svg2gif.py` draws the text with cairosvg, which needs the two fonts available
system-wide to reproduce the SVG geometry (otherwise it falls back to a default
font). Install them once:

```bash
cp tools/animation/fonts/*.ttf ~/.local/share/fonts/ && fc-cache -f
```
