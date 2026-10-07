# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.9", "numpy"]
# ///
"""Turn results/scores.jsonl into the tables and plots of the README.

For each guard and each threshold from 0.1 to 0.9 it counts the leaks caught
and the clean texts flagged, by language and by leak type. It adds the
threshold-free AUROC, the false alarms by placeholder density, the latency, a
reliability (calibration) table, and two combinations of a span detector with
a decision model. Rates carry a 95 % Wilson interval.

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
    """Each leaking text against its clean twin, which differs only by the leak."""
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
) -> None:
    """Share flagged on the originals, on the leaking and on the clean de-identified texts."""
    guards = [g for g in summary if g in sources]
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.75 * len(guards)), dpi=150)
    fig.patch.set_alpha(0)
    kinds = (
        ("original, all values in clear", "o", True),
        ("de-identified, one leak", "^", True),
        ("de-identified, clean", "s", False),
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
    ax.set_yticks(range(len(guards)), [NAMES[g] for g in reversed(guards)])
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.6, len(guards) - 0.4)
    ax.set_xlabel(f"share of texts flagged at {t}")
    ax.set_title("Flagged before and after de-identification")
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


def plot_tradeoff(summary: dict[str, dict[str, Any]], path: Path) -> None:
    """Plot leaks caught against false alarms across thresholds, for every guard."""
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
            label=f"{NAMES[guard]} (AUROC {g['auroc']:.2f})",
        )
        for t, x, y in zip(THRESHOLDS, xs, ys):
            if t in (0.1, 0.5, 0.9):
                ax.annotate(
                    f"{t}",
                    (x, y),
                    textcoords="offset points",
                    xytext=(6, -10),
                    fontsize=8,
                    color=INK,
                )
    ax.plot([0, 1], [0, 1], color=INK, linewidth=0.8, linestyle=":")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("False alarms (share of the 100 clean texts flagged)")
    ax.set_ylabel("Leaks caught (share of the 100 leaking texts)")
    ax.set_title("Leaks caught against false alarms, threshold 0.1 to 0.9")
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
) -> str:
    """Render the summary, combinations, meta, paired test and sources as the README markdown."""
    lines = ["# Decision-guard benchmark, results", ""]
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
    pairs = paired(scores, load_twins())
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
            },
            indent=1,
            ensure_ascii=False,
        )
    )
    (HERE / "results" / "report.md").write_text(
        markdown(summary, combo_rows, meta, pairs, sources), encoding="utf-8"
    )
    args.plots.mkdir(parents=True, exist_ok=True)
    shown = {g: summary[g] for g in PLOTTED if g in summary}
    plot_tradeoff(shown, args.plots / "tradeoff.png")
    plot_thresholds(shown, args.plots / "thresholds.png")
    plot_types(shown, args.plots / "leak-types.png")
    plot_density(shown, args.plots / "placeholder-density.png")
    plot_reliability(shown, args.plots / "reliability.png")
    if sources:
        plot_before_after(shown, sources, args.plots / "before-after.png")
    if pairs:
        plot_twins(
            {g: pairs[g] for g in PLOTTED if g in pairs}, args.plots / "twins.png"
        )
    print((HERE / "results" / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
