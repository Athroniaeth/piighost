# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools>=4.0"]
# ///
"""Render the de-identification chat animation as animated SVG files.

PII values are masked before reaching the model and restored on the way back.
Pure CSS keyframes, no JavaScript.

Colour states
  real  (amber)  the raw value, as the user typed it
  mask  (blue)   the placeholder actually sent to the model
  rest  (green)  the value restored on the way back
"""

import argparse
import os
from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont

Palette = dict[str, str]
Segment = tuple[str, Any]
Row = dict[str, Any]

# The chat is preceded by a short title card (INTRO seconds) and a system-prompt
# bubble (SYS_GAP seconds) shown before the first user message. Both push the
# original chat timeline later, so the loop and the fade-out grow by the same
# offset and every relative timing is preserved.
INTRO = 1.6
SYS_GAP = 1.7
OFFSET = INTRO + SYS_GAP
LOOP = 24.0 + OFFSET
FADE_OUT = 22.0 + OFFSET
W = 760
GAP_ROWS = 16.0

# Space Grotesk and JetBrains Mono, both under the SIL OFL.
FONT_DIR = os.environ.get("FONT_DIR", str(Path(__file__).resolve().parent / "fonts"))
SANS = "'Space Grotesk',sans-serif"
MONO = "'JetBrains Mono',ui-monospace,monospace"
FS, FSM, FSC = 13.5, 11.5, 11.5

DARK = {
    "text": "#E4EAF3",
    "muted": "#909DB4",
    "userBg": "#28303F",
    "aiBg": "#1D2431",
    "aiStroke": "#2E3746",
    "real": "#F0AD4A",
    "realBg": "#41300F",
    "mask": "#7FC0FF",
    "maskBg": "#16324F",
    "rest": "#79EE92",
    "restBg": "#12402A",
    "ai": "#B49CFF",
    "aiAvBg": "#2B2350",
    "avBg": "#252D3C",
    "avGlyph": "#8A97AC",
    "codeBg": "#252D3C",
}
# The assistant bubble must stay lighter than the page: below this value the
# card sinks into the background instead of floating on it.
PAGE = {"dark": "#151A24", "light": "#FFFFFF"}
LIGHT = {
    "text": "#18202E",
    "muted": "#647287",
    "userBg": "#EDF2F8",
    "aiBg": "#FFFFFF",
    "aiStroke": "#E2E9F2",
    "real": "#A65A05",
    "realBg": "#FBF0DC",
    "mask": "#0A58BE",
    "maskBg": "#E4EFFC",
    "rest": "#157F3B",
    "restBg": "#E0F4E5",
    "ai": "#5B36C9",
    "aiAvBg": "#EFEAFD",
    "avBg": "#F1F4F9",
    "avGlyph": "#7A879B",
    "codeBg": "#F4F7FB",
}


def hue(C: Palette, key: str) -> tuple[str, str]:
    """Return the foreground and background colours of a colour state."""
    return C[key], C[key + "Bg"]


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
# would have to be redone at every font change, and a pill too narrow overflows
# its bubble while the SVG stays valid: the fault only shows to the eye.
def _face(name: str) -> tuple[dict[str, float], dict[str, float]]:
    """Read the advance widths and left side bearings of a font, in em."""
    f = TTFont(str(Path(FONT_DIR) / name))
    upem = float(f["head"].unitsPerEm)
    hm, cmap = f["hmtx"], f.getBestCmap()
    adv = {chr(c): hm.metrics[n][0] / upem for c, n in cmap.items() if n in hm.metrics}
    lsb = {chr(c): hm.metrics[n][1] / upem for c, n in cmap.items() if n in hm.metrics}
    return adv, lsb


_SADV, _SLSB = _face("SpaceGrotesk-Medium.ttf")
_MADV, _MLSB = _face("JetBrainsMono-Regular.ttf")


def w_sans(s: str) -> float:
    """Real width of the text (+0.5 %: cairo rounds at the subpixel)."""
    return sum(_SADV.get(c, 0.55) for c in s) * FS * 1.005


def w_mono(s: str, fs: float | None = None) -> float:
    """Real width of a monospace text at font size fs."""
    fs = FSM if fs is None else fs
    return sum(_MADV.get(c, 0.6) for c in s) * fs * 1.005


PAD, PILL_H, LEAD = 3.5, 18.0, 3.0
PAD_X = 14.0  # horizontal padding of the bubbles


def pill_w(v: str, fs: float | None = None) -> float:
    """Width of a pill holding the value v."""
    return w_mono(v, fs) + 2 * PAD


_PUNCT = (",", ".", ")", ";", ":", "?", "!")


def gap_after(nxt: tuple[str, str], last: bool = False) -> float:
    """Gap after a fragment, given the next fragment nxt as (kind, text).

    A pill already carries 3.5 px of inner padding on its right, and the comma
    that follows adds its left side bearing: the sign ends up floating far from
    the word. Both are subtracted to stick it back. Only in running text: in
    the code block the closing parenthesis must stay readable next to the
    value, not glued to it.
    """
    kind, txt = nxt
    if last:
        return 0.0
    if txt[:1] not in _PUNCT:
        return 3.5
    return 0.5 - PAD - _SLSB.get(txt[0], 0.0) * FS if kind == "t" else 0.0


OUT: list[str] = []
_CAP: list[list[str] | None] = [None]


def add(s: str) -> None:
    """Append an SVG fragment to the output, or to the open capture buffer."""
    (OUT if _CAP[0] is None else _CAP[0]).append(s)


def swap_pill(
    x: float,
    y: float,
    va: str,
    vb: str,
    ka: str,
    kb: str,
    t_in: float,
    t_swap: float,
    C: Palette,
    fs: float,
) -> tuple[float, float]:
    """Pill with two stacked states. Return (width_a, width_b)."""
    ca, ba = hue(C, ka)
    cb, bb = hue(C, kb)
    wa, wb = pill_w(va, fs), pill_w(vb, fs)

    def state(txt: str, col: str, bg: str, wd: float, cls: str) -> str:
        """Render one state of the pill."""
        return (
            f'<g class="{cls}"><rect x="{x:.1f}" y="{y - 13:.1f}" width="{wd:.1f}" height="{PILL_H:.1f}" rx="5" '
            f'fill="{bg}"/><text x="{x + PAD:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{fs}" '
            f'fill="{col}">{esc(txt)}</text></g>'
        )

    add(state(va, ca, ba, wa, cls_out(t_in, t_swap)))
    add(state(vb, cb, bb, wb, cls_in(t_swap)))
    add(
        f'<g class="{cls_sweep(t_swap, wb - 3.0)}"><rect x="{x:.1f}" y="{y - 13:.1f}" width="3" height="{PILL_H:.1f}" rx="1.5" fill="{cb}"/></g>'
    )
    return wa, wb


def _next_seg(segs: list[Segment], i: int) -> tuple[str, str]:
    """Return the segment after index i as (kind, text), a pill's text empty."""
    for k, v in segs[i + 1 :]:
        return (k, v if isinstance(v, str) else "")
    return ("t", "")


def line_w(
    segs: list[Segment],
    states: tuple[str, str] = ("real", "mask"),
    which: str = "a",
    fs_mono: float = FSM,
) -> float:
    """Width of the line in state a (before the swap) or b (after)."""
    key = states[0] if which == "a" else states[1]
    tot = 0.0
    for i, (kind, val) in enumerate(segs):
        g = gap_after(_next_seg(segs, i), i == len(segs) - 1)
        if kind == "s":
            tot += LEAD + pill_w(val[1] if key == "mask" else val[0], fs_mono) + g
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
    states: tuple[str, str],
    shift: bool = False,
    fs_mono: float = FSM,
) -> None:
    """Render one line of a message.

    Args:
        x: Left edge of the line.
        y: Text baseline of the line.
        segs: Segments of the line, as (kind, value) pairs.
        C: Colour palette.
        t_in: Instant the line appears.
        swaps: Swap instants, consumed in order by the pills.
        states: Colour state keys before and after the swap.
        shift: Whether the end of the line follows the pill width.
        fs_mono: Font size of the monospace text.
    """
    ka, kb = states
    cur, dx, tail_open = x, 0.0, False
    plain, tail = [], []
    si = 0

    for i, (kind, val) in enumerate(segs):
        g = gap_after(_next_seg(segs, i), i == len(segs) - 1)
        if kind == "s":
            ts = swaps[si] if si < len(swaps) else LOOP * 2
            si += 1
            # val is always (real_value, token); the state decides which shows
            txt_a = val[1] if ka == "mask" else val[0]
            txt_b = val[1] if kb == "mask" else val[0]
            wa, wb = swap_pill(
                cur + LEAD, y, txt_a, txt_b, ka, kb, t_in, ts, C, fs_mono
            )
            if shift:
                dx = wb - wa
                cur += LEAD + wa + g
                tail_open = True
            else:
                cur += LEAD + wa + g
            continue
        if kind == "t":
            wd, ff, fz, col = w_sans(val), SANS, FS, C["text"]
        elif kind == "m":
            wd, ff, fz, col = w_mono(val, fs_mono), MONO, fs_mono, C["muted"]
        else:
            wd, ff, fz, col = w_mono(val, fs_mono), MONO, fs_mono, C["ai"]
        frag = f'<text x="{cur:.1f}" y="{y:.1f}" font-family="{ff}" font-size="{fz}" fill="{col}">{esc(val)}</text>'
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
    """Render the human or AI avatar."""
    cls = cls_appear(tin, dy=4)
    if kind == "human":
        return (
            '<g class="{}"><rect x="{:.1f}" y="{:.1f}" width="28" height="28" rx="9" fill="{}"/>'
            '<circle cx="{:.1f}" cy="{:.1f}" r="3.5" fill="{}"/>'
            '<path d="M{:.1f} {:.1f} a5.9 5.9 0 0 1 11.8 0 z" fill="{}"/></g>'.format(
                cls,
                x,
                y,
                C["avBg"],
                x + 14,
                y + 10.8,
                C["avGlyph"],
                x + 8.1,
                y + 21.6,
                C["avGlyph"],
            )
        )
    return (
        '<g class="{}"><rect x="{:.1f}" y="{:.1f}" width="28" height="28" rx="9" fill="{}"/>'
        '<path d="M{:.1f} {:.1f} C{:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} C{:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} '
        'C{:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} C{:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} Z" fill="{}"/></g>'.format(
            cls,
            x,
            y,
            C["aiAvBg"],
            x + 14,
            y + 6.4,
            x + 14.6,
            y + 11.3,
            x + 16.7,
            y + 13.4,
            x + 21.6,
            y + 14,
            x + 16.7,
            y + 14.6,
            x + 14.6,
            y + 16.7,
            x + 14,
            y + 21.6,
            x + 13.4,
            y + 16.7,
            x + 11.3,
            y + 14.6,
            x + 6.4,
            y + 14,
            x + 11.3,
            y + 13.4,
            x + 13.4,
            y + 11.3,
            x + 14,
            y + 6.4,
            C["ai"],
        )
    )


# ------------------------------------------------------------------ scenario
NAME_R, NAME_M = "Marie Dupont", "<<person:1>>"
MAIL_R, MAIL_M = "marie.dupont@acme.fr", "<<email:1>>"

# Base timeline of the chat, before the title card and system bubble are
# prepended. Every key is pushed later by OFFSET; the system bubble gets its
# own slot right after the title card starts fading.
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
T = {"sys": round(INTRO + 0.6, 3)}
T.update({k: round(v + OFFSET, 3) for k, v in _BASE.items()})

# Four bubbles fit in the frame. The last two push the first two out of view:
# the conversation scrolls as in a real interface.
VISIBLE = 4

# Only the display strings differ per language. NAME/MAIL and the timing keys
# are shared, so the message script stays the same and only the text changes.
LANGS = {
    "en": {
        "aria": "PII values are replaced by placeholders before reaching the model, "
        "then restored for the user and for tool calls",
        "greet_user": "Hi, I'm",
        "email_intro": ", my email is",
        "greet_ai": "Hello",
        "help_offer": ", how can I help?",
        "ask": "What's the first letter of my first name?",
        "refuse": "I can't, that name never reaches me.",
        "request": "Can you email me the summary?",
        "confirm": "Sure, sending it now.",
        "sys_tag": "System prompt",
        "sys": (
            "You are a support assistant. Every value that looks like",
            "personal data is already a placeholder: never reveal a real one…",
        ),
    },
    "fr": {
        "aria": "Les valeurs PII sont remplacées par des placeholders avant d'atteindre "
        "le modèle, puis restaurées pour l'utilisateur et pour les appels d'outils",
        "greet_user": "Bonjour, je suis",
        "email_intro": ", mon email est",
        "greet_ai": "Bonjour",
        "help_offer": ", comment puis-je aider ?",
        "ask": "Quelle est la première lettre de mon prénom ?",
        "refuse": "Je ne peux pas, ce nom ne m'atteint jamais.",
        "request": "Peux-tu m'envoyer le résumé par email ?",
        "confirm": "Bien sûr, je l'envoie.",
        "sys_tag": "Prompt système",
        "sys": (
            "Tu es un assistant support. Toute valeur ressemblant à une",
            "donnée personnelle est déjà un placeholder : ne rien révéler…",
        ),
    },
}


def make_rows(L: dict[str, Any]) -> list[Row]:
    """Build the message script for one language from its localized strings.

    The rows carry the animation structure (role, timing key, swap instants,
    optional tool call). Only the displayed text differs per language, so the
    geometry is recomputed from the real glyph widths of the chosen strings.
    """
    return [
        {
            "role": "system",
            "tin": "sys",
            "states": ("real", "mask"),
            "swaps": [],
            "system_tag": L["sys_tag"],
            "lines": [[("t", L["sys"][0])], [("t", L["sys"][1])]],
        },
        {
            "role": "human",
            "tin": "m1",
            "states": ("real", "mask"),
            "swaps": ["s1", "s2"],
            "lines": [
                [
                    ("t", L["greet_user"]),
                    ("s", (NAME_R, NAME_M)),
                    ("t", L["email_intro"]),
                    ("s", (MAIL_R, MAIL_M)),
                ]
            ],
        },
        {
            "role": "ai",
            "tin": "m2",
            "states": ("mask", "rest"),
            "swaps": ["s3"],
            "lines": [
                [("t", L["greet_ai"]), ("s", (NAME_R, NAME_M)), ("t", L["help_offer"])]
            ],
        },
        {
            "role": "human",
            "tin": "m3",
            "states": ("real", "mask"),
            "swaps": [],
            "lines": [[("t", L["ask"])]],
        },
        {
            "role": "ai",
            "tin": "m4",
            "states": ("mask", "rest"),
            "swaps": [],
            "lines": [[("t", L["refuse"])]],
        },
        {
            "role": "human",
            "tin": "m5",
            "states": ("real", "mask"),
            "swaps": [],
            "lines": [[("t", L["request"])]],
        },
        {
            "role": "ai",
            "tin": "m6",
            "states": ("mask", "rest"),
            "swaps": [],
            "lines": [[("t", L["confirm"])]],
            "code": [
                ("v", "send_email"),
                ("m", "(to="),
                ("s", (MAIL_R, MAIL_M)),
                ("m", ")"),
            ],
        },
    ]


CODE_TOP = 28.0  # from the top of the bubble: tight space under the text
CODE_H = 30.0


def row_w(r: Row, which: str) -> float:
    """Width of the widest line of the row r in state which."""
    ws = [line_w(line, r["states"], which) for line in r["lines"]]
    if "code" in r:
        ws.append(line_w(r["code"], r["states"], which, FSC) + 40)
    return max(ws)


def build(C: Palette, uid: str, rows: list[Row], aria: str) -> str:
    """Render the whole animation for one palette as an SVG document."""
    OUT[:], KF[:], CL[:] = [], [], []
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
        # the resize follows the pill whose width changes
        t_resize = swaps[-1] if swaps else T["s4"]
        h = (len(r["lines"]) - 1) * 20 + 38 + (CODE_H + 2 if has_code else 0)
        if r["role"] == "system":
            h = 30 + len(r["lines"]) * 19 + 6

        if r["role"] == "ai":
            bx, ax, origin = 64.0, 24.0, "left"
        elif r["role"] == "human":
            bx, ax, origin = W - 64 - bw, W - 52.0, "right"
        else:  # system: left-aligned banner (a system message), no avatar
            bx, ax, origin = 24.0, None, "left"

        if ax is not None:
            add(
                draw_avatar(
                    "human" if r["role"] == "human" else "ai", ax, y + 5, C, tin
                )
            )

        # ---- bubble (+ code block background): shrinks or stretches, opposite edge fixed
        if r["role"] == "human":
            shell = '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" rx="13" fill="{}"/>'.format(
                bx, y, bw, h, C["userBg"]
            )
        elif r["role"] == "ai":
            shell = (
                '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" rx="13" fill="{}" '
                'stroke="{}"/>'.format(
                    bx + 0.5, y + 0.5, bw, h, C["aiBg"], C["aiStroke"]
                )
            )
        else:  # system: muted instruction card
            shell = (
                '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" rx="12" fill="{}" '
                'stroke="{}"/>'.format(
                    bx + 0.5, y + 0.5, bw, h, C["codeBg"], C["aiStroke"]
                )
            )
        stretch = [f'<g class="{cls_appear(tin)}">{shell}</g>']

        cy = y + CODE_TOP
        code_cls = cls_appear(T["code"]) if has_code else ""
        if has_code:
            stretch.append(
                '<g class="{}"><rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" '
                'rx="8" fill="{}" opacity=".55"/></g>'.format(
                    code_cls, bx + 12, cy, bw - 24, CODE_H, C["codeBg"]
                )
            )
        block = "".join(stretch)
        if resize:
            block = f'<g class="{cls_scale(t_resize, bw_b / bw, origin)}">{block}</g>'
        add(block)

        # ---- content
        if r["role"] == "system":
            # a small tag, then the long prompt shown chunked (truncated with an
            # ellipsis): it stands for "there is much more, hidden here".
            add(
                '<g class="{}"><text x="{:.1f}" y="{:.1f}" font-family="{}" font-size="9.5" '
                'letter-spacing="0.8" fill="{}">{}</text></g>'.format(
                    cls_appear(tin),
                    bx + PAD_X,
                    y + 19,
                    SANS,
                    C["muted"],
                    esc(r["system_tag"].upper()),
                )
            )
            frags = []
            for i, ln in enumerate(r["lines"]):
                frags.append(
                    '<text x="{:.1f}" y="{:.1f}" font-family="{}" font-size="{}" '
                    'fill="{}">{}</text>'.format(
                        bx + PAD_X,
                        y + 39 + i * 18,
                        SANS,
                        FSM + 0.5,
                        C["muted"],
                        esc(ln[0][1]),
                    )
                )
            add('<g class="{}">{}</g>'.format(cls_appear(tin), "".join(frags)))
        else:
            # left-aligned in the bubble, it slides when the bubble shrinks
            slide = (
                cls_slide(t_resize, delta)
                if (resize and r["role"] == "human")
                else None
            )
            buf = []
            if slide:
                _CAP[0] = buf
            for i, ln in enumerate(r["lines"]):
                render_line(bx + PAD_X, y + 23 + i * 20, ln, C, tin + 0.12, swaps, st)
            if slide:
                _CAP[0] = None
                add('<g class="{}">{}</g>'.format(slide, "".join(buf)))

            if has_code:
                add(
                    '<g class="{}"><rect x="{:.1f}" y="{:.1f}" width="2.5" height="16" rx="1.25" '
                    'fill="{}"/></g>'.format(code_cls, bx + 12, cy + 7, C["ai"])
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

    # The frame fits the tallest state: the window never changes size along the
    # way, only the content slides beneath it.
    cum, H = 0.0, 0.0
    for k in range(len(rows) - VISIBLE + 1):
        if k:
            cum += steps[k - 1][1]
        yb, hb = geom[VISIBLE - 1 + k]
        H = max(H, yb + hb - cum + 26)

    scroll = cls_scroll(steps)

    # ---- title card: the ghost logo (a Lucide icon, as in the docs) and the
    # wordmark in the docs font, fading into the chat. It lives outside the
    # scroll mask, above the thread, and disappears for good as soon as the
    # first message arrives.
    tn = _n("z")
    KF.append(
        f"@keyframes {tn}{{0%,{pc(INTRO - 0.2)}%{{opacity:1}}{pc(INTRO + 0.8)}%,100%{{opacity:0}}}}"
    )
    CL.append(f".{tn}{{animation:{tn} {LOOP}s linear infinite}}")
    tfs, gi, gap = 36.0, 48.0, 17.0
    ww = sum(_SADV.get(c, 0.55) for c in "piighost") * tfs * 1.005
    tx = (W - (gi + gap + ww)) / 2
    tcy = H / 2
    ghost = (
        '<g transform="translate({:.1f},{:.1f}) scale({:.4f})" fill="none" stroke="{}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9 10h.01"/><path d="M15 10h.01"/>'
        '<path d="M12 2a8 8 0 0 0-8 8v12l3-3 2.5 2.5L12 19l2.5 2.5L17 19l3 3V10a8 8 0 0 '
        '0-8-8z"/></g>'.format(tx, tcy - gi / 2, gi / 24.0, C["text"])
    )
    word = (
        '<text x="{:.1f}" y="{:.1f}" font-family="{}" font-size="{}" font-weight="500" '
        'fill="{}">piighost</text>'.format(
            tx + gi + gap, tcy + tfs * 0.33, SANS, tfs, C["text"]
        )
    )
    title = (
        f'<g class="{tn}"><rect x="0" y="0" width="{W}" height="{H:.0f}" '
        f'fill="{PAGE[uid]}"/>{ghost}{word}</g>'
    )

    # The outgoing message is not yet fully out of the frame when the next one
    # arrives: without this fade a slice of bubble would show, cut sharp on the
    # top edge.
    defs = (
        f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".55" stop-color="#fff" stop-opacity=".2"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>'
        f'<mask id="m{uid}"><rect x="0" y="0" width="{W}" height="26" '
        f'fill="url(#g{uid})"/>'
        f'<rect x="0" y="26" width="{W}" height="{H - 26:.0f}" fill="#fff"/>'
        "</mask></defs>"
    )

    css = (
        "<style>"
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
    body = '<g mask="url(#m{})"><g class="{}">{}</g></g>'.format(
        uid, scroll, "".join(OUT)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" '
        f'width="{W}" height="{H:.0f}" role="img" aria-label="{esc(aria)}">'
        f"{defs}{css}{body}{title}</svg>"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render the de-identification "
        "chat animation as two SVG files (light + dark)."
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
    for palette, theme in ((DARK, "dark"), (LIGHT, "light")):
        # uid = theme keeps the two mask ids distinct, so the light and dark
        # SVGs can coexist on one page (one shown per colour scheme).
        svg = build(palette, theme, rows, strings["aria"])
        path = f"{ns.out}/deid-chat-{theme}.svg"
        Path(path).write_text(svg, encoding="utf-8")
        print(path, len(svg), "bytes")
