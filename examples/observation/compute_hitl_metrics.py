# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Compute precision / recall / F1 per label from a HITL dataset JSONL.

Reads records produced by ``export_hitl_dataset.py`` and aggregates,
per label:

* ``tp`` (true positives): model and human agreed on a span and label.
* ``fp`` (false positives): model emitted a span the human deleted or
  relabelled. Model "hallucinated" this entity from the human's POV.
* ``fn`` (false negatives): human added a span the model missed.

It also surfaces a label-confusion matrix when a model span and a
human span share the same character offsets but disagree on the label
(useful to spot systematic mislabelling).

Two matching modes:

* ``strict`` (default): a TP requires exact (start, end, label) match.
* ``lenient``: a TP requires identical labels and span-IoU above a
  configurable threshold (default 0.5). Useful when the human UI lets
  the user pick approximate boundaries.

Usage::

    uv run examples/observation/compute_hitl_metrics.py --input dataset.jsonl

Optional flags::

    --match-mode {strict,lenient}      default strict
    --iou-threshold FLOAT              default 0.5 (lenient mode only)
    --output-format {table,csv,json}   default table
    --output PATH                      write to file instead of stdout
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str

    def iou(self, other: "Span") -> float:
        """Char-level Intersection-over-Union, ignoring labels."""
        inter_start = max(self.start, other.start)
        inter_end = min(self.end, other.end)
        inter = max(0, inter_end - inter_start)
        union = max(self.end, other.end) - min(self.start, other.start)
        return inter / union if union > 0 else 0.0


@dataclass
class LabelStats:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _parse_entities(items: list[list[Any]] | None) -> list[Span]:
    if not items:
        return []
    out: list[Span] = []
    for item in items:
        if len(item) < 3 or item[2] is None:
            continue
        out.append(Span(int(item[0]), int(item[1]), str(item[2])))
    return out


def _match_strict(
    model: list[Span], human: list[Span]
) -> tuple[list[tuple[Span, Span]], list[Span], list[Span]]:
    """Return (matches, model_only, human_only) using exact (start, end, label)."""
    human_keyed: dict[tuple[int, int, str], Span] = {
        (s.start, s.end, s.label): s for s in human
    }
    matches: list[tuple[Span, Span]] = []
    model_only: list[Span] = []
    consumed: set[tuple[int, int, str]] = set()
    for m in model:
        key = (m.start, m.end, m.label)
        if key in human_keyed and key not in consumed:
            matches.append((m, human_keyed[key]))
            consumed.add(key)
        else:
            model_only.append(m)
    human_only = [h for h in human if (h.start, h.end, h.label) not in consumed]
    return matches, model_only, human_only


def _match_lenient(
    model: list[Span], human: list[Span], iou_threshold: float
) -> tuple[list[tuple[Span, Span]], list[Span], list[Span]]:
    """Greedy IoU matching, requiring label equality and IoU >= threshold."""
    pairs: list[tuple[float, int, int]] = []
    for i, m in enumerate(model):
        for j, h in enumerate(human):
            if m.label != h.label:
                continue
            score = m.iou(h)
            if score >= iou_threshold:
                pairs.append((score, i, j))
    pairs.sort(reverse=True)

    matched_model: set[int] = set()
    matched_human: set[int] = set()
    matches: list[tuple[Span, Span]] = []
    for _, i, j in pairs:
        if i in matched_model or j in matched_human:
            continue
        matches.append((model[i], human[j]))
        matched_model.add(i)
        matched_human.add(j)

    model_only = [m for i, m in enumerate(model) if i not in matched_model]
    human_only = [h for j, h in enumerate(human) if j not in matched_human]
    return matches, model_only, human_only


def aggregate(
    records: list[dict[str, Any]],
    *,
    match_mode: str = "strict",
    iou_threshold: float = 0.5,
) -> tuple[dict[str, LabelStats], dict[tuple[str, str], int]]:
    """Aggregate per-label TP/FP/FN and label-confusion counts."""
    per_label: dict[str, LabelStats] = defaultdict(LabelStats)
    confusion: dict[tuple[str, str], int] = defaultdict(int)

    for rec in records:
        model = _parse_entities(rec.get("model_entities"))
        human = _parse_entities(rec.get("entities"))

        if match_mode == "strict":
            matches, model_only, human_only = _match_strict(model, human)
        elif match_mode == "lenient":
            matches, model_only, human_only = _match_lenient(
                model, human, iou_threshold
            )
        else:
            raise ValueError(f"Unknown match_mode: {match_mode!r}")

        for m, _ in matches:
            per_label[m.label].tp += 1
        for m in model_only:
            # Same span, different label → record the label change.
            same_span = next(
                (h for h in human_only if h.start == m.start and h.end == m.end),
                None,
            )
            if same_span is not None:
                confusion[(m.label, same_span.label)] += 1
            per_label[m.label].fp += 1
        for h in human_only:
            per_label[h.label].fn += 1

    return per_label, confusion


def macro_avg(per_label: dict[str, LabelStats]) -> dict[str, float]:
    if not per_label:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    n = len(per_label)
    return {
        "precision": sum(s.precision for s in per_label.values()) / n,
        "recall": sum(s.recall for s in per_label.values()) / n,
        "f1": sum(s.f1 for s in per_label.values()) / n,
    }


def micro_avg(per_label: dict[str, LabelStats]) -> dict[str, float]:
    tp = sum(s.tp for s in per_label.values())
    fp = sum(s.fp for s in per_label.values())
    fn = sum(s.fn for s in per_label.values())
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": p, "recall": r, "f1": f1}


def render_table(
    per_label: dict[str, LabelStats],
    confusion: dict[tuple[str, str], int],
) -> str:
    if not per_label:
        return "(no records)"
    header = f"{'label':<20s} {'tp':>6} {'fp':>6} {'fn':>6} {'P':>6} {'R':>6} {'F1':>6}"
    sep = "-" * len(header)
    lines = [header, sep]
    for label in sorted(per_label):
        s = per_label[label]
        lines.append(
            f"{label:<20s} {s.tp:>6d} {s.fp:>6d} {s.fn:>6d}"
            f" {s.precision:>6.2f} {s.recall:>6.2f} {s.f1:>6.2f}"
        )
    lines.append(sep)
    macro = macro_avg(per_label)
    micro = micro_avg(per_label)
    lines.append(
        f"{'macro avg':<20s} {'-':>6} {'-':>6} {'-':>6}"
        f" {macro['precision']:>6.2f} {macro['recall']:>6.2f} {macro['f1']:>6.2f}"
    )
    lines.append(
        f"{'micro avg':<20s} {'-':>6} {'-':>6} {'-':>6}"
        f" {micro['precision']:>6.2f} {micro['recall']:>6.2f} {micro['f1']:>6.2f}"
    )
    if confusion:
        lines.append("")
        lines.append("Label confusion (model -> human, same span):")
        for (m, h), n in sorted(confusion.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {m} -> {h}: {n}")
    return "\n".join(lines)


def render_csv(per_label: dict[str, LabelStats]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["label", "tp", "fp", "fn", "precision", "recall", "f1"])
    for label in sorted(per_label):
        s = per_label[label]
        w.writerow(
            [
                label,
                s.tp,
                s.fp,
                s.fn,
                f"{s.precision:.4f}",
                f"{s.recall:.4f}",
                f"{s.f1:.4f}",
            ]
        )
    macro = macro_avg(per_label)
    micro = micro_avg(per_label)
    w.writerow([])
    w.writerow(
        [
            "macro avg",
            "",
            "",
            "",
            f"{macro['precision']:.4f}",
            f"{macro['recall']:.4f}",
            f"{macro['f1']:.4f}",
        ]
    )
    w.writerow(
        [
            "micro avg",
            "",
            "",
            "",
            f"{micro['precision']:.4f}",
            f"{micro['recall']:.4f}",
            f"{micro['f1']:.4f}",
        ]
    )
    return buf.getvalue()


def render_json(
    per_label: dict[str, LabelStats],
    confusion: dict[tuple[str, str], int],
) -> str:
    confusion_nested: dict[str, dict[str, int]] = defaultdict(dict)
    for (model_label, human_label), count in confusion.items():
        confusion_nested[model_label][human_label] = count
    payload = {
        "per_label": {
            label: {
                "tp": s.tp,
                "fp": s.fp,
                "fn": s.fn,
                "precision": s.precision,
                "recall": s.recall,
                "f1": s.f1,
            }
            for label, s in per_label.items()
        },
        "macro_avg": macro_avg(per_label),
        "micro_avg": micro_avg(per_label),
        "label_confusion": dict(confusion_nested),
    }
    return json.dumps(payload, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSONL file produced by export_hitl_dataset.py.",
    )
    parser.add_argument(
        "--match-mode",
        choices=["strict", "lenient"],
        default="strict",
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.5,
        help="Span-IoU floor in lenient mode (default 0.5).",
    )
    parser.add_argument(
        "--output-format",
        choices=["table", "csv", "json"],
        default="table",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the report to this path instead of stdout.",
    )
    args = parser.parse_args()

    records: list[dict[str, Any]] = []
    with args.input.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))

    per_label, confusion = aggregate(
        records,
        match_mode=args.match_mode,
        iou_threshold=args.iou_threshold,
    )

    if args.output_format == "table":
        out = render_table(per_label, confusion)
    elif args.output_format == "csv":
        out = render_csv(per_label)
    else:
        out = render_json(per_label, confusion)

    if args.output is None:
        print(out)
    else:
        args.output.write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
