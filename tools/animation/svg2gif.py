#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.10"
# dependencies = ["cairosvg>=2.7", "pillow>=10", "numpy>=1.24"]
# ///
"""Convertit le SVG anime (keyframes CSS) en GIF anime.

cairosvg ne joue pas les animations CSS : on rejoue donc les keyframes nous
memes, on fige l'etat de chaque groupe dans un attribut statique, puis on
rasterise. Les instants ou rien ne bouge sont fusionnes en une seule image de
longue duree, ce qui divise le poids du GIF par plusieurs.

    python3 svg2gif.py dark.svg out.gif --fps 20 --scale 1.0
"""
import re, io, sys, os, math
import numpy as np
import cairosvg
from PIL import Image

LOOP = 20.0


# ----------------------------------------------------------------- lecture CSS
def parse_transform(tr):
    d = dict(tx=0.0, ty=0.0, sx=1.0)
    num = lambda v: float(v.strip().replace("px", ""))
    for fn, args in re.findall(r'(translateX|translateY|translate|scaleX)\(([^)]*)\)', tr):
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


def load(path):
    """Renvoie aussi la duree de boucle : elle est declaree dans le CSS et une
    valeur codee en dur ici decalerait tout l'echantillonnage sans rien casser
    de visible dans le fichier."""
    global LOOP
    src = io.open(path, encoding="utf-8").read()
    style = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    LOOP = float(re.search(r'animation:\w+ ([\d.]+)s', style).group(1))
    body = src[src.index("</style>") + 8:].replace("</svg>", "")
    kfs = {}
    for m in re.finditer(r'@keyframes (\w+)\{(.*?)\}(?=@keyframes|@media|\Z)', style, re.S):
        stops = []
        for bm in re.finditer(r'([\d.%,\s]+)\{([^}]*)\}', m.group(2)):
            props = bm.group(2)
            op = re.search(r'opacity:([\d.]+)', props)
            tr = re.search(r'transform:([^;}]+)', props)
            p = dict(op=float(op.group(1)) if op else 1.0,
                     **(parse_transform(tr.group(1)) if tr else dict(tx=0.0, ty=0.0, sx=1.0)))
            for sel in bm.group(1).split(","):
                sel = sel.strip().rstrip("%")
                if sel:
                    stops.append((float(sel), p))
        kfs[m.group(1)] = sorted(stops, key=lambda x: x[0])
    origin = dict((m.group(1), m.group(2)) for m in
                  re.finditer(r'\.(\w+)\{[^}]*transform-origin:(\w+) center', style))
    vb = re.search(r'viewBox="([^"]+)"', src).group(1)
    return body, kfs, origin, vb


def sample(stops, t):
    pct = (t % LOOP) / LOOP * 100.0
    lo, hi = stops[0], stops[-1]
    for i in range(len(stops) - 1):
        if stops[i][0] <= pct <= stops[i + 1][0]:
            lo, hi = stops[i], stops[i + 1]
            break
    span = hi[0] - lo[0]
    u = 0.0 if span <= 0 else (pct - lo[0]) / span
    m = lambda k: lo[1][k] + (hi[1][k] - lo[1][k]) * u
    return (m("op"), m("tx"), m("ty"), m("sx"))


# ------------------------------------------------ boite englobante d'un groupe
def group_span(body, start):
    """Etendue horizontale (x_min, x_max) du groupe ouvert a `start`."""
    depth, i = 0, start
    for m in re.finditer(r'<g\b[^>]*>|</g>', body[start:]):
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


# ------------------------------------------------------------------ rendu SVG
def build_frame(body, kfs, origin, pivots, t):
    def rep(m):
        cid = m.group(1)
        stops = kfs.get(cid)
        if stops is None:
            return m.group(0)
        op, tx, ty, sx = sample(stops, t)
        tr = ""
        if abs(sx - 1.0) > 1e-6:
            px = pivots[cid]
            tr = "translate(%.4f,0) scale(%.6f,1) translate(%.4f,0) " % (px, sx, -px)
        if abs(tx) > 1e-6 or abs(ty) > 1e-6:
            tr += "translate(%.4f,%.4f)" % (tx, ty)
        a = ' transform="%s"' % tr.strip() if tr else ""
        return '<g opacity="%.4f"%s>' % (op, a)
    return re.sub(r'<g class="(\w+)">', rep, body)


def state_key(kfs, t):
    """Signature de l'image : deux instants de meme signature sont identiques."""
    out = []
    for cid in sorted(kfs):
        op, tx, ty, sx = sample(kfs[cid], t)
        out.append((round(op, 3), round(tx, 2), round(ty, 2), round(sx, 4)))
    return tuple(out)


def render(svg_path, out_path, fps=20.0, scale=1.0, bg=None, colors=200):
    body, kfs, origin, vb = load(svg_path)
    pivots = {}
    for m in re.finditer(r'<g class="(\w+)">', body):
        cid = m.group(1)
        if cid in origin:
            x0, x1 = group_span(body, m.start())
            pivots[cid] = x0 if origin[cid] == "left" else x1

    n = int(round(LOOP * fps))
    print("  boucle de %.1f s" % LOOP)
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

    print("  %d instants -> %d images distinctes" % (n, len(times)))
    frames = []
    for j, t in enumerate(times):
        png = cairosvg.svg2png(
            bytestring=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s">%s</svg>'
                        % (vb, build_frame(body, kfs, origin, pivots, t))).encode(),
            scale=scale, background_color=bg)
        frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
        if (j + 1) % 25 == 0:
            print("    %d/%d" % (j + 1, len(times)))

    # palette commune : sans elle chaque image embarque la sienne
    # ... ponderee par le temps d'affichage. Les fondus produisent des milliers
    # de teintes intermediaires ; sans ponderation elles noient les couleurs des
    # etats stables, et le vert restaure vire au gris.
    # Le fond occupe 95 % des pixels : un median cut classique lui donne tout et
    # fusionne le bleu du jeton avec le vert restaure. On quantifie donc la liste
    # des couleurs *distinctes* des images stables, chacune comptee une fois.
    hold = [f for f, d in zip(frames, durs) if d >= 15] or frames
    uniq = set()
    for f in hold:
        uniq.update(c for _, c in f.getcolors(1 << 22))
    uniq = sorted(uniq)
    sheet = Image.new("RGB", (len(uniq), 1))
    sheet.putdata(uniq)
    table = list(sheet.quantize(colors=colors, method=Image.MEDIANCUT).getpalette())[:colors * 3]

    # Compter chaque teinte une fois laisse deriver les aplats : le fond blanc
    # ressortait a (250,251,253), assez pour qu'une couture se voie contre la
    # page d'un README. On recale les teintes dominantes sur leur valeur exacte.
    tally = {}
    for f in hold:
        for cnt, col in f.getcolors(1 << 22):
            tally[col] = tally.get(col, 0) + cnt
    taken = set()
    for col in sorted(tally, key=tally.get, reverse=True)[:24]:
        d = [(sum((table[3 * i + k] - col[k]) ** 2 for k in range(3)), i)
             for i in range(colors) if i not in taken]
        if not d:
            break
        i = min(d)[1]
        taken.add(i)
        table[3 * i:3 * i + 3] = list(col)

    # Image.quantize(palette=...) passe par un cache 5 bits par canal : blanc pur
    # et (250,251,253) tombent dans la meme case et le blanc exact est ignore.
    # On fait donc la recherche du plus proche voisin nous memes, sur la liste
    # des couleurs distinctes (quelques milliers), pas sur chaque pixel.
    allc = set()
    for f in frames:
        allc.update(c for _, c in f.getcolors(1 << 22))
    allc = np.array(sorted(allc), dtype=np.int16)
    ptab = np.array(table, dtype=np.int16).reshape(-1, 3)
    idx = np.empty(len(allc), dtype=np.uint8)
    for s0 in range(0, len(allc), 2048):
        chunk = allc[s0:s0 + 2048]
        d2 = ((chunk[:, None, :] - ptab[None, :, :]).astype(np.int32) ** 2).sum(2)
        idx[s0:s0 + 2048] = d2.argmin(1).astype(np.uint8)
    keys = (allc[:, 0].astype(np.uint32) << 16 | allc[:, 1].astype(np.uint32) << 8
            | allc[:, 2].astype(np.uint32))
    order = np.argsort(keys)
    keys, idx = keys[order], idx[order]

    conv = []
    for f in frames:
        a = np.asarray(f, dtype=np.uint32)
        k = (a[:, :, 0] << 16) | (a[:, :, 1] << 8) | a[:, :, 2]
        m = Image.fromarray(idx[np.searchsorted(keys, k.ravel())].reshape(k.shape), "P")
        m.putpalette(table + [0] * (768 - len(table)))
        conv.append(m)
    print("  %d couleurs distinctes -> palette de %d, %d aplats recales"
          % (len(uniq), colors, len(taken)))

    ds = [max(2, int(round(d))) * 10 for d in durs]     # centiemes -> millisecondes
    conv[0].save(out_path, save_all=True, append_images=conv[1:], duration=ds,
                 loop=0, optimize=True, disposal=1)
    kb = os.path.getsize(out_path) / 1024.0
    print("  %s  %dx%d  %.0f Ko" % (out_path, conv[0].width, conv[0].height, kb))
    return out_path


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        sys.exit(1)
    g = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
    render(a[0], a[1], fps=g("--fps", 20.0), scale=g("--scale", 1.0),
           bg=(a[a.index("--bg") + 1] if "--bg" in a else None),
           colors=int(g("--colors", 200)))
