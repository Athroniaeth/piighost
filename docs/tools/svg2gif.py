# /// script
# requires-python = ">=3.10"
# dependencies = ["cairosvg>=2.7", "pillow>=10", "numpy>=1.24"]
# ///
"""Convert the animated SVG (CSS keyframes) into an animated GIF.

cairosvg does not play CSS animations, so the script replays the keyframes
itself, freezes the state of each group into a static attribute, then
rasterizes. Instants where nothing moves are merged into a single long frame,
which divides the GIF weight several times over.

    uv run --no-project svg2gif.py dark.svg out.gif --fps 20 --scale 1.0

--bg bakes the page colour in, and --dots the charter's field of dots over it,
1px every 22px: a GIF has no page behind it to show them.
"""

import io
import re
import sys
from pathlib import Path
from typing import cast

import cairosvg
import numpy as np
from PIL import Image

Props = dict[str, float]
Stop = tuple[float, Props]
Keyframes = dict[str, list[Stop]]
StateKey = tuple[tuple[float, float, float, float], ...]
Colour = tuple[int, int, int]

LOOP = 20.0


def _group(pattern: str, text: str, flags: int = 0) -> str:
    """Return the first group of the first match of pattern, or raise."""
    match = re.search(pattern, text, flags)
    if match is None:
        raise ValueError(f"no match for {pattern!r}")
    return match.group(1)


def _colours(img: Image.Image) -> list[tuple[int, Colour]]:
    """Return the (count, colour) pairs of an RGB image."""
    colours = img.getcolors(1 << 22)
    if colours is None:
        raise ValueError("too many colours to count")
    # Every frame is converted to RGB, so each colour is a 3-tuple of ints.
    return cast("list[tuple[int, Colour]]", colours)


# --------------------------------------------------------------------- CSS read
def parse_transform(tr: str) -> Props:
    """Read the translate and scaleX functions of a CSS transform value."""
    d = {"tx": 0.0, "ty": 0.0, "sx": 1.0}

    def num(v: str) -> float:
        return float(v.strip().replace("px", ""))

    for fn, args in re.findall(
        r"(translateX|translateY|translate|scaleX)\(([^)]*)\)", tr
    ):
        a = args.split(",")
        if fn == "translate":
            d["tx"] = num(a[0])
            d["ty"] = num(a[1]) if len(a) > 1 else 0.0
        elif fn == "translateX":
            d["tx"] = num(a[0])
        elif fn == "translateY":
            d["ty"] = num(a[0])
        else:
            d["sx"] = num(a[0])
    return d


def load(path: str) -> tuple[str, Keyframes, dict[str, str], str]:
    """Parse the SVG into its body, keyframes, transform origins and viewBox.

    The loop duration is read too: it is declared in the CSS, and a value
    hard-coded here would shift the whole sampling without breaking anything
    visible in the file.
    """
    global LOOP
    src = Path(path).read_text(encoding="utf-8")
    style = _group(r"<style>(.*?)</style>", src, re.DOTALL)
    LOOP = float(_group(r"animation:\w+ ([\d.]+)s", style))
    # Only the root's closing tag: the logo of the title card nests an <svg>.
    body = src[src.index("</style>") + 8 : src.rindex("</svg>")]
    kfs = {}
    for m in re.finditer(
        r"@keyframes (\w+)\{(.*?)\}(?=@keyframes|@media|\Z)", style, re.DOTALL
    ):
        stops = []
        for bm in re.finditer(r"([\d.%,\s]+)\{([^}]*)\}", m.group(2)):
            props = bm.group(2)
            op = re.search(r"opacity:([\d.]+)", props)
            tr = re.search(r"transform:([^;}]+)", props)
            p = dict(
                op=float(op.group(1)) if op else 1.0,
                **(
                    parse_transform(tr.group(1))
                    if tr
                    else {"tx": 0.0, "ty": 0.0, "sx": 1.0}
                ),
            )
            for sel in bm.group(1).split(","):
                sel = sel.strip().rstrip("%")
                if sel:
                    stops.append((float(sel), p))
        kfs[m.group(1)] = sorted(stops, key=lambda x: x[0])
    origin = {
        m.group(1): m.group(2)
        for m in re.finditer(r"\.(\w+)\{[^}]*transform-origin:(\w+) center", style)
    }
    vb = _group(r'viewBox="([^"]+)"', src)
    return body, kfs, origin, vb


def sample(stops: list[Stop], t: float) -> tuple[float, float, float, float]:
    """Interpolate (opacity, tx, ty, sx) linearly at time t within the loop."""
    pct = (t % LOOP) / LOOP * 100.0
    lo, hi = stops[0], stops[-1]
    for i in range(len(stops) - 1):
        if stops[i][0] <= pct <= stops[i + 1][0]:
            lo, hi = stops[i], stops[i + 1]
            break
    span = hi[0] - lo[0]
    u = 0.0 if span <= 0 else (pct - lo[0]) / span

    def m(k: str) -> float:
        return lo[1][k] + (hi[1][k] - lo[1][k]) * u

    return (m("op"), m("tx"), m("ty"), m("sx"))


# ---------------------------------------------------------- group bounding box
def group_span(body: str, start: int) -> tuple[float, float]:
    """Horizontal extent (x_min, x_max) of the group opened at start."""
    depth, i = 0, start
    for m in re.finditer(r"<g\b[^>]*>|</g>", body[start:]):
        depth += 1 if m.group(0) != "</g>" else -1
        if depth == 0:
            i = start + m.end()
            break
    inner = body[start:i]
    xs = []
    for r in re.finditer(r'<rect x="(-?[\d.]+)"[^>]*width="([\d.]+)"', inner):
        x, w = float(r.group(1)), float(r.group(2))
        xs += [x, x + w]
    for c in re.finditer(r'<circle cx="(-?[\d.]+)"[^>]*r="([\d.]+)"', inner):
        x, r_ = float(c.group(1)), float(c.group(2))
        xs += [x - r_, x + r_]
    return (min(xs), max(xs)) if xs else (0.0, 0.0)


# ------------------------------------------------------------------ SVG render
def build_frame(body: str, kfs: Keyframes, pivots: dict[str, float], t: float) -> str:
    """Freeze every animated group of the body into its static state at time t."""

    def rep(m: re.Match[str]) -> str:
        cid = m.group(1)
        stops = kfs.get(cid)
        if stops is None:
            return m.group(0)
        op, tx, ty, sx = sample(stops, t)
        tr = ""
        if abs(sx - 1.0) > 1e-6:
            px = pivots[cid]
            tr = f"translate({px:.4f},0) scale({sx:.6f},1) translate({-px:.4f},0) "
        if abs(tx) > 1e-6 or abs(ty) > 1e-6:
            tr += f"translate({tx:.4f},{ty:.4f})"
        a = f' transform="{tr.strip()}"' if tr else ""
        return f'<g opacity="{op:.4f}"{a}>'

    return re.sub(r'<g class="(\w+)">', rep, body)


def state_key(kfs: Keyframes, t: float) -> StateKey:
    """Signature of the frame: two instants with the same signature are identical."""
    out = []
    for cid in sorted(kfs):
        op, tx, ty, sx = sample(kfs[cid], t)
        out.append((round(op, 3), round(tx, 2), round(ty, 2), round(sx, 4)))
    return tuple(out)


def render(
    svg_path: str,
    out_path: str,
    fps: float = 20.0,
    scale: float = 1.0,
    bg: str | None = None,
    colors: int = 200,
    dots: str | None = None,
) -> str:
    """Rasterize the animated SVG at svg_path into an animated GIF at out_path."""
    body, kfs, origin, vb = load(svg_path)
    pivots = {}
    for m in re.finditer(r'<g class="(\w+)">', body):
        cid = m.group(1)
        if cid in origin:
            x0, x1 = group_span(body, m.start())
            pivots[cid] = x0 if origin[cid] == "left" else x1

    field = ""
    if dots:
        field = (
            '<defs><pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
            f'<circle cx="11" cy="11" r="0.75" fill="{dots}"/></pattern></defs>'
            '<rect width="100%" height="100%" fill="url(#dots)"/>'
        )
    n = round(LOOP * fps)
    print(f"  loop of {LOOP:.1f} s")
    step_cs = 100.0 / fps
    keys, times, durs = [], [], []
    for i in range(n):
        k = state_key(kfs, i / fps)
        if keys and k == keys[-1]:
            durs[-1] += step_cs
        else:
            keys.append(k)
            times.append(i / fps)
            durs.append(step_cs)

    print(f"  {n} instants -> {len(times)} distinct frames")
    frames = []
    for j, t in enumerate(times):
        frame = build_frame(body, kfs, pivots, t)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">{field}{frame}</svg>'
        png = cairosvg.svg2png(
            bytestring=svg.encode(), scale=scale, background_color=bg
        )
        frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
        if (j + 1) % 25 == 0:
            print(f"    {j + 1}/{len(times)}")

    # One shared palette, otherwise every frame embeds its own, weighted by
    # display time. The fades produce thousands of intermediate shades; without
    # weighting they drown the colours of the stable states, and the restored
    # green turns grey. The background covers 95 % of the pixels: a plain median
    # cut gives it everything and merges the token blue with the restored green.
    # So the list of *distinct* colours of the stable frames is quantized, each
    # one counted once.
    hold = [f for f, d in zip(frames, durs, strict=True) if d >= 15] or frames
    uniq = sorted({c for f in hold for _, c in _colours(f)})
    sheet = Image.new("RGB", (len(uniq), 1))
    sheet.putdata(uniq)
    palette = sheet.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    table = list(palette.getpalette() or [])[: colors * 3]

    # Counting each shade once lets the flat areas drift: the white background
    # came out as (250,251,253), enough for a seam to show against a README
    # page. The dominant shades are snapped back to their exact value.
    tally: dict[Colour, int] = {}
    for f in hold:
        for cnt, col in _colours(f):
            tally[col] = tally.get(col, 0) + cnt
    taken = set()
    for col in sorted(tally, key=lambda c: tally[c], reverse=True)[:24]:
        d = [
            (sum((table[3 * i + k] - col[k]) ** 2 for k in range(3)), i)
            for i in range(colors)
            if i not in taken
        ]
        if not d:
            break
        i = min(d)[1]
        taken.add(i)
        table[3 * i : 3 * i + 3] = list(col)

    # Image.quantize(palette=...) goes through a 5-bit-per-channel cache: pure
    # white and (250,251,253) land in the same bucket and the exact white is
    # ignored. So the nearest-neighbour search is done here, over the list of
    # distinct colours (a few thousand), not over every pixel.
    allc = np.array(sorted({c for f in frames for _, c in _colours(f)}), dtype=np.int16)
    ptab = np.array(table, dtype=np.int16).reshape(-1, 3)
    idx = np.empty(len(allc), dtype=np.uint8)
    for s0 in range(0, len(allc), 2048):
        chunk = allc[s0 : s0 + 2048]
        d2 = ((chunk[:, None, :] - ptab[None, :, :]).astype(np.int32) ** 2).sum(2)
        idx[s0 : s0 + 2048] = d2.argmin(1).astype(np.uint8)
    keys = (
        allc[:, 0].astype(np.uint32) << 16
        | allc[:, 1].astype(np.uint32) << 8
        | allc[:, 2].astype(np.uint32)
    )
    order = np.argsort(keys)
    keys, idx = keys[order], idx[order]

    conv = []
    for f in frames:
        a = np.asarray(f, dtype=np.uint32)
        k = (a[:, :, 0] << 16) | (a[:, :, 1] << 8) | a[:, :, 2]
        m = Image.fromarray(idx[np.searchsorted(keys, k.ravel())].reshape(k.shape), "P")
        m.putpalette(table + [0] * (768 - len(table)))
        conv.append(m)
    print(
        f"  {len(uniq)} distinct colours -> palette of {colors}, "
        f"{len(taken)} flat areas snapped"
    )

    ds = [max(2, round(d)) * 10 for d in durs]  # centiseconds -> milliseconds
    conv[0].save(
        out_path,
        save_all=True,
        append_images=conv[1:],
        duration=ds,
        loop=0,
        optimize=True,
        disposal=1,
    )
    kb = Path(out_path).stat().st_size / 1024.0
    print(f"  {out_path}  {conv[0].width}x{conv[0].height}  {kb:.0f} KB")
    return out_path


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        sys.exit(1)

    def g(k: str, d: float) -> float:
        """Read the float value following flag k, or return the default d."""
        return float(a[a.index(k) + 1]) if k in a else d

    render(
        a[0],
        a[1],
        fps=g("--fps", 20.0),
        scale=g("--scale", 1.0),
        bg=(a[a.index("--bg") + 1] if "--bg" in a else None),
        colors=int(g("--colors", 200)),
        dots=(a[a.index("--dots") + 1] if "--dots" in a else None),
    )
