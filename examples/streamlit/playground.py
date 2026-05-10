# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "piighost[gliner2]",
#   "gliner2>=1.2.4",
#   "streamlit>=1.46",
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Streamlit playground for piighost's GLiNER detection.

Tweak the model, labels, threshold, ``flat_ner`` and optional chunking
on the fly, then click **Run detection** to see highlighted spans and
a sortable dataframe.

Detection only: no anonymization, no resolver, no linker. Run via
``uv run streamlit run examples/streamlit/playground.py`` (after
``uv sync --group dev``) or ``uv run --with streamlit streamlit run ...``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from gliner2 import GLiNER2

MODEL_PRESETS: list[str] = [
    "fastino/gliner2-multi-v1",
    "urchade/gliner_multi-v2.1",
    "urchade/gliner_multi_pii-v1",
    "knowledgator/gliner-multitask-v1.0",
]
CUSTOM_MODEL_SENTINEL = "Custom..."

DEFAULT_LABELS: list[str] = [
    "PERSON",
    "ADDRESS",
    "EMAIL",
    "PHONE",
    "ORGANIZATION",
    "DATE",
    "IBAN",
]
LABEL_PRESETS: dict[str, list[str]] = {
    "Standard": DEFAULT_LABELS,
    "FR notarial": ["PERSON", "ADDRESS", "ORGANIZATION", "DATE"],
    "Email/contact": ["PERSON", "EMAIL", "PHONE", "ORGANIZATION"],
}
LABELS_WIDGET_KEY = "playground_labels_multiselect"
PRESET_WIDGET_KEY = "playground_labels_preset"


@st.cache_resource(show_spinner="Loading GLiNER model…")
def load_gliner(model_id: str) -> GLiNER2:
    """Load (and cache) a GLiNER2 model by its HuggingFace id."""
    return GLiNER2.from_pretrained(model_id)


def _model_selector() -> str | None:
    """Render the model selector and return the resolved model id, or None on error."""
    choice = st.selectbox(
        "Model",
        options=[*MODEL_PRESETS, CUSTOM_MODEL_SENTINEL],
        index=0,
        help="GLiNER2 model id on HuggingFace.",
    )
    if choice == CUSTOM_MODEL_SENTINEL:
        custom = st.text_input(
            "Custom model id",
            value="",
            placeholder="e.g. urchade/gliner_small-v2.1",
        ).strip()
        return custom or None
    return choice


def _labels_widget() -> list[str]:
    """Render the preset segmented control + tag-style multiselect.

    Uses ``key=`` on both widgets and writes the multiselect's
    session-state value *before* it is instantiated this run, so that
    a preset click actually resets the multiselect (the ``default=``
    kwarg is only honoured on first render).
    """
    if LABELS_WIDGET_KEY not in st.session_state:
        st.session_state[LABELS_WIDGET_KEY] = list(DEFAULT_LABELS)

    preset = st.segmented_control(
        "Label preset",
        options=list(LABEL_PRESETS.keys()),
        default=None,
        key=PRESET_WIDGET_KEY,
        help="Click a preset to overwrite the selection below.",
    )
    if preset is not None and (
        st.session_state[LABELS_WIDGET_KEY] != LABEL_PRESETS[preset]
    ):
        st.session_state[LABELS_WIDGET_KEY] = list(LABEL_PRESETS[preset])

    return st.multiselect(
        "Labels",
        options=DEFAULT_LABELS,
        accept_new_options=True,
        key=LABELS_WIDGET_KEY,
        help="Type a label and press Enter to add a custom one.",
    )


def _detection_params() -> tuple[float, bool, tuple[int, int] | None]:
    """Render threshold + flat_ner + chunk toggle. Return (threshold, flat_ner, chunk_params).

    ``chunk_params`` is ``None`` when chunking is OFF, otherwise
    ``(chunk_size, overlap)``.
    """
    threshold = st.slider("Threshold", 0.0, 1.0, 0.5, step=0.05)
    flat_ner = st.checkbox("flat_ner (no nested entities)", value=True)

    with st.expander("Chunking", expanded=False):
        chunk_on = st.checkbox("Chunk long inputs", value=False)
        if chunk_on:
            chunk_size = st.slider("chunk_size (chars)", 200, 4000, 1500, step=100)
            overlap = st.slider("overlap (chars)", 0, 500, 100, step=50)
            chunk_params: tuple[int, int] | None = (chunk_size, overlap)
        else:
            chunk_params = None
    return threshold, flat_ner, chunk_params


SAMPLES_DIR = Path(__file__).parent / "samples"


def _list_samples() -> list[Path]:
    return sorted(SAMPLES_DIR.glob("*.txt"))


def _input_widget() -> str:
    """Render the input-mode radio + the matching widget. Return the resolved text."""
    mode = st.radio(
        "Input source",
        options=["Sample", "Paste", "Upload"],
        index=0,
        horizontal=True,
    )
    if mode == "Sample":
        samples = _list_samples()
        if not samples:
            st.warning(f"No samples found in {SAMPLES_DIR}.")
            return ""
        choice = st.selectbox(
            "Sample file",
            options=samples,
            format_func=lambda p: p.name,
        )
        text = choice.read_text(encoding="utf-8")
        st.text_area("Preview", value=text, height=240, disabled=True)
        return text
    if mode == "Paste":
        return st.text_area("Text to scan", value="", height=300)
    upload = st.file_uploader("Upload .txt", type=["txt"])
    if upload is None:
        return ""
    raw = upload.read()
    text = raw.decode("utf-8", errors="replace")
    if "�" in text:
        st.warning("Non-UTF-8 bytes were replaced with U+FFFD.")
    return text


def main() -> None:
    st.set_page_config(
        page_title="piighost — GLiNER playground",
        page_icon="🔎",
        layout="wide",
    )
    st.title("piighost — GLiNER detection playground")
    st.caption("Tune GLiNER on the fly against text or .txt documents.")

    with st.sidebar:
        st.header("Configuration")
        model_id = _model_selector()
        st.divider()
        labels = _labels_widget()
        st.divider()
        threshold, flat_ner, chunk_params = _detection_params()

    if not model_id:
        st.info("Pick a model in the sidebar to get started.")
        return
    if not labels:
        st.info("Add at least one label in the sidebar.")
        return

    st.write(f"**Selected model:** `{model_id}`")
    st.write(f"**Labels ({len(labels)}):** {', '.join(labels)}")
    chunk_label = (
        f"chunked({chunk_params[0]}/{chunk_params[1]})"
        if chunk_params
        else "no chunking"
    )
    st.write(
        f"**Threshold:** {threshold:.2f} — "
        f"**flat_ner:** {flat_ner} — "
        f"**{chunk_label}**"
    )

    st.divider()
    text = _input_widget()
    st.caption(f"Text length: {len(text)} chars")


if __name__ == "__main__":
    main()
