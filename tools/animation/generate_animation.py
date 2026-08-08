#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools>=4.0"]
# ///
"""Animated SVG for a README: PII values are masked before reaching the model
and restored on the way back. Pure CSS keyframes, no JavaScript.

Colour states
  real  (amber)  the raw value, as the user typed it
  mask  (blue)   the placeholder actually sent to the model
  rest  (green)  the value restored on the way back
"""

LOOP = 24.0
FADE_OUT = 22.0
W = 760
GAP_ROWS = 16.0

import os as _os
# Space Grotesk et JetBrains Mono, toutes deux sous licence SIL OFL.
FONT_DIR = _os.environ.get("FONT_DIR", _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "fonts"))
SANS = "'Space Grotesk',sans-serif"
MONO = "'JetBrains Mono',ui-monospace,monospace"
FS, FSM, FSC = 13.5, 11.5, 11.5

DARK = dict(
    text="#E4EAF3", muted="#909DB4",
    userBg="#28303F", aiBg="#1D2431", aiStroke="#2E3746",
    real="#F0AD4A", realBg="#41300F",
    mask="#7FC0FF", maskBg="#16324F",
    rest="#79EE92", restBg="#12402A",
    ai="#B49CFF", aiAvBg="#2B2350",
    avBg="#252D3C", avGlyph="#8A97AC",
    codeBg="#252D3C")
# La bulle de l'assistant doit rester plus claire que la page : sous cette
# valeur la carte s'enfonce dans le fond au lieu de flotter dessus.
PAGE = dict(dark="#151A24", light="#FFFFFF")
LIGHT = dict(
    text="#18202E", muted="#647287",
    userBg="#EDF2F8", aiBg="#FFFFFF", aiStroke="#E2E9F2",
    real="#A65A05", realBg="#FBF0DC",
    mask="#0A58BE", maskBg="#E4EFFC",
    rest="#157F3B", restBg="#E0F4E5",
    ai="#5B36C9", aiAvBg="#EFEAFD",
    avBg="#F1F4F9", avGlyph="#7A879B",
    codeBg="#F4F7FB")

def hue(C, key):
    return C[key], C[key + "Bg"]

# ------------------------------------------------------------------ CSS engine
KF, CL, _uid = [], [], [0]

def _n(p):
    _uid[0] += 1
    return "%s%d" % (p, _uid[0])

def pc(t): return round(max(0.0, min(t, LOOP)) / LOOP * 100, 3)

def cls_appear(tin, tout=FADE_OUT, dy=7.0, ramp=0.40):
    n = _n("e")
    KF.append("@keyframes %s{0%%,%s%%{opacity:0;transform:translateY(%.1fpx)}"
              "%s%%,%s%%{opacity:1;transform:translateY(0)}"
              "%s%%,100%%{opacity:0}}"
              % (n, pc(tin), dy, pc(tin + ramp), pc(tout), pc(tout + 0.55)))
    CL.append(".%s{animation:%s %ss linear infinite}" % (n, n, LOOP))
    return n

# Chronologie d'un basculement, en secondes depuis l'instant du swap.
# L'ordre compte : l'ancienne valeur s'efface et la place se fait AVANT que la
# nouvelle arrive, sinon la fin de ligne glisse par-dessus le texte entrant.
SW_OUT, SW_GAP, SW_IN, SW_END = 0.10, 0.26, 0.28, 0.46

def cls_out(tin, tswap, ramp=0.38):
    """etat visible jusqu'au basculement"""
    n = _n("o")
    KF.append("@keyframes %s{0%%,%s%%{opacity:0}%s%%,%s%%{opacity:1}%s%%,100%%{opacity:0}}"
              % (n, pc(tin), pc(tin + ramp), pc(tswap + SW_OUT), pc(tswap + SW_GAP)))
    CL.append(".%s{animation:%s %ss linear infinite}" % (n, n, LOOP))
    return n

def cls_in(tswap, tout=FADE_OUT):
    """etat qui prend le relais apres le balayage"""
    n = _n("i")
    KF.append("@keyframes %s{0%%,%s%%{opacity:0}%s%%,%s%%{opacity:1}%s%%,100%%{opacity:0}}"
              % (n, pc(tswap + SW_IN), pc(tswap + SW_END), pc(tout), pc(tout + 0.55)))
    CL.append(".%s{animation:%s %ss linear infinite}" % (n, n, LOOP))
    return n

def cls_sweep(tswap, dist, dur=None):
    n = _n("w")
    tswap, dur = tswap + SW_OUT, (SW_END - SW_OUT) if dur is None else dur
    KF.append("@keyframes %s{0%%,%s%%{opacity:0;transform:translateX(0)}"
              "%s%%{opacity:1;transform:translateX(0)}"
              "%s%%{opacity:1;transform:translateX(%.1fpx)}"
              "%s%%,100%%{opacity:0;transform:translateX(%.1fpx)}}"
              % (n, pc(tswap), pc(tswap + 0.05), pc(tswap + dur - 0.05), dist,
                 pc(tswap + dur), dist))
    CL.append(".%s{animation:%s %ss linear infinite}" % (n, n, LOOP))
    return n

SCROLL_DUR = 0.55

def cls_scroll(steps):
    """Defilement du fil. `steps` : (instant, hauteur poussee hors champ).

    Le decalage est cumulatif et ne revient jamais en arriere. Les deux points
    intermediaires imitent une deceleration : l'interpolation reste lineaire
    entre keyframes, donc le rendu est identique dans un navigateur et dans le
    GIF, ce qu'une fonction d'easing CSS ne garantirait pas.
    """
    n = _n("y")
    cum, out = 0.0, ["0%{transform:translateY(0px)}"]
    for t, dy in steps:
        for frac, off in ((0.0, 0.0), (0.40, 0.68), (0.70, 0.92), (1.0, 1.0)):
            out.append("%s%%{transform:translateY(%.2fpx)}"
                       % (pc(t + frac * SCROLL_DUR), -(cum + off * dy)))
        cum += dy
    out.append("100%%{transform:translateY(%.2fpx)}" % -cum)
    KF.append("@keyframes %s{%s}" % (n, "".join(out)))
    CL.append(".%s{animation:%s %ss linear infinite;--dy:%.2fpx}" % (n, n, LOOP, -cum))
    return n


def _kf(name, stops):
    """Construit les keyframes depuis une liste ((debut%, fin%), proprietes).
    Forme explicite : plus aucun risque d'interversion d'arguments positionnels."""
    KF.append("@keyframes %s{%s}" % (name, "".join(
        "%s%%,%s%%{%s}" % (a, b, props) for (a, b), props in stops)))

def cls_tail(tin, tswap, dx, tout=FADE_OUT, ramp=0.40):
    """fin de ligne : se decale pile pendant que la nouvelle pastille apparait,
    sinon elle arrive seule et parait flotter dans le vide."""
    n = _n("t")
    at = "opacity:1;transform:translate(%.2fpx,0px)" % dx
    _kf(n, [((0.0, pc(tin)), "opacity:0;transform:translate(0px,7px)"),
            ((pc(tin + ramp), pc(tswap + SW_OUT)), "opacity:1;transform:translate(0px,0px)"),
            ((pc(tswap + SW_GAP + 0.02), pc(tout)), at),
            ((pc(tout + 0.55), 100.0), "opacity:0;transform:translate(%.2fpx,0px)" % dx)])
    CL.append(".%s{animation:%s %ss linear infinite;--dx:%.2fpx}" % (n, n, LOOP, dx))
    return n

def _window(tswap, early):
    """On fait la place tot, on la reprend tard : la bulle n'est jamais
    plus petite que son contenu pendant la transition."""
    return ((tswap + SW_OUT, tswap + SW_GAP + 0.02) if early
            else (tswap + SW_IN, tswap + SW_END))

def cls_slide(tswap, dx):
    """glissement horizontal seul : la bulle est calee a droite, le contenu suit"""
    n = _n("t")
    t0, t1 = _window(tswap, dx < 0)
    KF.append("@keyframes %s{0%%,%s%%{transform:translateX(0)}"
              "%s%%,100%%{transform:translateX(%.2fpx)}}"
              % (n, pc(t0), pc(t1), dx))
    CL.append(".%s{animation:%s %ss linear infinite;--dx:%.2fpx}" % (n, n, LOOP, dx))
    return n

def cls_scale(tswap, sx, origin):
    """la bulle se retracte ou s etire, bord oppose fixe"""
    n = _n("k")
    t0, t1 = _window(tswap, sx > 1.0)          # elargissement : des le debut
    KF.append("@keyframes %s{0%%,%s%%{transform:scaleX(1)}"
              "%s%%,100%%{transform:scaleX(%.4f)}}"
              % (n, pc(t0), pc(t1), sx))
    CL.append(".%s{animation:%s %ss linear infinite;transform-box:fill-box;"
              "transform-origin:%s center;--sx:%.4f}" % (n, n, LOOP, origin, sx))
    return n

# ------------------------------------------------------------------ text
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# Les largeurs viennent du fichier de police lui-meme. Une table d'avances
# figee dans le code obligerait a la refaire a chaque changement de fonte, et
# une pastille trop etroite deborde de sa bulle sans que le SVG cesse d'etre
# valide : la faute ne se voit qu'a l'oeil.
def _face(name):
    from fontTools.ttLib import TTFont
    import os
    f = TTFont(os.path.join(FONT_DIR, name))
    upem = float(f["head"].unitsPerEm)
    hm, cmap = f["hmtx"], f.getBestCmap()
    adv = dict((chr(c), hm.metrics[n][0] / upem) for c, n in cmap.items() if n in hm.metrics)
    lsb = dict((chr(c), hm.metrics[n][1] / upem) for c, n in cmap.items() if n in hm.metrics)
    return adv, lsb

_SADV, _SLSB = _face("SpaceGrotesk-Medium.ttf")
_MADV, _MLSB = _face("JetBrainsMono-Regular.ttf")

def w_sans(s):
    """Largeur reelle du texte (+0,5 % : cairo arrondit au sous-pixel)."""
    return sum(_SADV.get(c, 0.55) for c in s) * FS * 1.005

def w_mono(s, fs=None):
    fs = FSM if fs is None else fs
    return sum(_MADV.get(c, 0.6) for c in s) * fs * 1.005

PAD, PILL_H, LEAD = 3.5, 18.0, 3.0
PAD_X = 14.0   # rembourrage horizontal des bulles
def pill_w(v, fs=None): return w_mono(v, fs) + 2 * PAD

_PUNCT = (",", ".", ")", ";", ":", "?", "!")
def gap_after(nxt, last=False):
    """`nxt` : le fragment suivant, (genre, texte).

    Une pastille porte deja 3,5 px de marge interne a droite, et la virgule qui
    suit ajoute son approche gauche : le signe finit par flotter loin du mot. On
    retranche les deux pour le recoller. Uniquement dans le texte courant : dans
    le bloc de code la parenthesse fermante doit rester lisible a cote de la
    valeur, pas collee dessus.
    """
    kind, txt = nxt
    if last:
        return 0.0
    if txt[:1] not in _PUNCT:
        return 3.5
    return 0.5 - PAD - _SLSB.get(txt[0], 0.0) * FS if kind == "t" else 0.0

OUT, _CAP = [], [None]
def add(s): (OUT if _CAP[0] is None else _CAP[0]).append(s)

def swap_pill(x, y, va, vb, ka, kb, t_in, t_swap, C, fs):
    """Pastille a deux etats superposes. Renvoie (largeur_a, largeur_b)."""
    ca, ba = hue(C, ka)
    cb, bb = hue(C, kb)
    wa, wb = pill_w(va, fs), pill_w(vb, fs)

    def state(txt, col, bg, wd, cls):
        return ('<g class="%s"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" '
                'fill="%s"/><text x="%.1f" y="%.1f" font-family="%s" font-size="%s" '
                'fill="%s">%s</text></g>'
                % (cls, x, y - 13, wd, PILL_H, bg, x + PAD, y, MONO, fs, col, esc(txt)))

    add(state(va, ca, ba, wa, cls_out(t_in, t_swap)))
    add(state(vb, cb, bb, wb, cls_in(t_swap)))
    add('<g class="%s"><rect x="%.1f" y="%.1f" width="3" height="%.1f" rx="1.5" fill="%s"/></g>'
        % (cls_sweep(t_swap, wb - 3.0), x, y - 13, PILL_H, cb))
    return wa, wb

def _next_seg(segs, i):
    for k, v in segs[i + 1:]:
        return (k, v if isinstance(v, str) else "")
    return ("t", "")

def line_w(segs, states=("real", "mask"), which="a", fs_mono=FSM):
    """Largeur de la ligne dans l'etat 'a' (avant basculement) ou 'b' (apres)."""
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

def render_line(x, y, segs, C, t_in, swaps, states, shift=False, fs_mono=FSM):
    """swaps : instants de basculement, consommes dans l'ordre par les pastilles.
    states : (cle_avant, cle_apres). shift : la fin de ligne suit la largeur."""
    ka, kb = states
    cur, dx, tail_open = x, 0.0, False
    plain, tail = [], []
    si = 0

    for i, (kind, val) in enumerate(segs):
        g = gap_after(_next_seg(segs, i), i == len(segs) - 1)
        if kind == "s":
            ts = swaps[si] if si < len(swaps) else LOOP * 2
            si += 1
            # val est toujours (valeur_reelle, jeton) ; l'etat decide lequel s'affiche
            txt_a = val[1] if ka == "mask" else val[0]
            txt_b = val[1] if kb == "mask" else val[0]
            wa, wb = swap_pill(cur + LEAD, y, txt_a, txt_b, ka, kb, t_in, ts, C, fs_mono)
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
        frag = ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s">%s</text>'
                % (cur, y, ff, fz, col, esc(val)))
        (tail if tail_open else plain).append(frag)
        cur += wd

    # le texte simple apparait avec le message, il ne doit pas etre statique
    if plain:
        add('<g class="%s">%s</g>' % (cls_appear(t_in), "".join(plain)))
    if tail:
        ts = swaps[0] if swaps else LOOP * 2
        add('<g class="%s">%s</g>' % (cls_tail(t_in, ts, dx), "".join(tail)))

# ------------------------------------------------------------------ avatars
def draw_avatar(kind, x, y, C, tin):
    cls = cls_appear(tin, dy=4)
    if kind == "human":
        return ('<g class="%s"><rect x="%.1f" y="%.1f" width="28" height="28" rx="9" fill="%s"/>'
                '<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>'
                '<path d="M%.1f %.1f a5.9 5.9 0 0 1 11.8 0 z" fill="%s"/></g>'
                % (cls, x, y, C["avBg"], x + 14, y + 10.8, C["avGlyph"],
                   x + 8.1, y + 21.6, C["avGlyph"]))
    return ('<g class="%s"><rect x="%.1f" y="%.1f" width="28" height="28" rx="9" fill="%s"/>'
            '<path d="M%.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f '
            'C%.1f %.1f %.1f %.1f %.1f %.1f C%.1f %.1f %.1f %.1f %.1f %.1f Z" fill="%s"/></g>'
            % (cls, x, y, C["aiAvBg"], x + 14, y + 6.4,
               x + 14.6, y + 11.3, x + 16.7, y + 13.4, x + 21.6, y + 14,
               x + 16.7, y + 14.6, x + 14.6, y + 16.7, x + 14, y + 21.6,
               x + 13.4, y + 16.7, x + 11.3, y + 14.6, x + 6.4, y + 14,
               x + 11.3, y + 13.4, x + 13.4, y + 11.3, x + 14, y + 6.4, C["ai"]))

# ------------------------------------------------------------------ scenario
NAME_R, NAME_M = "Marie Dupont", "<<person:1>>"
MAIL_R, MAIL_M = "marie.dupont@acme.fr", "<<email:1>>"

T = dict(m1=0.9, s1=2.6, s2=2.95,
         m2=4.7, s3=6.4,
         m3=8.4,
         m4=10.0,
         m5=12.6,
         m6=14.4, code=15.2, s4=17.0, ok=18.0)

# Quatre bulles tiennent dans le cadre. Les deux dernieres poussent les deux
# premieres hors champ : la conversation defile comme dans une vraie interface.
VISIBLE = 4

# Only the display strings differ per language. NAME/MAIL and the timing keys
# are shared, so the message script stays the same and only the text changes.
LANGS = {
    "en": dict(
        aria="PII values are replaced by placeholders before reaching the model, "
             "then restored for the user and for tool calls",
        greet_user="Hi, I'm", email_intro=", my email is",
        greet_ai="Hello", help_offer=", how can I help?",
        ask="What's the first letter of my first name?",
        refuse="I can't, that name never reaches me.",
        request="Can you email me the summary?",
        confirm="Sure, sending it now."),
    "fr": dict(
        aria="Les valeurs PII sont remplacées par des placeholders avant d'atteindre "
             "le modèle, puis restaurées pour l'utilisateur et pour les appels d'outils",
        greet_user="Bonjour, je suis", email_intro=", mon email est",
        greet_ai="Bonjour", help_offer=", comment puis-je aider ?",
        ask="Quelle est la première lettre de mon prénom ?",
        refuse="Je ne peux pas, ce nom ne m'atteint jamais.",
        request="Peux-tu m'envoyer le résumé par email ?",
        confirm="Bien sûr, je l'envoie."),
}


def make_rows(L):
    """Build the message script for one language from its localized strings.

    The rows carry the animation structure (role, timing key, swap instants,
    optional tool call). Only the displayed text differs per language, so the
    geometry is recomputed from the real glyph widths of the chosen strings.
    """
    return [
        dict(role="human", tin="m1", states=("real", "mask"), swaps=["s1", "s2"],
             lines=[[("t", L["greet_user"]), ("s", (NAME_R, NAME_M)),
                     ("t", L["email_intro"]), ("s", (MAIL_R, MAIL_M))]]),
        dict(role="ai", tin="m2", states=("mask", "rest"), swaps=["s3"],
             lines=[[("t", L["greet_ai"]), ("s", (NAME_R, NAME_M)),
                     ("t", L["help_offer"])]]),
        dict(role="human", tin="m3", states=("real", "mask"), swaps=[],
             lines=[[("t", L["ask"])]]),
        dict(role="ai", tin="m4", states=("mask", "rest"), swaps=[],
             lines=[[("t", L["refuse"])]]),
        dict(role="human", tin="m5", states=("real", "mask"), swaps=[],
             lines=[[("t", L["request"])]]),
        dict(role="ai", tin="m6", states=("mask", "rest"), swaps=[],
             lines=[[("t", L["confirm"])]],
             code=[("v", "send_email"), ("m", "(to="), ("s", (MAIL_R, MAIL_M)), ("m", ")")]),
    ]

CODE_TOP = 28.0      # depuis le haut de la bulle : espace serre sous le texte
CODE_H = 30.0

def build(C, uid, rows, aria):
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

        def row_w(which):
            ws = [line_w(l, st, which) for l in r["lines"]]
            if has_code:
                ws.append(line_w(r["code"], st, which, FSC) + 40)
            return max(ws)

        WA, WB = row_w("a"), row_w("b")
        bw, bw_b = WA + 2 * PAD_X, WB + 2 * PAD_X
        delta = WA - WB                      # > 0 : le contenu se resserre
        resize = abs(delta) > 0.5
        # le redimensionnement suit la pastille qui change de largeur
        t_resize = (swaps[-1] if swaps else T["s4"]) if resize else None
        h = (len(r["lines"]) - 1) * 20 + 38 + (CODE_H + 2 if has_code else 0)

        if r["role"] == "ai":
            bx, ax, origin = 64.0, 24.0, "left"
        else:
            bx, ax, origin = W - 64 - bw, W - 52.0, "right"

        add(draw_avatar("human" if r["role"] == "human" else "ai", ax, y + 5, C, tin))

        # ---- bulle (+ fond du bloc de code) : se retracte ou s'etire, bord oppose fixe
        if r["role"] == "human":
            shell = ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="13" fill="%s"/>'
                     % (bx, y, bw, h, C["userBg"]))
        else:
            shell = ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="13" fill="%s" '
                     'stroke="%s"/>' % (bx + .5, y + .5, bw, h, C["aiBg"], C["aiStroke"]))
        stretch = ['<g class="%s">%s</g>' % (cls_appear(tin), shell)]

        cy = y + CODE_TOP
        if has_code:
            code_cls = cls_appear(T["code"])
            stretch.append('<g class="%s"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                           'rx="8" fill="%s" opacity=".55"/></g>'
                           % (code_cls, bx + 12, cy, bw - 24, CODE_H, C["codeBg"]))
        block = "".join(stretch)
        if resize:
            block = '<g class="%s">%s</g>' % (cls_scale(t_resize, bw_b / bw, origin), block)
        add(block)

        # ---- contenu : cale a gauche dans la bulle, il glisse si la bulle se retracte
        slide = cls_slide(t_resize, delta) if (resize and r["role"] == "human") else None
        buf = []
        if slide:
            _CAP[0] = buf
        for i, ln in enumerate(r["lines"]):
            render_line(bx + PAD_X, y + 23 + i * 20, ln, C, tin + 0.12, swaps, st)
        if slide:
            _CAP[0] = None
            add('<g class="%s">%s</g>' % (slide, "".join(buf)))

        if has_code:
            add('<g class="%s"><rect x="%.1f" y="%.1f" width="2.5" height="16" rx="1.25" '
                'fill="%s"/></g>' % (code_cls, bx + 12, cy + 7, C["ai"]))
            render_line(bx + 26, cy + 20, r["code"], C, T["code"] + 0.12,
                        [T["s4"]], st, shift=True, fs_mono=FSC)
            cw = line_w(r["code"], st, "b", FSC)
            add('<g class="%s"><path d="M%.1f %.1f l3.6 3.6 l7.2 -8" fill="none" stroke="%s" '
                'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></g>'
                % (cls_appear(T["ok"], dy=0), bx + 26 + cw + 12, cy + 16, C["rest"]))

        geom.append((y, h))
        y += h + GAP_ROWS

    # ---- defilement : chaque message au-dela du quatrieme chasse le plus ancien
    steps = [(T[rows[i]["tin"]] - 0.15, geom[i - VISIBLE][1] + GAP_ROWS)
             for i in range(VISIBLE, len(rows))]

    # Le cadre est cale sur l'etat le plus haut : la fenetre ne change pas de
    # taille en cours de route, seul le contenu glisse dessous.
    cum, H = 0.0, 0.0
    for k in range(len(rows) - VISIBLE + 1):
        if k:
            cum += steps[k - 1][1]
        yb, hb = geom[VISIBLE - 1 + k]
        H = max(H, yb + hb - cum + 26)

    scroll = cls_scroll(steps)

    # Le message qui sort n'est pas encore entierement hors cadre quand le
    # suivant arrive : sans ce fondu on verrait une tranche de bulle coupee net
    # sur le bord superieur.
    defs = ('<defs><linearGradient id="g%s" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".55" stop-color="#fff" stop-opacity=".2"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>'
            '<mask id="m%s"><rect x="0" y="0" width="%d" height="26" fill="url(#g%s)"/>'
            '<rect x="0" y="26" width="%d" height="%.0f" fill="#fff"/></mask></defs>'
            % (uid, uid, W, uid, W, H - 26))

    css = ("<style>" + "".join(CL) + "".join(KF) +
           "@media (prefers-reduced-motion:reduce){"
           "*{animation:none!important;opacity:1!important;transform:none!important}"
           "g[class^='o'],g[class^='w']{display:none!important}"
           "g[class^='t']{transform:translateX(var(--dx))!important}"
           "g[class^='k']{transform:scaleX(var(--sx))!important}"
           "g[class^='y']{transform:translateY(var(--dy))!important}}"
           "</style>")
    body = '<g mask="url(#m%s)"><g class="%s">%s</g></g>' % (uid, scroll, "".join(OUT))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %.0f" width="%d" '
            'height="%.0f" role="img" aria-label="%s">%s%s%s</svg>'
            % (W, H, W, H, esc(aria), defs, css, body))


if __name__ == "__main__":
    import argparse
    import io

    parser = argparse.ArgumentParser(description="Render the de-identification "
                                      "chat animation as two SVG files (light + dark).")
    parser.add_argument("--lang", choices=sorted(LANGS), default="en",
                        help="Language of the message script (default: en).")
    parser.add_argument("--out", default=".",
                        help="Output directory for the two SVG files (default: .).")
    ns = parser.parse_args()

    strings = LANGS[ns.lang]
    rows = make_rows(strings)
    for palette, theme in ((DARK, "dark"), (LIGHT, "light")):
        # uid = theme keeps the two mask ids distinct, so the light and dark
        # SVGs can coexist on one page (one shown per colour scheme).
        svg = build(palette, theme, rows, strings["aria"])
        path = "%s/deid-chat-%s.svg" % (ns.out, theme)
        io.open(path, "w", encoding="utf-8").write(svg)
        print(path, len(svg), "bytes")
