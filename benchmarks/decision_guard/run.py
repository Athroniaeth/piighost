# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[gliner2]", "laya==0.3.28"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Run every guard rail on every de-identified text and record its score.

Four guards, each behind piighost's AnyGuardRail port, each asked about the
same 200 texts:

- laya-en: LayaGuardRail from examples/guard_rail_laya.py, unchanged, the
  same question, the English checkpoint.
- laya-multi: the same guard on the laya-multilingual checkpoint.
- laya-en-hint: the same guard and checkpoint, with one sentence added to the
  question saying that tokens such as <<PERSON:1>> are placeholders, not
  personal data, the hint LLMGuardRail's prompt carries.
- gliner2-guard: Gliner2GuardRail, the GLiNER2 safety classifier (whether).
- gliner2-spans: DetectorGuardRail over Gliner2PiiDetector, a span detector
  re-run on the output (where), asked for the six kinds of value the Laya
  question names.
- gliner2-spans-ph: the same detector, with every detection that is only a
  placeholder (fewer than two letters or digits once the placeholders are
  taken out) dropped. Only a guard that knows where it fired can do this.

Each call goes through the guard's async check(), one text at a time, after a
warm-up call, and its wall time is recorded. Scores are written to
results/scores.jsonl, one line per guard and text. A run resumes: a guard and
text already scored are skipped.

The same guards also score data/twins.jsonl, the clean twin of each leaking
text, into results/scores-twins.jsonl, with --twins. With --sources they score
the source document of each clean text, before de-identification, every value
in clear, into results/scores-sources.jsonl: a bar any guard should clear.

Run with:
uv run benchmarks/decision_guard/run.py            # every guard
uv run benchmarks/decision_guard/run.py laya-en    # one guard
uv run benchmarks/decision_guard/run.py --twins    # the clean twins
uv run benchmarks/decision_guard/run.py --sources  # the documents before de-identification
"""

import asyncio
import json
import platform
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "examples"))

from guard_rail_laya import QUESTION, LayaGuardRail

from piighost.components.detector import AnyDetector
from piighost.components.detector.ner.gliner2 import Gliner2PiiDetector
from piighost.components.guard import AnyGuardRail, DetectorGuardRail, GuardVerdict
from piighost.components.guard.gliner2 import Gliner2GuardRail

TWINS = "--twins" in sys.argv
SOURCES = "--sources" in sys.argv
DATA = HERE / "data" / ("twins.jsonl" if TWINS else "texts.jsonl")
OUT = (
    HERE
    / "results"
    / (
        "scores-twins.jsonl"
        if TWINS
        else "scores-sources.jsonl"
        if SOURCES
        else "scores.jsonl"
    )
)
META = HERE / "results" / "run-meta.json"

SPAN_LABELS = {
    "PERSON": "person",
    "EMAIL": "email address",
    "PHONE": "phone number",
    "ADDRESS": "street address",
    "IBAN": "iban",
    "ID_NUMBER": "social security number",
}
"""The six kinds of value the Laya question names, in the detector's words."""

SPAN_FLOOR = 0.1
"""The span detector keeps detections down to this confidence, for the sweep."""


PLACEHOLDER = re.compile(r"<<[A-Z_]+:\d+>>")


class PlaceholderAwareGuardRail:
    """Re-run a detector, ignoring what it finds on the placeholders themselves.

    A span detector tags <<PERSON:1>> as a person. Because each detection
    says where it is, the guard can drop the ones that hold nothing but
    placeholders and punctuation, and flag on the rest.
    """

    def __init__(self, detector: AnyDetector) -> None:
        """Store the detector the guard re-runs on each text."""
        self.detector = detector

    async def check(self, text: str) -> GuardVerdict:
        """Flag the text when the detector finds something beyond the placeholders."""
        found = await self.detector.detect(text)
        residual = tuple(
            d
            for d in found
            if len(re.sub(r"[\W_]", "", PLACEHOLDER.sub("", d.text))) >= 2
        )
        return GuardVerdict(flagged=bool(residual), detections=residual)


class MultilingualLayaGuardRail(LayaGuardRail):
    """The example's guard on the laya-multilingual checkpoint, same question."""

    async def check(self, text: str) -> GuardVerdict:
        """Ask the question on the multilingual checkpoint and return the verdict."""
        question = {"pii": {"type": "noul", "instructions": QUESTION}}
        result = await asyncio.to_thread(
            self.router.predict, text, question, model="multilingual"
        )
        self.last = result
        score = result["answers"]["pii"]["noul"]
        return GuardVerdict(flagged=score >= self.threshold, score=score)


HINTED_QUESTION = (
    QUESTION + " Tokens such as <<PERSON:1>> or <<EMAIL:2>> are placeholders that "
    "replaced personal data. They are not personal data."
)


class HintedLayaGuardRail(LayaGuardRail):
    """The example's guard and checkpoint, told that placeholders are not PII."""

    async def check(self, text: str) -> GuardVerdict:
        """Ask the hinted question on the English checkpoint and return the verdict."""
        question = {"pii": {"type": "noul", "instructions": HINTED_QUESTION}}
        result = await asyncio.to_thread(
            self.router.predict, text, question, model="english"
        )
        self.last = result
        score = result["answers"]["pii"]["noul"]
        return GuardVerdict(flagged=score >= self.threshold, score=score)


class RecordingLayaGuardRail(LayaGuardRail):
    """The example's guard, keeping Laya's last raw answer for the usage block."""

    async def check(self, text: str) -> GuardVerdict:
        """Check the text while recording Laya's last raw answer on self.last."""
        original = self.router.predict

        def predict(*args: Any, **kwargs: Any) -> Any:
            self.last = original(*args, **kwargs)
            return self.last

        self.router.predict = predict
        try:
            return await super().check(text)
        finally:
            self.router.predict = original


class RecordingGliner2GuardRail(Gliner2GuardRail):
    """Gliner2GuardRail, keeping the label so P(unsafe) can be swept.

    The guard's score is the confidence of the label it chose. With two
    exclusive labels, P(unsafe) is that score when the label is unsafe and one
    minus it when the label is safe.
    """

    async def check(self, text: str) -> GuardVerdict:
        """Check the text while recording the model's last raw answer on self.last."""
        original = self.model.classify_text

        def classify(*args: Any, **kwargs: Any) -> Any:
            self.last = original(*args, **kwargs)
            return self.last

        self.model.classify_text = classify
        try:
            return await super().check(text)
        finally:
            del self.model.classify_text


def laya_extra(guard: LayaGuardRail) -> dict:
    """Return the truncation flag and input token count from the guard's last answer."""
    usage = guard.last.get("usage", {})
    return {
        "truncated": usage.get("truncated"),
        "input_tokens": usage.get("input_tokens"),
    }


def gliner_extra(guard: RecordingGliner2GuardRail, verdict: GuardVerdict) -> dict:
    """Return the label and the probability of unsafe from the guard's last answer."""
    answer = guard.last.get(guard.task) or {}
    label = answer.get("label")
    p_unsafe = verdict.score if label == "unsafe" else 1.0 - verdict.score
    return {"label": label, "p_unsafe": p_unsafe}


def spans_extra(verdict: GuardVerdict) -> dict:
    """Return the verdict's detections as plain dicts, for JSON output."""
    return {
        "detections": [
            {
                "start": d.span.start,
                "end": d.span.end,
                "text": d.text,
                "label": d.label,
                "confidence": d.confidence,
            }
            for d in verdict.detections
        ]
    }


def build(name: str) -> AnyGuardRail:
    """Return the guard instance named name, or exit if the name is unknown."""
    if name == "laya-en":
        return RecordingLayaGuardRail()
    if name == "laya-en-hint":
        return HintedLayaGuardRail()
    if name == "laya-multi":
        return MultilingualLayaGuardRail()
    if name == "gliner2-guard":
        return RecordingGliner2GuardRail()
    if name == "gliner2-spans":
        return DetectorGuardRail(
            Gliner2PiiDetector(labels=SPAN_LABELS, threshold=SPAN_FLOOR)
        )
    if name == "gliner2-spans-ph":
        return PlaceholderAwareGuardRail(
            Gliner2PiiDetector(labels=SPAN_LABELS, threshold=SPAN_FLOOR)
        )
    raise SystemExit(f"unknown guard {name}")


GUARDS = (
    "laya-en",
    "laya-en-hint",
    "laya-multi",
    "gliner2-guard",
    "gliner2-spans",
    "gliner2-spans-ph",
)


async def run(name: str, rows: list[dict], done: set[tuple[str, str]]) -> None:
    """Score every row in rows with the guard named name, skipping ids already in done."""
    todo = [r for r in rows if (name, r["id"]) not in done]
    if not todo:
        print(f"{name}: nothing to do")
        return
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        guard = build(name)
        await guard.check("Warm-up text, <<PERSON:1>> wrote to <<EMAIL:1>>.")
    load = time.perf_counter() - started
    notes = sorted({str(w.message) for w in caught if "laya" in str(w.message).lower()})
    print(f"{name}: loaded and warmed up in {load:.1f} s")
    with OUT.open("a", encoding="utf-8") as handle:
        for i, row in enumerate(todo, 1):
            t0 = time.perf_counter()
            verdict = await guard.check(row["text"])
            latency = time.perf_counter() - t0
            if name.startswith("gliner2-spans"):
                score = max((d.confidence for d in verdict.detections), default=0.0)
                extra = spans_extra(verdict)
            elif name == "gliner2-guard":
                extra = gliner_extra(guard, verdict)
                score = extra["p_unsafe"]
            else:
                score = verdict.score
                extra = laya_extra(guard)
            line = {
                "guard": name,
                "id": row["id"],
                "score": score,
                "flagged_default": verdict.flagged,
                "latency_s": latency,
                **extra,
            }
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
            handle.flush()
            if i % 25 == 0:
                print(f"{name}: {i}/{len(todo)}")
    meta = json.loads(META.read_text()) if META.exists() else {}
    if not (TWINS or SOURCES):
        meta[name] = {"load_and_warmup_s": load, "warnings": notes}
    meta["machine"] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
    }
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


async def main() -> None:
    """Run every requested guard over the data file and write resumable score files."""
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(GUARDS)
    rows = [json.loads(line) for line in DATA.open(encoding="utf-8")]
    if SOURCES:
        rows = [
            {**r, "id": r["id"] + "-source", "text": r["source"]}
            for r in rows
            if not r["leak"]
        ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {
            (s["guard"], s["id"]) for s in map(json.loads, OUT.open(encoding="utf-8"))
        }
    for name in names:
        await run(name, rows, done)


if __name__ == "__main__":
    asyncio.run(main())
