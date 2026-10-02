# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools>=4.50", "brotli>=1.1"]
# ///
"""Render the de-identification chat animation as animated SVG files.

A user writes to an agent. Each confidential value is replaced by its
placeholder before the model reads it, and restored on the way back, for the
user and for the tool the agent calls. Pure CSS keyframes, no JavaScript.

The look is the piighost charter, version 3, the one the sites wear: Schibsted
Grotesk and IBM Plex Mono, the 0.25rem radius, grey for structure, the primary
for the product's own gesture (the sweep of a swap, the tool call), and a hue
per category of value. A value and its placeholder wear the same chip: the text
alone says which is which, as on every surface of the charter.
"""

import argparse
import base64
import io
import math
import os
import re
from pathlib import Path
from typing import Any

from fontTools import subset
from fontTools.ttLib import TTFont

Palette = dict[str, str]
Segment = tuple[str, Any]
Row = dict[str, Any]

# The chat is preceded by a title card (INTRO seconds), the logo and the key
# phrase, and a system-prompt card (SYS_GAP seconds) shown before the first user
# message. Both push the chat timeline later, so the loop and the fade-out grow
# by the same offset and every relative timing is preserved.
INTRO = 2.8
SYS_GAP = 1.7
OFFSET = INTRO + SYS_GAP
LOOP = 24.0 + OFFSET
FADE_OUT = 22.0 + OFFSET
W = 760
GAP_ROWS = 16.0

HERE = Path(__file__).resolve().parent
FONT_DIR = Path(os.environ.get("FONT_DIR", str(HERE / "fonts")))
SANS = "'Schibsted Grotesk',system-ui,sans-serif"
MONO = "'IBM Plex Mono',ui-monospace,monospace"
FS, FSM, FSC = 13.5, 12.0, 12.0

RADIUS = 4.0
"""--radius, 0.25rem: chips, code blocks and cards."""

RADIUS_XL = RADIUS + 4.0
"""shadcn's --radius-xl, the bubbles."""


# ------------------------------------------------------------------ colours
def oklch(
    lightness: float, chroma: float, hue_deg: float
) -> tuple[float, float, float]:
    """An oklch colour as linear-light sRGB, clipped to the gamut."""
    a = chroma * math.cos(math.radians(hue_deg))
    b = chroma * math.sin(math.radians(hue_deg))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        +4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    return tuple(min(max(x, 0.0), 1.0) for x in rgb)  # type: ignore[return-value]


def _encode(linear: float) -> float:
    return (
        12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    )


def hexa(rgb: tuple[float, float, float]) -> str:
    """Linear-light sRGB as a #rrggbb string."""
    return "#" + "".join(f"{round(_encode(x) * 255):02x}" for x in rgb)


def over(
    top: tuple[float, float, float], alpha: float, ground: tuple[float, float, float]
) -> str:
    """A translucent colour laid on its ground, blended in sRGB as a browser does."""
    mixed = [
        alpha * _encode(t) + (1 - alpha) * _encode(g)
        for t, g in zip(top, ground, strict=True)
    ]
    return "#" + "".join(f"{round(x * 255):02x}" for x in mixed)


def _oklch_css(text: str) -> str:
    """Every oklch() of a file as hex, for renderers that do not read oklch."""
    return re.sub(
        r"oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)",
        lambda m: hexa(oklch(*map(float, m.groups()))),
        text,
    )


Oklch = tuple[float, float, float]

# The values of the charter's tokens.css (piighost-identite, brand/tokens),
# written as there, converted here: a hex copied by hand drifts from its source.
TOKENS: dict[str, dict[str, Oklch]] = {
    "light": {
        "background": (0.978, 0.002, 220),
        "foreground": (0.17, 0.012, 220),
        "card": (0.996, 0.001, 220),
        "muted": (0.952, 0.002, 220),
        "mutedForeground": (0.50, 0.008, 220),
        "border": (0.862, 0.005, 220),
        "primary": (0.51, 0.23, 277),
    },
    "dark": {
        "background": (0.155, 0.010, 220),
        "foreground": (0.962, 0.002, 220),
        "card": (0.198, 0.011, 220),
        "muted": (0.262, 0.010, 220),
        "mutedForeground": (0.715, 0.009, 220),
        "border": (0.99, 0.002, 220),
        "primary": (0.62, 0.19, 277),
    },
}

BORDER_ALPHA = {"light": 1.0, "dark": 0.16}
"""The dark border is translucent, oklch(0.99 0.002 220 / 16%), over the card it outlines."""

ENTITIES: dict[str, list[tuple[Oklch, Oklch]]] = {
    "light": [
        ((0.935, 0.0328, 27), (0.53, 0.15, 27)),
        ((0.935, 0.0386, 55), (0.52, 0.1288, 55)),
    ],
    "dark": [
        ((0.305, 0.068, 27), (0.69, 0.13, 27)),
        ((0.305, 0.068, 55), (0.68, 0.13, 55)),
    ],
}
"""The tint and text of the chips of entities 01 and 02, the two the scene uses."""

DOTS = {"light": 0.13, "dark": 0.17}
"""The field of dots behind the interface: the foreground at this opacity."""


def palette(theme: str) -> Palette:
    """The colours of one theme, as hex."""
    t = TOKENS[theme]
    colours = {key: hexa(oklch(*value)) for key, value in t.items()}
    colours["border"] = over(
        oklch(*t["border"]), BORDER_ALPHA[theme], oklch(*t["card"])
    )
    for number, (tint, ink) in enumerate(ENTITIES[theme], start=1):
        colours[f"e{number}Bg"], colours[f"e{number}"] = (
            hexa(oklch(*tint)),
            hexa(oklch(*ink)),
        )
    colours["dots"] = over(
        oklch(*t["foreground"]), DOTS[theme], oklch(*t["background"])
    )
    return colours


def chip(C: Palette, hue: int) -> tuple[str, str]:
    """The text and tint of the chip of a category, by its hue in this run."""
    return C[f"e{hue}"], C[f"e{hue}Bg"]


# ------------------------------------------------------------------ CSS engine
KF, CL, _uid = [], [], [0]


def _n(p: str) -> str:
    """Return a fresh CSS class name with the prefix p."""
    _uid[0] += 1
    return f"{p}{_uid[0]}"


def pc(t: float) -> float:
    """Convert a time in seconds into a percentage of the loop, clamped."""
    return round(max(0.0, min(t, LOOP)) / LOOP * 100, 3)


def cls_appear(
    tin: float, tout: float = FADE_OUT, dy: float = 7.0, ramp: float = 0.40
) -> str:
    """Class that fades and slides an element in at tin and out at tout."""
    n = _n("e")
    KF.append(
        f"@keyframes {n}{{0%,{pc(tin)}%{{opacity:0;transform:translateY({dy:.1f}px)}}"
        f"{pc(tin + ramp)}%,{pc(tout)}%{{opacity:1;transform:translateY(0)}}"
        f"{pc(tout + 0.55)}%,100%{{opacity:0}}}}"
    )
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite}}")
    return n


# Timeline of a swap, in seconds from the swap instant. The order matters: the
# old value fades and the room is made BEFORE the new one arrives, otherwise
# the end of the line slides over the incoming text.
SW_OUT, SW_GAP, SW_IN, SW_END = 0.10, 0.26, 0.28, 0.46


def cls_out(tin: float, tswap: float, ramp: float = 0.38) -> str:
    """Class of the state visible until the swap."""
    n = _n("o")
    KF.append(
        f"@keyframes {n}{{0%,{pc(tin)}%{{opacity:0}}{pc(tin + ramp)}%,{pc(tswap + SW_OUT)}%{{opacity:1}}{pc(tswap + SW_GAP)}%,100%{{opacity:0}}}}"
    )
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite}}")
    return n


def cls_in(tswap: float, tout: float = FADE_OUT) -> str:
    """Class of the state that takes over after the sweep."""
    n = _n("i")
    KF.append(
        f"@keyframes {n}{{0%,{pc(tswap + SW_IN)}%{{opacity:0}}{pc(tswap + SW_END)}%,{pc(tout)}%{{opacity:1}}{pc(tout + 0.55)}%,100%{{opacity:0}}}}"
    )
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite}}")
    return n


def cls_sweep(tswap: float, dist: float, dur: float | None = None) -> str:
    """Class of the thin bar that sweeps across a pill during the swap."""
    n = _n("w")
    tswap, dur = tswap + SW_OUT, (SW_END - SW_OUT) if dur is None else dur
    KF.append(
        f"@keyframes {n}{{0%,{pc(tswap)}%{{opacity:0;transform:translateX(0)}}"
        f"{pc(tswap + 0.05)}%{{opacity:1;transform:translateX(0)}}"
        f"{pc(tswap + dur - 0.05)}%{{opacity:1;transform:translateX({dist:.1f}px)}}"
        f"{pc(tswap + dur)}%,100%{{opacity:0;transform:translateX({dist:.1f}px)}}}}"
    )
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite}}")
    return n


SCROLL_DUR = 0.55


def cls_scroll(steps: list[tuple[float, float]]) -> str:
    """Class that scrolls the thread, from (instant, height pushed out) steps.

    The offset is cumulative and never goes back. The two intermediate points
    mimic a deceleration: interpolation stays linear between keyframes, so the
    render is identical in a browser and in the GIF, which a CSS easing
    function would not guarantee.
    """
    n = _n("y")
    cum, out = 0.0, ["0%{transform:translateY(0px)}"]
    for t, dy in steps:
        for frac, off in ((0.0, 0.0), (0.40, 0.68), (0.70, 0.92), (1.0, 1.0)):
            out.append(
                f"{pc(t + frac * SCROLL_DUR)}%{{transform:translateY({-(cum + off * dy):.2f}px)}}"
            )
        cum += dy
    out.append(f"100%{{transform:translateY({-cum:.2f}px)}}")
    KF.append("@keyframes {}{{{}}}".format(n, "".join(out)))
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite;--dy:{-cum:.2f}px}}")
    return n


def _kf(name: str, stops: list[tuple[tuple[float, float], str]]) -> None:
    """Build keyframes from a list of ((start%, end%), properties).

    The explicit form leaves no risk of swapping positional arguments.
    """
    KF.append(
        "@keyframes {}{{{}}}".format(
            name, "".join(f"{a}%,{b}%{{{props}}}" for (a, b), props in stops)
        )
    )


def cls_tail(
    tin: float, tswap: float, dx: float, tout: float = FADE_OUT, ramp: float = 0.40
) -> str:
    """Class of the end of a line, which shifts while the new pill appears.

    Shifting at any other moment makes it arrive alone and look adrift.
    """
    n = _n("t")
    at = f"opacity:1;transform:translate({dx:.2f}px,0px)"
    _kf(
        n,
        [
            ((0.0, pc(tin)), "opacity:0;transform:translate(0px,7px)"),
            (
                (pc(tin + ramp), pc(tswap + SW_OUT)),
                "opacity:1;transform:translate(0px,0px)",
            ),
            ((pc(tswap + SW_GAP + 0.02), pc(tout)), at),
            (
                (pc(tout + 0.55), 100.0),
                f"opacity:0;transform:translate({dx:.2f}px,0px)",
            ),
        ],
    )
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite;--dx:{dx:.2f}px}}")
    return n


def _window(tswap: float, early: bool) -> tuple[float, float]:
    """Make room early and take it back late.

    The bubble is thus never smaller than its content during the transition.
    """
    return (
        (tswap + SW_OUT, tswap + SW_GAP + 0.02)
        if early
        else (tswap + SW_IN, tswap + SW_END)
    )


def cls_slide(tswap: float, dx: float) -> str:
    """Class of a horizontal slide: the bubble sits on the right, content follows."""
    n = _n("t")
    t0, t1 = _window(tswap, dx < 0)
    KF.append(
        f"@keyframes {n}{{0%,{pc(t0)}%{{transform:translateX(0)}}"
        f"{pc(t1)}%,100%{{transform:translateX({dx:.2f}px)}}}}"
    )
    CL.append(f".{n}{{animation:{n} {LOOP}s linear infinite;--dx:{dx:.2f}px}}")
    return n


def cls_scale(tswap: float, sx: float, origin: str) -> str:
    """Class that shrinks or stretches a bubble, the opposite edge fixed."""
    n = _n("k")
    t0, t1 = _window(tswap, sx > 1.0)  # widening: right from the start
    KF.append(
        f"@keyframes {n}{{0%,{pc(t0)}%{{transform:scaleX(1)}}"
        f"{pc(t1)}%,100%{{transform:scaleX({sx:.4f})}}}}"
    )
    CL.append(
        f".{n}{{animation:{n} {LOOP}s linear infinite;transform-box:fill-box;"
        f"transform-origin:{origin} center;--sx:{sx:.4f}}}"
    )
    return n


# ------------------------------------------------------------------ text
def esc(s: str) -> str:
    """Escape a text for XML."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# The widths come from the font file itself. An advance table frozen in the code
# would have to be redone at every font change, and a chip too narrow overflows
# its bubble while the SVG stays valid: the fault only shows to the eye.
def _face(name: str) -> tuple[dict[str, float], dict[str, float]]:
    """Read the advance widths and left side bearings of a font, in em."""
    f = TTFont(str(FONT_DIR / name))
    upem = float(f["head"].unitsPerEm)
    hm, cmap = f["hmtx"], f.getBestCmap()
    adv = {chr(c): hm.metrics[n][0] / upem for c, n in cmap.items() if n in hm.metrics}
    lsb = {chr(c): hm.metrics[n][1] / upem for c, n in cmap.items() if n in hm.metrics}
    return adv, lsb


SANS_FILE, MONO_FILE = "SchibstedGrotesk-Regular.ttf", "IBMPlexMono-Regular.ttf"
_SADV, _SLSB = _face(SANS_FILE)
_MADV, _MLSB = _face(MONO_FILE)


def w_sans(s: str, fs: float = FS) -> float:
    """Real width of the text (+0.5 %: cairo rounds at the subpixel)."""
    return sum(_SADV.get(c, 0.55) for c in s) * fs * 1.005


def w_mono(s: str, fs: float | None = None) -> float:
    """Real width of a monospace text at font size fs."""
    fs = FSM if fs is None else fs
    return sum(_MADV.get(c, 0.6) for c in s) * fs * 1.005


PAD, PILL_H, LEAD = 4.0, 19.0, 4.5
PAD_X = 14.0  # horizontal padding of the bubbles


def pill_w(v: str, fs: float | None = None) -> float:
    """Width of a chip holding the value v."""
    return w_mono(v, fs) + 2 * PAD


_PUNCT = (",", ".", ")", ";", ":", "?", "!")


def gap_after(nxt: tuple[str, str], last: bool = False) -> float:
    """Gap after a fragment, given the next fragment nxt as (kind, text).

    A chip already carries its inner padding on its right, and the comma that
    follows adds its left side bearing: the sign ends up floating far from the
    word. Both are subtracted to stick it back. Only in running text: in the
    code block the closing parenthesis must stay readable next to the value.
    """
    kind, txt = nxt
    if last:
        return 0.0
    if txt[:1] not in _PUNCT:
        return 3.5
    return 0.5 - PAD - _SLSB.get(txt[0], 0.0) * FS if kind == "t" else 0.0


OUT: list[str] = []
_CAP: list[list[str] | None] = [None]
SHOWN: set[str] = set()
"""Every character drawn, per font, to subset the fonts the SVG embeds."""
SHOWN_MONO: set[str] = set()


def add(s: str) -> None:
    """Append an SVG fragment to the output, or to the open capture buffer."""
    (OUT if _CAP[0] is None else _CAP[0]).append(s)


def text(
    x: float,
    y: float,
    s: str,
    C: Palette,
    *,
    mono: bool = False,
    fs: float | None = None,
    fill: str | None = None,
    weight: int | None = None,
) -> str:
    """One run of text, its characters noted for the embedded fonts."""
    (SHOWN_MONO if mono else SHOWN).update(s)
    size = fs if fs is not None else (FSM if mono else FS)
    bold = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO if mono else SANS}" font-size="{size}"{bold} '
        f'fill="{fill or C["foreground"]}">{esc(s)}</text>'
    )


def swap_pill(
    x: float,
    y: float,
    va: str,
    vb: str,
    hue: int,
    t_in: float,
    t_swap: float,
    C: Palette,
    fs: float,
) -> tuple[float, float]:
    """A chip with two stacked texts, the value and its placeholder. Return both widths.

    Both wear the category's colours: the charter marks no state, only the
    category. The swap itself is the product's gesture, a sweep in the primary.
    """
    ink, tint = chip(C, hue)
    wa, wb = pill_w(va, fs), pill_w(vb, fs)

    def state(txt: str, wd: float, cls: str) -> str:
        return (
            f'<g class="{cls}"><rect x="{x:.1f}" y="{y - 13.5:.1f}" width="{wd:.1f}" height="{PILL_H:.1f}" '
            f'rx="{RADIUS:.0f}" fill="{tint}"/>{text(x + PAD, y, txt, C, mono=True, fs=fs, fill=ink)}</g>'
        )

    add(state(va, wa, cls_out(t_in, t_swap)))
    add(state(vb, wb, cls_in(t_swap)))
    add(
        f'<g class="{cls_sweep(t_swap, wb - 3.0)}"><rect x="{x:.1f}" y="{y - 13.5:.1f}" width="3" '
        f'height="{PILL_H:.1f}" rx="1.5" fill="{C["primary"]}"/></g>'
    )
    return wa, wb


def _next_seg(segs: list[Segment], i: int) -> tuple[str, str]:
    """Return the segment after index i as (kind, text), a chip's text empty."""
    for k, v in segs[i + 1 :]:
        return (k, v if isinstance(v, str) else "")
    return ("t", "")


def _shown(val: tuple[str, str, int], token: bool) -> str:
    return val[1] if token else val[0]


def line_w(
    segs: list[Segment],
    states: tuple[bool, bool],
    which: str = "a",
    fs_mono: float = FSM,
) -> float:
    """Width of the line before the swap (a) or after it (b).

    states says, before and after the swap, whether a chip shows the placeholder.
    """
    token = states[0] if which == "a" else states[1]
    tot = 0.0
    for i, (kind, val) in enumerate(segs):
        g = gap_after(_next_seg(segs, i), i == len(segs) - 1)
        if kind == "s":
            tot += LEAD + pill_w(_shown(val, token), fs_mono) + g
        elif kind == "t":
            tot += w_sans(val)
        else:
            tot += w_mono(val, fs_mono)
    return tot


def render_line(
    x: float,
    y: float,
    segs: list[Segment],
    C: Palette,
    t_in: float,
    swaps: list[float],
    states: tuple[bool, bool],
    shift: bool = False,
    fs_mono: float = FSM,
) -> None:
    """Render one line of a message.

    Args:
        x: Left edge of the line.
        y: Text baseline of the line.
        segs: Segments of the line, as (kind, value) pairs: "t" text, "m" muted
            mono, "v" code name, "s" a value, (clear, placeholder, hue).
        C: Colour palette.
        t_in: Instant the line appears.
        swaps: Swap instants, consumed in order by the chips.
        states: Whether a chip shows the placeholder, before and after its swap.
        shift: Whether the end of the line follows the chip's width.
        fs_mono: Font size of the monospace text.
    """
    cur, dx, tail_open = x, 0.0, False
    plain, tail = [], []
    si = 0
    for i, (kind, val) in enumerate(segs):
        g = gap_after(_next_seg(segs, i), i == len(segs) - 1)
        if kind == "s":
            ts = swaps[si] if si < len(swaps) else LOOP * 2
            si += 1
            wa, wb = swap_pill(
                cur + LEAD,
                y,
                _shown(val, states[0]),
                _shown(val, states[1]),
                val[2],
                t_in,
                ts,
                C,
                fs_mono,
            )
            if shift:
                dx = wb - wa
                tail_open = True
            cur += LEAD + wa + g
            continue
        if kind == "t":
            wd, frag = w_sans(val), text(cur, y, val, C)
        elif kind == "m":
            wd, frag = (
                w_mono(val, fs_mono),
                text(cur, y, val, C, mono=True, fs=fs_mono, fill=C["mutedForeground"]),
            )
        else:
            wd, frag = w_mono(val, fs_mono), text(cur, y, val, C, mono=True, fs=fs_mono)
        (tail if tail_open else plain).append(frag)
        cur += wd
    # plain text appears with the message, it must not be static
    if plain:
        add('<g class="{}">{}</g>'.format(cls_appear(t_in), "".join(plain)))
    if tail:
        ts = swaps[0] if swaps else LOOP * 2
        add('<g class="{}">{}</g>'.format(cls_tail(t_in, ts, dx), "".join(tail)))


# ------------------------------------------------------------------ avatars
def draw_avatar(kind: str, x: float, y: float, C: Palette, tin: float) -> str:
    """The person or the assistant: grey, since neither is data nor the product."""
    cls = cls_appear(tin, dy=4)
    ground = f'<rect x="{x:.1f}" y="{y:.1f}" width="28" height="28" rx="{RADIUS:.0f}" fill="{C["muted"]}"/>'
    ink = C["mutedForeground"]
    if kind == "human":
        glyph = (
            f'<circle cx="{x + 14:.1f}" cy="{y + 10.8:.1f}" r="3.6" fill="{ink}"/>'
            f'<path d="M{x + 8.1:.1f} {y + 21.6:.1f} a5.9 5.9 0 0 1 11.8 0 z" fill="{ink}"/>'
        )
    else:  # a four-point spark, drawn in strokes so it reads at 28px
        cx, cy = x + 14, y + 14
        glyph = (
            f'<path d="M{cx:.1f} {cy - 7:.1f} Q{cx + 1:.1f} {cy - 1:.1f} {cx + 7:.1f} {cy:.1f} '
            f"Q{cx + 1:.1f} {cy + 1:.1f} {cx:.1f} {cy + 7:.1f} Q{cx - 1:.1f} {cy + 1:.1f} {cx - 7:.1f} {cy:.1f} "
            f'Q{cx - 1:.1f} {cy - 1:.1f} {cx:.1f} {cy - 7:.1f} Z" fill="{ink}"/>'
        )
    return f'<g class="{cls}">{ground}{glyph}</g>'


# ------------------------------------------------------------------ scenario
NAME_R, NAME_M = "Marie Dupont", "<<PERSON:1>>"
MAIL_R, MAIL_M = "marie.dupont@acme.fr", "<<EMAIL:1>>"
NAME, MAIL = (NAME_R, NAME_M, 1), (MAIL_R, MAIL_M, 2)
"""The two values, with the hue their category takes by first appearance."""

CLEAR_TO_TOKEN, TOKEN_TO_CLEAR, CLEAR = (False, True), (True, False), (False, False)

_BASE = {
    "m1": 0.9,
    "s1": 2.6,
    "s2": 2.95,
    "m2": 4.7,
    "s3": 6.4,
    "m3": 8.4,
    "m4": 10.0,
    "m5": 12.6,
    "m6": 14.4,
    "code": 15.2,
    "s4": 17.0,
}
T = {"sys": round(INTRO + 0.8, 3)}
T.update({k: round(v + OFFSET, 3) for k, v in _BASE.items()})

# Four bubbles fit in the frame. The last two push the first two out of view:
# the conversation scrolls as in a real interface.
VISIBLE = 4

LANGS = {
    "en": {
        "aria": "Confidential values are replaced by placeholders before reaching the model, "
        "then restored for the user and for tool calls",
        "phrase": ("Everything the model can do.", "Nothing it doesn't need to know."),
        "greet_user": "Hi, I'm",
        "email_intro": ", my email is",
        "greet_ai": "Hello",
        "help_offer": ", how can I help?",
        "ask": "What's the first letter of my first name?",
        "refuse": "I can't tell, that name never reaches me.",
        "request": "Can you email me the summary?",
        "confirm": "Sure, sending it now.",
        "sys_tag": "System prompt",
        "sys": (
            "You are a support assistant. A value that looks like personal",
            "data is already a placeholder: never guess the real one…",
        ),
    },
    "fr": {
        "aria": "Les valeurs confidentielles sont remplacées par des placeholders avant "
        "d'atteindre le modèle, puis restaurées pour l'utilisateur et pour les appels d'outils",
        "phrase": (
            "Tout ce que le modèle sait faire,",
            "rien de ce qu'il n'a pas à savoir.",
        ),
        "greet_user": "Bonjour, je suis",
        "email_intro": ", mon email est",
        "greet_ai": "Bonjour",
        "help_offer": ", comment puis-je aider ?",
        "ask": "Quelle est la première lettre de mon prénom ?",
        "refuse": "Je ne peux pas, ce nom ne m'arrive jamais.",
        "request": "Peux-tu m'envoyer le résumé par email ?",
        "confirm": "Bien sûr, je l'envoie.",
        "sys_tag": "Prompt système",
        "sys": (
            "Tu es un assistant support. Une valeur qui ressemble à une donnée",
            "personnelle est déjà un placeholder : ne devine jamais la vraie…",
        ),
    },
}


def make_rows(L: dict[str, Any]) -> list[Row]:
    """Build the message script for one language from its localized strings."""
    return [
        {
            "role": "system",
            "tin": "sys",
            "states": CLEAR,
            "swaps": [],
            "system_tag": L["sys_tag"],
            "lines": [[("t", L["sys"][0])], [("t", L["sys"][1])]],
        },
        {
            "role": "human",
            "tin": "m1",
            "states": CLEAR_TO_TOKEN,
            "swaps": ["s1", "s2"],
            "lines": [
                [
                    ("t", L["greet_user"]),
                    ("s", NAME),
                    ("t", L["email_intro"]),
                    ("s", MAIL),
                ]
            ],
        },
        {
            "role": "ai",
            "tin": "m2",
            "states": TOKEN_TO_CLEAR,
            "swaps": ["s3"],
            "lines": [[("t", L["greet_ai"]), ("s", NAME), ("t", L["help_offer"])]],
        },
        {
            "role": "human",
            "tin": "m3",
            "states": CLEAR_TO_TOKEN,
            "swaps": [],
            "lines": [[("t", L["ask"])]],
        },
        {
            "role": "ai",
            "tin": "m4",
            "states": TOKEN_TO_CLEAR,
            "swaps": [],
            "lines": [[("t", L["refuse"])]],
        },
        {
            "role": "human",
            "tin": "m5",
            "states": CLEAR_TO_TOKEN,
            "swaps": [],
            "lines": [[("t", L["request"])]],
        },
        {
            "role": "ai",
            "tin": "m6",
            "states": TOKEN_TO_CLEAR,
            "swaps": [],
            "lines": [[("t", L["confirm"])]],
            "code": [("v", "send_email"), ("m", "(to="), ("s", MAIL), ("m", ")")],
        },
    ]


CODE_TOP = 28.0  # from the top of the bubble: tight space under the text
CODE_H = 30.0


def row_w(r: Row, which: str) -> float:
    """Width of the widest line of the row r before or after its swap."""
    ws = [line_w(line, r["states"], which) for line in r["lines"]]
    if "code" in r:
        ws.append(line_w(r["code"], r["states"], which, FSC) + 40)
    return max(ws)


def _logo(theme: str, x: float, y: float, height: float) -> str:
    """The charter's lock-up, the light one or its negative, as a nested SVG."""
    name = "horizontal.svg" if theme == "light" else "horizontal-negatif.svg"
    src = _oklch_css((HERE / "logo" / name).read_text(encoding="utf-8"))
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', src)
    if box is None:
        raise ValueError(f"{name} has no viewBox")
    vw, vh = float(box.group(1)), float(box.group(2))
    width = height * vw / vh
    # The lock-up's ids would collide with the other theme's on one page.
    src = re.sub(r'(id="|url\(#)(\w+)', rf"\1\2-{theme}", src)
    inner = src[src.index(">") + 1 : src.rindex("</svg>")]
    return (
        f'<svg x="{x - width / 2:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {vw} {vh}">{inner}</svg>'
    )


def _font_face(family: str, file: str, chars: set[str]) -> str:
    """A @font-face holding only the glyphs drawn, as an inline woff2.

    An SVG shown through <img> reaches no font of the page: without its own, a
    browser draws the fallback and the measured geometry falls apart.
    """
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga"]
    font = subset.load_font(str(FONT_DIR / file), options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(text="".join(chars) + " ")
    subsetter.subset(font)
    buffer = io.BytesIO()
    subset.save_font(font, buffer, options)
    data = base64.b64encode(buffer.getvalue()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2')}}"


def build(C: Palette, theme: str, rows: list[Row], lang: dict[str, Any]) -> str:
    """Render the whole animation for one theme as an SVG document."""
    OUT[:], KF[:], CL[:] = [], [], []
    SHOWN.clear()
    SHOWN_MONO.clear()
    _uid[0] = 0
    _CAP[0] = None
    y = 26.0

    geom = []
    for r in rows:
        tin = T[r["tin"]]
        has_code = "code" in r
        swaps = [T[x] for x in r["swaps"]]
        st = r["states"]

        WA, WB = row_w(r, "a"), row_w(r, "b")
        bw, bw_b = WA + 2 * PAD_X, WB + 2 * PAD_X
        delta = WA - WB  # > 0: the content tightens
        resize = abs(delta) > 0.5
        t_resize = swaps[-1] if swaps else T["s4"]
        h = (len(r["lines"]) - 1) * 20 + 38 + (CODE_H + 2 if has_code else 0)
        if r["role"] == "system":
            h = 30 + len(r["lines"]) * 19 + 6

        if r["role"] == "ai":
            bx, ax, origin = 64.0, 24.0, "left"
        elif r["role"] == "human":
            bx, ax, origin = W - 64 - bw, W - 52.0, "right"
        else:  # system: a left-aligned card, no avatar
            bx, ax, origin = 24.0, None, "left"

        if ax is not None:
            add(
                draw_avatar(
                    "human" if r["role"] == "human" else "ai", ax, y + 5, C, tin
                )
            )

        if r["role"] == "human":
            shell = (
                f'<rect x="{bx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                f'rx="{RADIUS_XL:.0f}" fill="{C["muted"]}"/>'
            )
        elif r["role"] == "ai":
            shell = (
                f'<rect x="{bx + 0.5:.1f}" y="{y + 0.5:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                f'rx="{RADIUS_XL:.0f}" fill="{C["card"]}" stroke="{C["border"]}"/>'
            )
        else:
            shell = (
                f'<rect x="{bx + 0.5:.1f}" y="{y + 0.5:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                f'rx="{RADIUS:.0f}" fill="{C["card"]}" stroke="{C["border"]}" stroke-dasharray="3 3"/>'
            )
        stretch = [f'<g class="{cls_appear(tin)}">{shell}</g>']

        cy = y + CODE_TOP
        code_cls = cls_appear(T["code"]) if has_code else ""
        if has_code:
            stretch.append(
                f'<g class="{code_cls}"><rect x="{bx + 12:.1f}" y="{cy:.1f}" width="{bw - 24:.1f}" '
                f'height="{CODE_H:.1f}" rx="{RADIUS:.0f}" fill="{C["muted"]}"/></g>'
            )
        block = "".join(stretch)
        if resize:
            block = f'<g class="{cls_scale(t_resize, bw_b / bw, origin)}">{block}</g>'
        add(block)

        if r["role"] == "system":
            # A tag in sentence case, then the long prompt cut with an ellipsis:
            # there is much more, out of the frame.
            tag = text(
                bx + PAD_X,
                y + 19,
                r["system_tag"],
                C,
                mono=True,
                fs=10.5,
                fill=C["mutedForeground"],
            )
            lines = "".join(
                text(
                    bx + PAD_X,
                    y + 39 + i * 18,
                    ln[0][1],
                    C,
                    fs=FSM,
                    fill=C["mutedForeground"],
                )
                for i, ln in enumerate(r["lines"])
            )
            add(f'<g class="{cls_appear(tin)}">{tag}{lines}</g>')
        else:
            slide = (
                cls_slide(t_resize, delta)
                if (resize and r["role"] == "human")
                else None
            )
            buf: list[str] = []
            if slide:
                _CAP[0] = buf
            for i, ln in enumerate(r["lines"]):
                render_line(bx + PAD_X, y + 23 + i * 20, ln, C, tin + 0.12, swaps, st)
            if slide:
                _CAP[0] = None
                add('<g class="{}">{}</g>'.format(slide, "".join(buf)))
            if has_code:
                # The tool call is the product at work: its mark is the primary.
                add(
                    f'<g class="{code_cls}"><rect x="{bx + 12:.1f}" y="{cy + 7:.1f}" width="2.5" height="16" '
                    f'rx="1.25" fill="{C["primary"]}"/></g>'
                )
                render_line(
                    bx + 26,
                    cy + 20,
                    r["code"],
                    C,
                    T["code"] + 0.12,
                    [T["s4"]],
                    st,
                    shift=True,
                    fs_mono=FSC,
                )

        geom.append((y, h))
        y += h + GAP_ROWS

    # ---- scrolling: every message past the fourth pushes out the oldest
    steps = [
        (T[rows[i]["tin"]] - 0.15, geom[i - VISIBLE][1] + GAP_ROWS)
        for i in range(VISIBLE, len(rows))
    ]
    cum, H = 0.0, 0.0
    for k in range(len(rows) - VISIBLE + 1):
        if k:
            cum += steps[k - 1][1]
        yb, hb = geom[VISIBLE - 1 + k]
        H = max(H, yb + hb - cum + 26)
    scroll = cls_scroll(steps)

    # ---- title card: the lock-up and the key phrase, one half per line, the
    # second in the primary. It fades into the chat before the first card.
    tn = _n("z")
    KF.append(
        f"@keyframes {tn}{{0%,{pc(INTRO - 0.3)}%{{opacity:1}}{pc(INTRO + 0.5)}%,100%{{opacity:0}}}}"
    )
    CL.append(f".{tn}{{animation:{tn} {LOOP}s linear infinite}}")
    logo_h, pfs = 58.0, 19.0
    top = H / 2 - (logo_h + 22 + 2 * pfs * 1.35) / 2
    first, second = lang["phrase"]
    phrase = text(
        W / 2 - w_sans(first, pfs) / 2, top + logo_h + 22 + pfs, first, C, fs=pfs
    ) + text(
        W / 2 - w_sans(second, pfs) / 2,
        top + logo_h + 22 + pfs * 2.35,
        second,
        C,
        fs=pfs,
        fill=C["primary"],
    )
    title = f'<g class="{tn}">{_logo(theme, W / 2, top, logo_h)}{phrase}</g>'

    # The outgoing message is not yet fully out of the frame when the next one
    # arrives: without this fade a slice of bubble would show, cut on the top edge.
    defs = (
        f'<defs><linearGradient id="g{theme}" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".55" stop-color="#fff" stop-opacity=".2"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>'
        f'<mask id="m{theme}"><rect x="0" y="0" width="{W}" height="26" fill="url(#g{theme})"/>'
        f'<rect x="0" y="26" width="{W}" height="{H - 26:.0f}" fill="#fff"/></mask></defs>'
    )
    fonts = _font_face("Schibsted Grotesk", SANS_FILE, SHOWN) + _font_face(
        "IBM Plex Mono", MONO_FILE, SHOWN_MONO
    )
    css = (
        "<style>"
        + fonts
        + "".join(CL)
        + "".join(KF)
        + "@media (prefers-reduced-motion:reduce){"
        "*{animation:none!important;opacity:1!important;transform:none!important}"
        "g[class^='o'],g[class^='w']{display:none!important}"
        "g[class^='t']{transform:translateX(var(--dx))!important}"
        "g[class^='k']{transform:scaleX(var(--sx))!important}"
        "g[class^='y']{transform:translateY(var(--dy))!important}"
        "g[class^='z']{display:none!important}}"
        "</style>"
    )
    body = f'<g mask="url(#m{theme})"><g class="{scroll}">{"".join(OUT)}</g></g>'
    # The defs follow the style: svg2gif.py keeps what comes after it.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" '
        f'width="{W}" height="{H:.0f}" role="img" aria-label="{esc(lang["aria"])}">'
        f"{css}{defs}{body}{title}</svg>"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render the de-identification chat animation as two SVG files (light + dark)."
    )
    parser.add_argument(
        "--lang",
        choices=sorted(LANGS),
        default="en",
        help="Language of the message script (default: en).",
    )
    parser.add_argument(
        "--out",
        default=".",
        help="Output directory for the two SVG files (default: .).",
    )
    ns = parser.parse_args()

    strings = LANGS[ns.lang]
    rows = make_rows(strings)
    for theme in ("dark", "light"):
        svg = build(palette(theme), theme, rows, strings)
        path = f"{ns.out}/deid-chat-{theme}.svg"
        Path(path).write_text(svg, encoding="utf-8")
        print(path, len(svg), "bytes")
