# Chat de-identification animation

Source for the animation shown on the documentation home page and in the
READMEs: a chat where PII values are replaced by placeholders before reaching
the model, then restored for the user and for the tool calls.

## Files

- `generate_animation.py` renders the animation as two self-contained SVG files
  (light + dark), pure CSS keyframes and no JavaScript, in the piighost charter
  (version 3): its tokens, read in oklch and converted, its fonts, its radius,
  one chip colour per category, the same for a value and its placeholder, and
  its lock-up on the title card. Glyph widths are measured from the vendored
  fonts, so the geometry is exact for the chosen language, and the SVG embeds
  the subset of the fonts it draws, since an SVG shown through `<img>` reaches
  no font of the page.
- `svg2gif.py` rasterizes an animated SVG to an animated GIF. GitHub strips the
  CSS animation out of an inline SVG, so the READMEs need a GIF, while the
  documentation site keeps the animated SVG, light and dark. The READMEs are
  read by developers and show the dark one only, the charter's default.
- `fonts/` holds Schibsted Grotesk Regular, a static instance of the variable
  font, and IBM Plex Mono Regular, all under the SIL Open Font License,
  with the license texts alongside.
- `logo/` holds the charter's horizontal lock-up, light and negative.

## Regenerate

Both scripts carry PEP 723 inline metadata, so `uv run` resolves their
dependencies on its own.

```bash
# Animated SVGs, one light/dark pair per language
uv run --no-project docs/tools/generate_animation.py --lang en --out docs/en/assets
uv run --no-project docs/tools/generate_animation.py --lang fr --out docs/fr/assets

# Dark GIFs for the READMEs, with the dark background and its field of dots
uv run --no-project docs/tools/svg2gif.py docs/en/assets/deid-chat-dark.svg docs/assets/deid-chat-dark.gif    --bg "#080d0f" --dots "#2f3436"
uv run --no-project docs/tools/svg2gif.py docs/fr/assets/deid-chat-dark.svg docs/assets/deid-chat-fr-dark.gif --bg "#080d0f" --dots "#2f3436"
```

The two colours are the dark `--background` and its dots, as `palette("dark")`
of `generate_animation.py` computes them from the tokens.

`svg2gif.py` draws the text with cairosvg, which needs the two fonts available
system-wide to reproduce the SVG geometry (otherwise it falls back to a default
font). Install them once:

```bash
cp docs/tools/fonts/*.ttf ~/.local/share/fonts/ && fc-cache -f
```
