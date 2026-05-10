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

import streamlit as st
from gliner2 import GLiNER2

MODEL_PRESETS: list[str] = [
    "fastino/gliner2-multi-v1",
    "urchade/gliner_multi-v2.1",
    "urchade/gliner_multi_pii-v1",
    "knowledgator/gliner-multitask-v1.0",
]
CUSTOM_MODEL_SENTINEL = "Custom..."


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

    if not model_id:
        st.info("Pick a model in the sidebar to get started.")
        return

    st.write(f"**Selected model:** `{model_id}`")


if __name__ == "__main__":
    main()
