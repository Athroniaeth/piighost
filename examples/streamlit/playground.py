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


def main() -> None:
    st.set_page_config(
        page_title="piighost — GLiNER playground",
        page_icon="🔎",
        layout="wide",
    )
    st.title("piighost — GLiNER detection playground")
    st.caption("Tune GLiNER on the fly against text or .txt documents.")


if __name__ == "__main__":
    main()
