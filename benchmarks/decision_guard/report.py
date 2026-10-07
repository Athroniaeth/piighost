# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.9", "numpy"]
# ///
"""Turn results/scores.jsonl into the tables and plots of the README.

For each guard and each threshold from 0.1 to 0.9 it counts the leaks caught
and the clean texts flagged, by language and by leak type. It adds the
threshold-free AUROC, the false alarms by placeholder density, the latency, a
reliability (calibration) table, and combinations of a span detector with a
decision model. Rates carry a 95 % Wilson interval.

The texts come from 28 templates, so texts of one template are not
independent. The report therefore also gives:

- intervals from a cluster bootstrap, which resamples whole templates
  (2,000 resamples), for the AUROC and the rates;
- a held-out evaluation, leave one template out: the threshold is chosen on
  the other 27 templates (the most leaks caught with at most 5 % false alarms
  there) and applied to the template left out, then the counts are summed
  over the 28 templates. A threshold read off the full table is chosen on the
  test data and is optimistic, this one is not;
- the same rule across languages, chosen on French and applied to English,
  and the other way round;
- paired tests with a p-value: each leak against its clean twin, and each
  original document against its de-identified version (exact two-sided sign
  test, ties dropped, Wilcoxon signed-rank as a check, and a sign test on the
  28 template means, which does not assume texts of a template independent).

Nothing here re-runs a model. It all reads the saved scores.

Run with:
uv run benchmarks/decision_guard/report.py [--plots DIR]
"""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes

HERE = Path(__file__).parent
THRESHOLDS = [round(0.1 * i, 1) for i in range(1, 10)]
GUARDS = (
    "laya-en",
    "laya-en-hint",
    "laya-multi",
    "gliner2-guard",
    "gliner2-spans",
    "gliner2-spans-ph",
)
NAMES = {
    "laya-en": "Laya (English)",
    "laya-en-hint": "Laya, placeholder hint",
    "laya-multi": "laya-multilingual",
    "gliner2-guard": "Gliner2GuardRail",
    "gliner2-spans": "GLiNER2 spans, raw",
    "gliner2-spans-ph": "GLiNER2 spans, placeholders ignored",
}
NAMES_FR = {
    "laya-en": "Laya (anglais)",
    "laya-en-hint": "Laya, indice sur les placeholders",
    "laya-multi": "laya-multilingual",
    "gliner2-guard": "Gliner2GuardRail",
    "gliner2-spans": "Spans GLiNER2, bruts",
    "gliner2-spans-ph": "Spans GLiNER2, placeholders ignorés",
}
TEXT = {
    "en": {
        "names": NAMES,
        "kinds": (
            "original, all values in clear",
            "de-identified, one leak",
            "de-identified, clean",
        ),
        "flagged_at": "share of texts flagged at {t}",
        "before_after_title": "Flagged before and after de-identification",
        "alarms_axis": "False alarms (share of the 100 clean texts flagged)",
        "caught_axis": "Leaks caught (share of the 100 leaking texts)",
        "tradeoff_title": "Leaks caught against false alarms, threshold 0.1 to 0.9",
    },
    "fr": {
        "names": NAMES_FR,
        "kinds": (
            "original, valeurs en clair",
            "dé-identifié, une fuite",
            "dé-identifié, propre",
        ),
        "flagged_at": "part des textes signalés au seuil {t}",
        "before_after_title": "Signalés avant et après la dé-identification",
        "alarms_axis": "Fausses alertes (part des 100 textes propres signalés)",
        "caught_axis": "Fuites rattrapées (part des 100 textes qui fuient)",
        "tradeoff_title": "Fuites rattrapées et fausses alertes, seuil de 0,1 à 0,9",
    },
}
"""Plot labels per language, for the plots the articles embed."""


def num(x: float, lang: str, digits: int | None = None) -> str:
    """Format a number for a plot label, with a decimal comma in French."""
    text = f"{x:.{digits}f}" if digits is not None else f"{x}"
    return text.replace(".", ",") if lang == "fr" else text


# Validated with the dataviz validator against #fcfcfb and #1a1a19: all checks
# pass in both modes, so the PNGs stay readable on a light or a dark page.
INK = "#8a8a86"
"""Mid grey: over 3:1 against both a white and a near-black page."""
COLOURS = {
    "laya-en": "#3987e5",
    "laya-multi": "#9085e9",
    "gliner2-guard": "#d95926",
    "gliner2-spans-ph": "#199e70",
    "gliner2-spans": INK,
}
MARKERS = {
    "laya-en": "o",
    "laya-multi": "s",
    "gliner2-guard": "^",
    "gliner2-spans-ph": "D",
    "gliner2-spans": "x",
}
PLOTTED = ("laya-en", "laya-multi", "gliner2-guard", "gliner2-spans-ph")
"""The guards drawn on the plots, four so each keeps a distinct colour."""
LEAK_ORDER = (
    "name",
    "variant",
    "partial",
    "email",
    "phone",
    "iban",
    "address",
    "id",
    "split",
)
DENSITY = (("4 to 6", 4, 6), ("7 to 8", 7, 8), ("11 to 15", 11, 15))
BOOTSTRAP = 2000
SEED = 20261007
MAX_ALARMS = 0.05
"""The held-out rule: catch the most leaks with at most this share of false alarms."""


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Return the Wilson score interval for k successes out of n, at confidence z."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def auroc(pos: list[float], neg: list[float]) -> float:
    """Return the AUROC, the share of pairs where the positive outranks the negative, ties counted half."""
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def rate(rows: list[dict], t: float) -> tuple[int, int]:
    """Return the count and total of rows whose score is at or above t."""
    k = sum(r["score"] >= t for r in rows)
    return k, len(rows)


def load() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Load the texts and the guards' scores, joined with the texts' labels."""
    texts = {
        r["id"]: r
        for r in map(json.loads, (HERE / "data" / "texts.jsonl").open(encoding="utf-8"))
    }
    scores = defaultdict(list)
    for s in map(
        json.loads, (HERE / "results" / "scores.jsonl").open(encoding="utf-8")
    ):
        scores[s["guard"]].append(
            {
                **s,
                **{
                    k: texts[s["id"]][k]
                    for k in (
                        "lang",
                        "template",
                        "leak",
                        "leak_type",
                        "leak_span",
                        "placeholders",
                        "text",
                    )
                },
            }
        )
    return texts, {g: scores[g] for g in GUARDS if scores.get(g)}


def summarise(scores: dict[str, list[dict]]) -> dict[str, dict[str, Any]]:
    """Build the per-guard summary: AUROC, threshold sweep, latency and reliability."""
    out = {}
    for guard, rows in scores.items():
        leaks = [r for r in rows if r["leak"]]
        clean = [r for r in rows if not r["leak"]]
        g = {
            "n": len(rows),
            "auroc": auroc([r["score"] for r in leaks], [r["score"] for r in clean]),
            "auroc_by_lang": {
                lang: auroc(
                    [r["score"] for r in leaks if r["lang"] == lang],
                    [r["score"] for r in clean if r["lang"] == lang],
                )
                for lang in ("fr", "en")
            },
            "sweep": [],
        }
        for t in THRESHOLDS:
            row = {"threshold": t}
            for lang in ("all", "fr", "en"):
                lk = [r for r in leaks if lang == "all" or r["lang"] == lang]
                cl = [r for r in clean if lang == "all" or r["lang"] == lang]
                caught, n_leak = rate(lk, t)
                alarms, n_clean = rate(cl, t)
                row[lang] = {
                    "caught": caught,
                    "leaks": n_leak,
                    "catch_ci": wilson(caught, n_leak),
                    "false_alarms": alarms,
                    "clean": n_clean,
                    "alarm_ci": wilson(alarms, n_clean),
                }
            row["by_type"] = {
                lt: rate([r for r in leaks if r["leak_type"] == lt], t)
                for lt in LEAK_ORDER
            }
            row["alarms_by_density"] = {
                name: rate([r for r in clean if lo <= r["placeholders"] <= hi], t)
                for name, lo, hi in DENSITY
            }
            g["sweep"].append(row)
        lat = sorted(r["latency_s"] for r in rows)
        g["latency"] = {
            "median_s": lat[len(lat) // 2],
            "p90_s": lat[int(len(lat) * 0.9)],
            "max_s": lat[-1],
        }
        g["reliability"] = reliability(rows)
        if guard.startswith("gliner2-spans"):
            g["spans"] = span_detail(rows)
        if guard.startswith("laya"):
            g["truncated"] = sum(bool(r.get("truncated")) for r in rows)
        out[guard] = g
    return out


def reliability(rows: list[dict], bins: int = 10) -> dict[str, Any]:
    """Bucket rows by score into bins and return the calibration error and Brier score."""
    table = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        inside = [
            r
            for r in rows
            if lo <= r["score"] < hi or (b == bins - 1 and r["score"] == 1.0)
        ]
        if inside:
            table.append(
                {
                    "bin": [lo, hi],
                    "n": len(inside),
                    "mean_score": sum(r["score"] for r in inside) / len(inside),
                    "leak_share": sum(r["leak"] for r in inside) / len(inside),
                }
            )
    n = len(rows)
    ece = sum(abs(t["mean_score"] - t["leak_share"]) * t["n"] / n for t in table)
    brier = sum((r["score"] - r["leak"]) ** 2 for r in rows) / n
    return {"bins": table, "ece": ece, "brier": brier}


def span_detail(rows: list[dict], t: float = 0.5) -> dict[str, Any]:
    """Did the span guard point at the leak, and did it fire on placeholders?"""
    caught = located = 0
    placeholder_alarms = other_alarms = 0
    for r in rows:
        hits = [d for d in r["detections"] if d["confidence"] >= t]
        if r["leak"] and hits:
            caught += 1
            s, e = r["leak_span"]
            located += any(d["start"] < e and d["end"] > s for d in hits)
        if not r["leak"] and hits:
            if any("<<" in d["text"] or ">>" in d["text"] for d in hits):
                placeholder_alarms += 1
            else:
                other_alarms += 1
    return {
        "threshold": t,
        "caught": caught,
        "located": located,
        "clean_alarms_touching_placeholder": placeholder_alarms,
        "clean_alarms_other": other_alarms,
    }


COMBOS = (
    ("or", "gliner2-spans-ph", 0.9, "laya-en", 0.9),
    ("or", "gliner2-spans-ph", 0.9, "gliner2-guard", 0.5),
    ("and", "gliner2-spans-ph", 0.5, "laya-en", 0.5),
    ("and", "gliner2-spans-ph", 0.7, "laya-en", 0.7),
    ("or", "gliner2-guard", 0.5, "laya-en", 0.9),
)
"""Two guards together: OR flags when either fires, AND only when both do."""


def combos(scores: dict[str, list[dict]]) -> list[dict[str, Any]]:
    """Score each guard combination in COMBOS against the leaks and clean texts."""
    by_id = {g: {r["id"]: r for r in rows} for g, rows in scores.items()}
    out = []
    for op, a, ta, b, tb in COMBOS:
        if a not in by_id or b not in by_id:
            continue
        flags = []
        for i, row in by_id[a].items():
            fa, fb = row["score"] >= ta, by_id[b][i]["score"] >= tb
            flags.append((fa or fb if op == "or" else fa and fb, row["leak"]))
        out.append(
            {
                "rule": f"{NAMES[a]} >= {ta} {op.upper()} {NAMES[b]} >= {tb}",
                "caught": sum(f and l for f, l in flags),
                "leaks": sum(l for _, l in flags),
                "false_alarms": sum(f and not l for f, l in flags),
                "clean": sum(not l for _, l in flags),
            }
        )
    return out


def best_alone(rows: list[dict], caught: int) -> dict[str, Any]:
    """Return the guard's own threshold that catches at least `caught` leaks with the fewest false alarms."""
    best = None
    for t in sorted({r["score"] for r in rows}):
        k = sum(r["score"] >= t for r in rows if r["leak"])
        fa = sum(r["score"] >= t for r in rows if not r["leak"])
        if k >= caught and (best is None or fa <= best["false_alarms"]):
            best = {"threshold": t, "caught": k, "false_alarms": fa}
    return best or {"threshold": math.nan, "caught": 0, "false_alarms": 0}


def combo_sweep(
    scores: dict[str, list[dict]],
    spans: str = "gliner2-spans-ph",
    laya: str = "laya-en",
) -> list[dict[str, Any]]:
    """Sweep the decision model's threshold in OR and AND rules, each against the span detector alone.

    For every rule, the last columns give the span detector's own threshold
    that catches as many leaks with the fewest false alarms. When it has fewer
    false alarms than the rule, adding the decision model did not pay.
    """
    if spans not in scores or laya not in scores:
        return []
    other = {r["id"]: r["score"] for r in scores[laya]}
    out = []
    for op, ts, tls in (
        ("or", 0.9, (0.5, 0.6, 0.7, 0.8, 0.9)),
        ("and", None, (0.5, 0.6, 0.7, 0.8, 0.9)),
    ):
        for tl in tls:
            t_spans = ts if ts is not None else tl
            flags = []
            for r in scores[spans]:
                fa, fb = r["score"] >= t_spans, other[r["id"]] >= tl
                flags.append((fa or fb if op == "or" else fa and fb, r["leak"]))
            caught = sum(f and leak for f, leak in flags)
            alone = best_alone(scores[spans], caught)
            out.append(
                {
                    "rule": f"spans >= {t_spans} {op.upper()} Laya >= {tl}",
                    "op": op,
                    "spans_threshold": t_spans,
                    "laya_threshold": tl,
                    "caught": caught,
                    "false_alarms": sum(f and not leak for f, leak in flags),
                    "spans_alone": alone,
                }
            )
    return out


def template_of(row: dict) -> str:
    """Return the key of the template a text was filled from, such as fr-03."""
    return f"{row['lang']}-{row['template']:02d}"


def by_template(rows: list[dict]) -> dict[str, list[dict]]:
    """Group rows by the template their text was filled from."""
    out = defaultdict(list)
    for r in rows:
        out[template_of(r)].append(r)
    return dict(out)


def auroc_fast(pos: np.ndarray, neg: np.ndarray) -> float:
    """Return the AUROC of two score arrays, ties counted half, NaN when one is empty."""
    if not len(pos) or not len(neg):
        return math.nan
    diff = pos[:, None] - neg[None, :]
    return float(((diff > 0) + 0.5 * (diff == 0)).mean())


POSITIONS = ("low", "mid", "high")
"""Where the threshold sits in the gap the training data leaves open, see choose_threshold."""


def choose_threshold(
    rows: list[dict], position: str = "mid", max_alarms: float = MAX_ALARMS
) -> float:
    """Return the threshold that catches the most leaks with at most max_alarms false alarms.

    Any threshold above the clean score that must not be flagged, and up to
    the next score seen in training, gives the same training counts. The
    training data cannot choose inside that gap, so `position` does: "low"
    just above the clean score, "high" at the next score, "mid" halfway, the
    default. The report gives all three, because a held-out text can fall in
    the gap.
    """
    clean = sorted((r["score"] for r in rows if not r["leak"]), reverse=True)
    allowed = int(max_alarms * len(clean))
    if allowed >= len(clean):
        return min(r["score"] for r in rows)
    lo = clean[allowed]
    above = [r["score"] for r in rows if r["score"] > lo]
    hi = min(above) if above else math.inf
    just_above = float(np.nextafter(lo, math.inf))
    if position == "low" or hi == math.inf:
        return just_above if position != "high" else hi
    return hi if position == "high" else (lo + hi) / 2


def held_out(rows: list[dict], position: str = "mid") -> dict[str, Any]:
    """Leave one template out: choose the threshold on the other 27, flag the one left out."""
    groups = by_template(rows)
    flags, thresholds = {}, {}
    for key, test in groups.items():
        train = [r for k, g in groups.items() if k != key for r in g]
        t = choose_threshold(train, position)
        thresholds[key] = t
        for r in test:
            flags[r["id"]] = r["score"] >= t
    leaks = [r for r in rows if r["leak"]]
    clean = [r for r in rows if not r["leak"]]
    ts = sorted(thresholds.values())
    return {
        "rule": f"most leaks caught with at most {MAX_ALARMS:.0%} false alarms on the training templates",
        "position": position,
        "caught": sum(flags[r["id"]] for r in leaks),
        "leaks": len(leaks),
        "false_alarms": sum(flags[r["id"]] for r in clean),
        "clean": len(clean),
        "threshold_min": ts[0],
        "threshold_median": ts[len(ts) // 2],
        "threshold_max": ts[-1],
        "flags": flags,
    }


def across_languages(rows: list[dict]) -> list[dict[str, Any]]:
    """Choose the threshold on one language with the held-out rule, apply it to the other."""
    out = []
    for train_lang, test_lang in (("fr", "en"), ("en", "fr")):
        train = [r for r in rows if r["lang"] == train_lang]
        test = [r for r in rows if r["lang"] == test_lang]
        x = {
            "chosen_on": train_lang,
            "applied_to": test_lang,
            "leaks": sum(r["leak"] for r in test),
            "clean": sum(not r["leak"] for r in test),
        }
        for position in POSITIONS:
            t = choose_threshold(train, position)
            x[position] = {
                "threshold": t,
                "caught": sum(r["score"] >= t for r in test if r["leak"]),
                "false_alarms": sum(r["score"] >= t for r in test if not r["leak"]),
            }
        out.append(x)
    return out


def cluster_bootstrap(
    rows: list[dict], flags: dict[str, bool]
) -> dict[str, tuple[float, float]]:
    """Resample whole templates and return 95 % percentile intervals.

    The statistics are the AUROC, the catch rate and the false-alarm rate at
    0.5 and at 0.9, and the held-out catch and false-alarm rates (the held-out
    flags stay fixed, so that interval leaves out the variation of the chosen
    threshold).
    """
    groups = list(by_template(rows).values())
    arrays = [
        (
            np.array([r["score"] for r in g]),
            np.array([r["leak"] for r in g], dtype=bool),
            np.array([flags[r["id"]] for r in g], dtype=bool),
        )
        for g in groups
    ]
    rng = np.random.default_rng(SEED)
    draws = defaultdict(list)
    for _ in range(BOOTSTRAP):
        pick = rng.integers(0, len(arrays), len(arrays))
        score = np.concatenate([arrays[i][0] for i in pick])
        leak = np.concatenate([arrays[i][1] for i in pick])
        flag = np.concatenate([arrays[i][2] for i in pick])
        if not leak.any() or leak.all():
            continue
        draws["auroc"].append(auroc_fast(score[leak], score[~leak]))
        for t in (0.5, 0.9):
            draws[f"caught_{t}"].append(float((score[leak] >= t).mean()))
            draws[f"alarms_{t}"].append(float((score[~leak] >= t).mean()))
        draws["held_out_caught"].append(float(flag[leak].mean()))
        draws["held_out_alarms"].append(float(flag[~leak].mean()))
    return {
        k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))
        for k, v in draws.items()
    }


def sign_test(wins: int, losses: int) -> float:
    """Return the exact two-sided sign-test p-value for wins against losses, ties dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1))
    return min(1.0, 2 * tail / 2**n)


def wilcoxon(diffs: list[float]) -> float:
    """Return the two-sided p-value of the Wilcoxon signed-rank test, normal approximation.

    Zero differences are dropped, tied absolute values share their mean rank,
    and the variance carries the tie correction.
    """
    d = np.array([x for x in diffs if x != 0])
    n = len(d)
    if n == 0:
        return 1.0
    absd = np.abs(d)
    order = absd.argsort()
    ranks = np.empty(n)
    sorted_abs = absd[order]
    i = 0
    ties = 0.0
    while i < n:
        j = i
        while j + 1 < n and sorted_abs[j + 1] == sorted_abs[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        size = j - i + 1
        ties += size**3 - size
        i = j + 1
    w_plus = ranks[d > 0].sum()
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24 - ties / 48
    if var == 0:
        return 1.0
    z = (w_plus - mean) / math.sqrt(var)
    return math.erfc(abs(z) / math.sqrt(2))


def paired_stats(pairs: list[tuple[float, float, str]]) -> dict[str, Any]:
    """Compare paired scores (a, b, template): counts, sign test, Wilcoxon, template-level sign test."""
    wins = sum(a > b for a, b, _ in pairs)
    losses = sum(a < b for a, b, _ in pairs)
    per_template = defaultdict(list)
    for a, b, key in pairs:
        per_template[key].append(a - b)
    means = [sum(v) / len(v) for v in per_template.values()]
    t_wins = sum(m > 0 for m in means)
    t_losses = sum(m < 0 for m in means)
    return {
        "n": len(pairs),
        "a_higher": wins,
        "ties": len(pairs) - wins - losses,
        "b_higher": losses,
        "sign_p": sign_test(wins, losses),
        "wilcoxon_p": wilcoxon([a - b for a, b, _ in pairs]),
        "templates": len(means),
        "templates_a_higher": t_wins,
        "templates_b_higher": t_losses,
        "template_sign_p": sign_test(t_wins, t_losses),
    }


def significance(
    scores: dict[str, list[dict]], twins: dict[str, dict[str, float]]
) -> dict[str, dict[str, Any]]:
    """Paired tests per guard: leak against twin, and de-identified clean text against its original."""
    sources = defaultdict(dict)
    path = HERE / "results" / "scores-sources.jsonl"
    if path.exists():
        for s in map(json.loads, path.open(encoding="utf-8")):
            sources[s["guard"]][s["id"].removesuffix("-source")] = s["score"]
    out = {}
    for guard, rows in scores.items():
        g = {}
        tw = twins.get(guard, {})
        pairs = [
            (r["score"], tw[r["id"]], template_of(r))
            for r in rows
            if r["leak"] and r["id"] in tw
        ]
        if pairs:
            g["leak_vs_twin"] = paired_stats(pairs)
        src = sources.get(guard, {})
        pairs = [
            (r["score"], src[r["id"]], template_of(r))
            for r in rows
            if not r["leak"] and r["id"] in src
        ]
        if pairs:
            g["deidentified_vs_original"] = paired_stats(pairs)
        out[guard] = g
    return out


def robustness(scores: dict[str, list[dict]]) -> dict[str, dict[str, Any]]:
    """Held-out thresholds, threshold transfer across languages and cluster intervals, per guard."""
    out = {}
    for guard, rows in scores.items():
        h = held_out(rows)
        out[guard] = {
            "held_out": {k: v for k, v in h.items() if k != "flags"},
            "held_out_by_position": {
                p: {
                    k: v
                    for k, v in held_out(rows, p).items()
                    if k in ("caught", "false_alarms")
                }
                for p in POSITIONS
            },
            "across_languages": across_languages(rows),
            "cluster_ci": cluster_bootstrap(rows, h["flags"]),
        }
    return out


def load_sources() -> dict[str, dict[str, Any]]:
    """Load the guards' scores on the source documents, before de-identification."""
    path = HERE / "results" / "scores-sources.jsonl"
    if not path.exists():
        return {}
    out = defaultdict(list)
    for s in map(json.loads, path.open(encoding="utf-8")):
        out[s["guard"]].append(s["score"])
    return {
        g: {
            "n": len(v),
            "flagged_at_0.5": sum(x >= 0.5 for x in v),
            "mean_score": sum(v) / len(v),
        }
        for g, v in out.items()
    }


def load_twins() -> dict[str, dict[str, float]]:
    """Load each guard's score on every clean twin, keyed by guard and text id."""
    path = HERE / "results" / "scores-twins.jsonl"
    if not path.exists():
        return {}
    twins = defaultdict(dict)
    for s in map(json.loads, path.open(encoding="utf-8")):
        twins[s["guard"]][s["id"].removesuffix("-twin")] = s["score"]
    return twins


def paired(
    scores: dict[str, list[dict]], twins: dict[str, dict[str, float]], t: float = 0.5
) -> dict[str, dict[str, Any]]:
    """Each leaking text against its clean twin, where the leak is one more placeholder."""
    out = {}
    for guard, rows in scores.items():
        if guard not in twins:
            continue
        pairs = [
            (r["score"], twins[guard][r["id"]], r["leak_type"])
            for r in rows
            if r["leak"] and r["id"] in twins[guard]
        ]
        if not pairs:
            continue
        higher = sum((a > b) + 0.5 * (a == b) for a, b, _ in pairs)
        flips = sum(a >= t and b < t for a, b, _ in pairs)
        both = sum(a >= t and b >= t for a, b, _ in pairs)
        by_type = {}
        for lt in LEAK_ORDER:
            sub = [(a, b) for a, b, x in pairs if x == lt]
            if sub:
                by_type[lt] = {
                    "n": len(sub),
                    "leak_higher": sum((a > b) + 0.5 * (a == b) for a, b in sub),
                    "mean_delta": sum(a - b for a, b in sub) / len(sub),
                }
        out[guard] = {
            "n": len(pairs),
            "leak_scored_higher": higher,
            "mean_delta": sum(a - b for a, b, _ in pairs) / len(pairs),
            "twin_flagged_at_0.5": sum(b >= t for _, b, _ in pairs),
            "only_leak_flagged_at_0.5": flips,
            "both_flagged_at_0.5": both,
            "by_type": by_type,
            "points": [(a, b) for a, b, _ in pairs],
        }
    return out


def plot_twins(pairs: dict[str, dict[str, Any]], path: Path) -> None:
    """Plot each guard's score on a leaking text against its clean twin."""
    guards = list(pairs)
    fig, axes = plt.subplots(
        1, len(guards), figsize=(3.2 * len(guards), 3.5), dpi=150, sharey=True
    )
    fig.patch.set_alpha(0)
    for ax, guard in zip(np.atleast_1d(axes), guards):
        p = pairs[guard]
        xs = [b for _, b in p["points"]]
        ys = [a for a, _ in p["points"]]
        ax.plot([0, 1], [0, 1], color=INK, linewidth=0.8, linestyle=":")
        ax.scatter(
            xs,
            ys,
            s=16,
            color=COLOURS[guard],
            marker=MARKERS[guard],
            alpha=0.8,
            edgecolors="none",
        )
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_title(
            f"{NAMES[guard]}\nleak higher in {p['leak_scored_higher']:g}/{p['n']} pairs (ties half)",
            fontsize=9,
        )
        ax.set_xlabel("score of the clean twin")
        style(ax)
    np.atleast_1d(axes)[0].set_ylabel("score of the leaking text")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def plot_before_after(
    summary: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    path: Path,
    t: float = 0.5,
    lang: str = "en",
) -> None:
    """Share flagged on the originals, on the leaking and on the clean de-identified texts."""
    words = TEXT[lang]
    guards = [g for g in summary if g in sources]
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.75 * len(guards)), dpi=150)
    fig.patch.set_alpha(0)
    kinds = tuple(
        zip(words["kinds"], ("o", "^", "s"), (True, True, False), strict=True)
    )
    for y, guard in enumerate(reversed(guards)):
        row = next(r for r in summary[guard]["sweep"] if r["threshold"] == t)["all"]
        values = (
            sources[guard]["flagged_at_0.5"] / sources[guard]["n"],
            row["caught"] / row["leaks"],
            row["false_alarms"] / row["clean"],
        )
        ax.plot([min(values), max(values)], [y, y], color=INK, linewidth=0.8, alpha=0.5)
        for (label, marker, filled), v in zip(kinds, values):
            ax.scatter(
                [v],
                [y],
                s=70,
                marker=marker,
                color=COLOURS[guard] if filled else "none",
                edgecolors=COLOURS[guard],
                linewidths=1.6,
                zorder=3,
            )
    ax.set_yticks(range(len(guards)), [words["names"][g] for g in reversed(guards)])
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.6, len(guards) - 0.4)
    ax.set_xlabel(words["flagged_at"].format(t=num(t, lang)))
    ax.set_title(words["before_after_title"])
    if lang == "fr":
        ax.xaxis.set_major_formatter(lambda x, _: num(round(x, 1), lang))
    style(ax)
    for tick in ax.get_yticklabels():
        tick.set_color(INK)
    from matplotlib.lines import Line2D

    handles = [
        Line2D(
            [],
            [],
            linestyle="none",
            marker=m,
            markersize=8,
            markerfacecolor=INK if f else "none",
            markeredgecolor=INK,
            markeredgewidth=1.6,
            label=label,
        )
        for label, m, f in kinds
    ]
    leg = ax.legend(
        handles=handles,
        frameon=False,
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.3),
        ncol=3,
    )
    for text in leg.get_texts():
        text.set_color(INK)
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def style(ax: Axes) -> None:
    """Apply the benchmark's muted, transparent style to a plot axis."""
    ax.set_facecolor("none")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK)
    ax.tick_params(colors=INK, labelsize=9)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    ax.title.set_color(INK)
    ax.grid(color=INK, alpha=0.2, linewidth=0.6)


def legend(ax: Axes, **kw: Any) -> None:
    """Draw a frameless legend on ax, coloured to match the benchmark's style."""
    leg = ax.legend(frameon=False, fontsize=9, **kw)
    for text in leg.get_texts():
        text.set_color(INK)


def plot_tradeoff(
    summary: dict[str, dict[str, Any]], path: Path, lang: str = "en"
) -> None:
    """Plot leaks caught against false alarms across thresholds, for every guard."""
    words = TEXT[lang]
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    fig.patch.set_alpha(0)
    for guard, g in summary.items():
        xs = [r["all"]["false_alarms"] / r["all"]["clean"] for r in g["sweep"]]
        ys = [r["all"]["caught"] / r["all"]["leaks"] for r in g["sweep"]]
        ax.plot(
            xs,
            ys,
            color=COLOURS[guard],
            marker=MARKERS[guard],
            markersize=6,
            linewidth=2,
            label=f"{words['names'][guard]} (AUROC {num(g['auroc'], lang, 2)})",
        )
        for t, x, y in zip(THRESHOLDS, xs, ys):
            if t in (0.1, 0.5, 0.9):
                ax.annotate(
                    num(t, lang),
                    (x, y),
                    textcoords="offset points",
                    xytext=(6, -10),
                    fontsize=8,
                    color=INK,
                )
    ax.plot([0, 1], [0, 1], color=INK, linewidth=0.8, linestyle=":")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel(words["alarms_axis"])
    ax.set_ylabel(words["caught_axis"])
    ax.set_title(words["tradeoff_title"])
    if lang == "fr":
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_formatter(lambda x, _: num(round(x, 1), lang))
    style(ax)
    legend(ax, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def plot_thresholds(summary: dict[str, dict[str, Any]], path: Path) -> None:
    """Plot leaks caught and false alarms against threshold, one panel per guard."""
    fig, axes = plt.subplots(
        1, len(summary), figsize=(3.2 * len(summary), 3.4), dpi=150, sharey=True
    )
    fig.patch.set_alpha(0)
    for ax, (guard, g) in zip(np.atleast_1d(axes), summary.items()):
        caught = [r["all"]["caught"] / r["all"]["leaks"] for r in g["sweep"]]
        alarms = [r["all"]["false_alarms"] / r["all"]["clean"] for r in g["sweep"]]
        ax.plot(
            THRESHOLDS,
            caught,
            color=COLOURS[guard],
            linewidth=2,
            marker="o",
            markersize=5,
            label="leaks caught",
        )
        ax.plot(
            THRESHOLDS,
            alarms,
            color=COLOURS[guard],
            linewidth=2,
            linestyle="--",
            marker="x",
            markersize=6,
            label="false alarms",
        )
        ax.set_title(NAMES[guard], fontsize=10)
        ax.set_xlabel("threshold")
        ax.set_ylim(-0.02, 1.02)
        style(ax)
        legend(ax, loc="center left")
    np.atleast_1d(axes)[0].set_ylabel("share of texts")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def plot_types(summary: dict[str, dict[str, Any]], path: Path, t: float = 0.5) -> None:
    """Plot leaks caught at threshold t, broken down by leak type, for every guard."""
    guards = list(summary)
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=150)
    fig.patch.set_alpha(0)
    width = 0.8 / len(guards)
    x = np.arange(len(LEAK_ORDER))
    for i, guard in enumerate(guards):
        row = next(r for r in summary[guard]["sweep"] if r["threshold"] == t)
        vals = [row["by_type"][lt][0] / row["by_type"][lt][1] for lt in LEAK_ORDER]
        ax.bar(
            x + (i - (len(guards) - 1) / 2) * width,
            vals,
            width * 0.9,
            color=COLOURS[guard],
            label=NAMES[guard],
        )
    ns = next(r for r in summary[guards[0]]["sweep"] if r["threshold"] == t)["by_type"]
    ax.set_xticks(x, [f"{lt}\n(n={ns[lt][1]})" for lt in LEAK_ORDER])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(f"leaks caught at {t}")
    ax.set_title(f"Leaks caught by type of leak, threshold {t}")
    style(ax)
    legend(ax, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=len(guards))
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def plot_density(
    summary: dict[str, dict[str, Any]], path: Path, t: float = 0.5
) -> None:
    """Plot false alarms at threshold t, broken down by placeholder density, for every guard."""
    guards = list(summary)
    fig, ax = plt.subplots(figsize=(7, 4.4), dpi=150)
    fig.patch.set_alpha(0)
    width = 0.8 / len(guards)
    x = np.arange(len(DENSITY))
    for i, guard in enumerate(guards):
        row = next(r for r in summary[guard]["sweep"] if r["threshold"] == t)
        vals = [
            row["alarms_by_density"][name][0] / row["alarms_by_density"][name][1]
            for name, _, _ in DENSITY
        ]
        ax.bar(
            x + (i - (len(guards) - 1) / 2) * width,
            vals,
            width * 0.9,
            color=COLOURS[guard],
            label=NAMES[guard],
        )
    ns = next(r for r in summary[guards[0]]["sweep"] if r["threshold"] == t)[
        "alarms_by_density"
    ]
    ax.set_xticks(
        x, [f"{name} placeholders\n(n={ns[name][1]})" for name, _, _ in DENSITY]
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(f"clean texts flagged at {t}")
    ax.set_title("False alarms on clean texts, by number of placeholders")
    style(ax)
    legend(ax, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def plot_reliability(summary: dict[str, dict[str, Any]], path: Path) -> None:
    """Plot each guard's calibration curve, score against the leak share observed."""
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(6, 6), dpi=150)
    handles = [
        Line2D(
            [], [], color=INK, linewidth=0.8, linestyle=":", label="perfect calibration"
        )
    ]
    fig.patch.set_alpha(0)
    ax.plot([0, 1], [0, 1], color=INK, linewidth=0.8, linestyle=":")
    for guard in ("laya-en", "laya-multi", "gliner2-guard", "gliner2-spans-ph"):
        if guard not in summary:
            continue
        rel = summary[guard]["reliability"]
        xs = [b["mean_score"] for b in rel["bins"]]
        ys = [b["leak_share"] for b in rel["bins"]]
        sizes = [12 + 4 * b["n"] for b in rel["bins"]]
        ax.plot(xs, ys, color=COLOURS[guard], linewidth=1.5)
        ax.scatter(
            xs,
            ys,
            s=sizes,
            color=COLOURS[guard],
            marker=MARKERS[guard],
            edgecolors="none",
        )
        handles.append(
            Line2D(
                [],
                [],
                color=COLOURS[guard],
                marker=MARKERS[guard],
                markersize=6,
                linewidth=1.5,
                label=f"{NAMES[guard]} (ECE {rel['ece']:.2f})",
            )
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("score the guard gave (bin mean)")
    ax.set_ylabel("share of texts in the bin that leak")
    ax.set_title(
        "Reliability: do 80 % of the texts scored 0.8 leak?\nmarker area grows with the texts in the bin",
        fontsize=10,
    )
    style(ax)
    leg = ax.legend(
        handles=handles,
        frameon=False,
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
    )
    for text in leg.get_texts():
        text.set_color(INK)
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def pct(k: int, n: int) -> str:
    """Format k out of n as a fraction and a percentage."""
    return f"{k}/{n} ({100 * k / n:.0f} %)"


def markdown(
    summary: dict[str, dict[str, Any]],
    combo_rows: list[dict[str, Any]],
    meta: dict[str, Any],
    pairs: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    robust: dict[str, dict[str, Any]],
    tests: dict[str, dict[str, Any]],
    sweep: list[dict[str, Any]],
) -> str:
    """Render the summary, combinations, meta, paired tests, robustness and sources as the README markdown."""
    lines = ["# Decision-guard benchmark, results", ""]
    lines += [
        "## Held out by template",
        "",
        (
            "The threshold is chosen on 27 templates, the most leaks caught with at most "
            f"{MAX_ALARMS:.0%} false alarms there, and applied to the template left out. "
            "It sits halfway in the gap the training scores leave open, the last column gives "
            "the counts at the low and the high end of that gap. "
            "The counts are summed over the 28 templates. Intervals come from a cluster "
            f"bootstrap over the templates ({BOOTSTRAP:,} resamples, the held-out flags fixed)."
        ),
        "",
        "| Guard | AUROC (cluster 95 % CI) | Caught, held out | 95 % CI | False alarms, held out | 95 % CI | Thresholds chosen (min, median, max) | Threshold low / high in the gap, caught and false alarms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for guard, g in summary.items():
        rb = robust[guard]
        h, ci = rb["held_out"], rb["cluster_ci"]
        lines.append(
            f"| {NAMES[guard]} | {g['auroc']:.2f} ({ci['auroc'][0]:.2f} to {ci['auroc'][1]:.2f}) "
            f"| {pct(h['caught'], h['leaks'])} | {ci['held_out_caught'][0]:.2f} to {ci['held_out_caught'][1]:.2f} "
            f"| {pct(h['false_alarms'], h['clean'])} | {ci['held_out_alarms'][0]:.2f} to {ci['held_out_alarms'][1]:.2f} "
            f"| {h['threshold_min']:.3f}, {h['threshold_median']:.3f}, {h['threshold_max']:.3f} "
            f"| {rb['held_out_by_position']['low']['caught']}/{rb['held_out_by_position']['low']['false_alarms']}"
            f" and {rb['held_out_by_position']['high']['caught']}/{rb['held_out_by_position']['high']['false_alarms']} |"
        )
    lines += [
        "",
        "Fixed thresholds, with cluster bootstrap intervals (in sample, the thresholds were not chosen on other data):",
        "",
        "| Guard | Caught at 0.5 | False alarms at 0.5 | Caught at 0.9 | False alarms at 0.9 |",
        "|---|---|---|---|---|",
    ]
    for guard, g in summary.items():
        ci = robust[guard]["cluster_ci"]
        cells = []
        for t in (0.5, 0.9):
            a = next(r for r in g["sweep"] if r["threshold"] == t)["all"]
            cells.append(
                f"{a['caught']}/{a['leaks']} ({ci[f'caught_{t}'][0]:.2f} to {ci[f'caught_{t}'][1]:.2f})"
            )
            cells.append(
                f"{a['false_alarms']}/{a['clean']} ({ci[f'alarms_{t}'][0]:.2f} to {ci[f'alarms_{t}'][1]:.2f})"
            )
        lines.append(f"| {NAMES[guard]} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "The same rule across languages, the threshold chosen on one language and applied to the other:",
        "",
        "| Guard | Chosen on | Applied to | Threshold (mid) | Caught | False alarms | Low end: threshold, caught, false alarms | High end: threshold, caught, false alarms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for guard in summary:
        for x in robust[guard]["across_languages"]:
            m, lo, hi = x["mid"], x["low"], x["high"]
            lines.append(
                f"| {NAMES[guard]} | {x['chosen_on'].upper()} | {x['applied_to'].upper()} | {m['threshold']:.3f} "
                f"| {m['caught']}/{x['leaks']} | {m['false_alarms']}/{x['clean']} "
                f"| {lo['threshold']:.3f}, {lo['caught']}, {lo['false_alarms']} "
                f"| {hi['threshold']:.3f}, {hi['caught']}, {hi['false_alarms']} |"
            )
    lines += [
        "",
        "## Paired tests",
        "",
        (
            "Exact two-sided sign test, ties dropped. Wilcoxon signed-rank (normal approximation) as a check. "
            "The template-level sign test compares the mean gap of each of the 28 templates, so it does not "
            "assume that texts of one template are independent."
        ),
        "",
        "| Guard | Pair | Pairs | First higher / tie / second higher | Sign test p | Wilcoxon p | Templates, first higher / second higher | Template sign test p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for guard, t in tests.items():
        for key, label in (
            ("leak_vs_twin", "leak vs clean twin"),
            ("deidentified_vs_original", "de-identified clean vs original"),
        ):
            if key in t:
                x = t[key]
                lines.append(
                    f"| {NAMES[guard]} | {label} | {x['n']} | {x['a_higher']} / {x['ties']} / {x['b_higher']} "
                    f"| {x['sign_p']:.2g} | {x['wilcoxon_p']:.2g} "
                    f"| {x['templates_a_higher']} / {x['templates_b_higher']} | {x['template_sign_p']:.2g} |"
                )
    if sweep:
        lines += [
            "",
            "## Adding Laya to the span detector, or lowering its threshold",
            "",
            (
                "Each rule, then the span detector alone at the threshold that catches at least as many leaks "
                "with the fewest false alarms (in sample)."
            ),
            "",
            "| Rule | Caught | False alarms | Spans alone, threshold | Caught | False alarms |",
            "|---|---|---|---|---|---|",
        ]
        for c in sweep:
            a = c["spans_alone"]
            lines.append(
                f"| {c['rule']} | {c['caught']}/100 | {c['false_alarms']}/100 | {a['threshold']:.3f} "
                f"| {a['caught']}/100 | {a['false_alarms']}/100 |"
            )
    lines += [""]
    lines += [
        "## At a glance",
        "",
        "| Guard | AUROC | AUROC FR | AUROC EN | Caught at 0.5 | False alarms at 0.5 | Median latency |",
        "|---|---|---|---|---|---|---|",
    ]
    for guard, g in summary.items():
        r = next(r for r in g["sweep"] if r["threshold"] == 0.5)["all"]
        lines.append(
            f"| {NAMES[guard]} | {g['auroc']:.2f} | {g['auroc_by_lang']['fr']:.2f} | {g['auroc_by_lang']['en']:.2f} "
            f"| {pct(r['caught'], r['leaks'])} | {pct(r['false_alarms'], r['clean'])} | {1000 * g['latency']['median_s']:.0f} ms |"
        )
    for guard, g in summary.items():
        lines += [
            "",
            f"## {NAMES[guard]}",
            "",
            "| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in g["sweep"]:
            a, fr, en = r["all"], r["fr"], r["en"]
            lines.append(
                f"| {r['threshold']} | {pct(a['caught'], a['leaks'])} | {a['catch_ci'][0]:.2f} to {a['catch_ci'][1]:.2f} "
                f"| {pct(a['false_alarms'], a['clean'])} | {a['alarm_ci'][0]:.2f} to {a['alarm_ci'][1]:.2f} "
                f"| {fr['caught']}/{fr['leaks']} | {fr['false_alarms']}/{fr['clean']} | {en['caught']}/{en['leaks']} | {en['false_alarms']}/{en['clean']} |"
            )
        r5 = next(r for r in g["sweep"] if r["threshold"] == 0.5)
        lines += [
            "",
            "Caught at 0.5 by leak type: "
            + ", ".join(f"{lt} {k}/{n}" for lt, (k, n) in r5["by_type"].items())
            + ".",
        ]
        lines += [
            "False alarms at 0.5 by placeholder count: "
            + ", ".join(
                f"{name} {k}/{n}" for name, (k, n) in r5["alarms_by_density"].items()
            )
            + "."
        ]
        lat = g["latency"]
        lines += [
            f"Latency per text: median {1000 * lat['median_s']:.0f} ms, p90 {1000 * lat['p90_s']:.0f} ms, max {1000 * lat['max_s']:.0f} ms."
        ]
        rel = g["reliability"]
        lines += [
            f"Calibration: ECE {rel['ece']:.3f}, Brier {rel['brier']:.3f}. Bins (score range, n, mean score, share leaking): "
            + "; ".join(
                f"{b['bin'][0]:.1f}-{b['bin'][1]:.1f} n={b['n']} {b['mean_score']:.2f}/{b['leak_share']:.2f}"
                for b in rel["bins"]
            )
            + "."
        ]
        if "truncated" in g:
            lines += [f"Texts truncated by Laya's window: {g['truncated']}."]
        if "spans" in g:
            s = g["spans"]
            lines += [
                (
                    f"At 0.5, {s['located']} of the {s['caught']} leaks caught had a detection on the leaked value itself. "
                    f"Clean texts flagged: {s['clean_alarms_touching_placeholder']} with a detection touching a placeholder, {s['clean_alarms_other']} on other text."
                )
            ]
    if combo_rows:
        lines += [
            "",
            "## Combinations",
            "",
            "| Rule | Caught | False alarms |",
            "|---|---|---|",
        ]
        for c in combo_rows:
            lines.append(
                f"| {c['rule']} | {pct(c['caught'], c['leaks'])} | {pct(c['false_alarms'], c['clean'])} |"
            )
    if pairs:
        lines += [
            "",
            "## Paired test, each leak against its clean twin",
            "",
            "| Guard | Pairs | Leak scored higher | Mean score gap | Twin flagged at 0.5 | Only the leak flagged at 0.5 |",
            "|---|---|---|---|---|---|",
        ]
        for guard, p in pairs.items():
            lines.append(
                f"| {NAMES[guard]} | {p['n']} | {p['leak_scored_higher']:.1f} | {p['mean_delta']:+.3f} | {p['twin_flagged_at_0.5']} | {p['only_leak_flagged_at_0.5']} |"
            )
        for guard, p in pairs.items():
            lines += [
                "",
                f"{NAMES[guard]}, leak scored higher than its twin, by type: "
                + ", ".join(
                    f"{lt} {v['leak_higher']:.1f}/{v['n']} (gap {v['mean_delta']:+.2f})"
                    for lt, v in p["by_type"].items()
                )
                + ".",
            ]
    if sources:
        lines += [
            "",
            "## The documents before de-identification, every value in clear",
            "",
            "| Guard | Documents | Flagged at 0.5 | Mean score |",
            "|---|---|---|---|",
        ]
        for guard, v in sources.items():
            lines.append(
                f"| {NAMES[guard]} | {v['n']} | {v['flagged_at_0.5']} | {v['mean_score']:.2f} |"
            )
    if meta:
        lines += [
            "",
            "## Run",
            "",
            "```json",
            json.dumps(meta, indent=2, ensure_ascii=False),
            "```",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Parse arguments, compute the summary and write the report, the JSON and the plots."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--plots", type=Path, default=HERE / "results" / "plots")
    args = parser.parse_args()
    _, scores = load()
    summary = summarise(scores)
    combo_rows = combos(scores)
    twins = load_twins()
    pairs = paired(scores, twins)
    robust = robustness(scores)
    tests = significance(scores, twins)
    sweep = combo_sweep(scores)
    sources = load_sources()
    meta_path = HERE / "results" / "run-meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    paired_out = {
        g: {k: v for k, v in p.items() if k != "points"} for g, p in pairs.items()
    }
    (HERE / "results" / "summary.json").write_text(
        json.dumps(
            {
                "guards": summary,
                "combinations": combo_rows,
                "paired": paired_out,
                "sources": sources,
                "robustness": robust,
                "paired_tests": tests,
                "combination_sweep": sweep,
            },
            indent=1,
            ensure_ascii=False,
        )
    )
    (HERE / "results" / "report.md").write_text(
        markdown(summary, combo_rows, meta, pairs, sources, robust, tests, sweep),
        encoding="utf-8",
    )
    args.plots.mkdir(parents=True, exist_ok=True)
    shown = {g: summary[g] for g in PLOTTED if g in summary}
    plot_tradeoff(shown, args.plots / "tradeoff.png")
    plot_tradeoff(shown, args.plots / "tradeoff-fr.png", lang="fr")
    plot_thresholds(shown, args.plots / "thresholds.png")
    plot_types(shown, args.plots / "leak-types.png")
    plot_density(shown, args.plots / "placeholder-density.png")
    plot_reliability(shown, args.plots / "reliability.png")
    if sources:
        plot_before_after(shown, sources, args.plots / "before-after.png")
        plot_before_after(shown, sources, args.plots / "before-after-fr.png", lang="fr")
    if pairs:
        plot_twins(
            {g: pairs[g] for g in PLOTTED if g in pairs}, args.plots / "twins.png"
        )
    print((HERE / "results" / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
