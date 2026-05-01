# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "langfuse>=3.0",
#     "python-dotenv>=1.0",
# ]
# ///
"""Export HITL traces from Langfuse into a NER training JSONL dataset.

Each ``piighost.hitl_correction`` trace carries everything we need:

* ``input.text`` — the raw user message, not redacted.
* ``input.labels`` — the detector's label vocabulary at the time of the
  correction (empty list for detectors that do not expose ``labels``).
* ``input.detections`` — the model's detections (with redacted text);
  positions remain exploitable.
* ``output.detections`` — the human-corrected detections in the same
  shape; this is the ground truth we want.

The script writes one JSON object per trace, in the spaCy-friendly
``{"text": ..., "entities": [[start, end, label], ...]}`` shape, plus a
``model_entities`` list and the ``labels_universe`` for that trace.

Usage::

    LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... \
        uv run examples/observation/export_hitl_dataset.py \
            --output hitl_dataset.jsonl

Optional flags:

    --since YYYY-MM-DD     Skip traces older than this date.
    --limit N              Stop after N traces (default: no cap).
    --tag TAG              Override the trace tag filter (default: hitl).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse


def _check_env() -> None:
    missing = [
        v for v in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not os.getenv(v)
    ]
    if missing:
        sys.exit(
            "Missing env vars: " + ", ".join(missing) + ". "
            "Set them with the keys from your Langfuse project (Settings → API Keys)."
        )


def _entities_from_detections(detections: list[dict[str, Any]]) -> list[list[Any]]:
    """Convert ``[{label, position: [start, end], ...}, ...]`` to ``[[s, e, l], ...]``."""
    out: list[list[Any]] = []
    for det in detections:
        pos = det.get("position") or [det.get("start_pos"), det.get("end_pos")]
        if pos is None or pos[0] is None or pos[1] is None:
            continue
        out.append([int(pos[0]), int(pos[1]), det.get("label")])
    return out


def _record_from_trace(trace: Any) -> dict[str, Any] | None:
    """Build a JSONL record from one trace, or ``None`` if it is malformed."""
    raw_input = getattr(trace, "input", None) or {}
    raw_output = getattr(trace, "output", None) or {}
    if not isinstance(raw_input, dict) or not isinstance(raw_output, dict):
        return None

    text = raw_input.get("text")
    if not isinstance(text, str) or not text:
        return None

    return {
        "text": text,
        "entities": _entities_from_detections(raw_output.get("detections", [])),
        "model_entities": _entities_from_detections(raw_input.get("detections", [])),
        "labels_universe": list(raw_input.get("labels") or []),
        "trace_id": getattr(trace, "id", None),
        "session_id": getattr(trace, "session_id", None),
        "created_at": getattr(trace, "createdAt", None),
    }


def main() -> None:
    load_dotenv()
    _check_env()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSONL file path to write the dataset to.",
    )
    parser.add_argument(
        "--tag",
        default="hitl",
        help="Trace tag to filter on (default: hitl).",
    )
    parser.add_argument(
        "--since",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Skip traces older than this ISO date (e.g. 2026-04-01).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N traces.",
    )
    args = parser.parse_args()

    client = Langfuse()
    fetch_kwargs: dict[str, Any] = {"tags": [args.tag]}
    if args.since is not None:
        fetch_kwargs["from_timestamp"] = args.since

    traces = client.api.trace.list(**fetch_kwargs).data
    if args.limit is not None:
        traces = traces[: args.limit]

    written = 0
    skipped = 0
    with args.output.open("w", encoding="utf-8") as fh:
        for trace in traces:
            record = _record_from_trace(trace)
            if record is None:
                skipped += 1
                continue
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"Wrote {written} records to {args.output} ({skipped} skipped).")


if __name__ == "__main__":
    main()
