# Streamlit detection playground — design

**Status:** approved
**Date:** 2026-05-10
**Target directory:** `examples/streamlit/`
**Stack:** piighost + GLiNER2 + Streamlit (PEP 723 inline-metadata script)

## Goal

Add a Streamlit-based playground that lets a user iteratively tweak GLiNER
detection settings against arbitrary text or business `.txt` documents,
re-run on demand, and inspect detected spans visually.

Primary use case: experimenting with which GLiNER model / labels /
threshold work best for a given kind of document, without writing code.

## Non-goals

- No anonymization stage. Detection only. The playground does not load
  `Anonymizer`, `LabelCounterPlaceholderFactory`, or any pipeline
  resolver. If a "playground 2" wants to demo the full anonymize/
  deanonymize round-trip later, it gets its own page or its own example.
- No `RegexDetector`, `ExactMatchDetector`, or `CompositeDetector`.
  Out by user request to keep the UI focused on GLiNER tuning.
- No PDF / DOCX / image ingestion. Plain `.txt` only (UTF-8, fallback
  `errors="replace"`).
- No comparison view (configs side-by-side, A/B). Out of scope here,
  could be a future page.
- No tests. Examples are not part of the test suite by convention.
- No persistence of past runs. Each Run click computes fresh; the only
  state is widget state and the model cache.

## Architecture

```
examples/streamlit/
├── playground.py          # PEP 723 self-contained script (UI + logic)
├── samples/
│   ├── email_pro.txt
│   ├── facture.txt
│   ├── contrat_cdi.txt
│   ├── compte_rendu.txt
│   ├── ticket_support.txt
│   └── cv_candidat.txt
└── README.md              # how to run + what the samples cover
```

`playground.py` is a single PEP 723 inline-metadata script depending on
`piighost[gliner2]`, `gliner2>=1.2.4`, and `streamlit>=1.46`
(needed for `st.multiselect(accept_new_options=True)`).

Run options:

```bash
# Self-contained (PEP 723 resolves deps in an ephemeral venv)
uv run --with streamlit streamlit run examples/streamlit/playground.py

# Or via the dev environment, after adding streamlit to [dependency-groups].dev
uv sync --group dev
uv run streamlit run examples/streamlit/playground.py
```

The `streamlit>=1.46` line is also added to the root `pyproject.toml`
under `[dependency-groups].dev` so contributors who already run
`uv sync` don't need the `--with streamlit` flag.

## Components

### Sidebar (configuration)

Top-down order:

1. **Model selection**
   - `st.selectbox` listing presets:
     - `fastino/gliner2-multi-v1` (default)
     - `urchade/gliner_multi-v2.1`
     - `urchade/gliner_multi_pii-v1`
     - `knowledgator/gliner-multitask-v1.0`
     - `Custom...` → reveals an `st.text_input` for any HuggingFace id
   - Loaded via `@st.cache_resource(show_spinner="Loading model…")`
     keyed on the resolved model id, so each model loads once per
     Streamlit process. Cache is never invalidated; RAM grows with the
     number of distinct models tried in a session — acceptable for a
     playground.

2. **Labels**
   - `st.segmented_control` with three preset buttons that overwrite
     the multiselect value via `st.session_state`:
     - `Standard` → `["PERSON", "ADDRESS", "EMAIL", "PHONE", "ORGANIZATION", "DATE", "IBAN"]`
     - `FR notarial` → `["PERSON", "ADDRESS", "ORGANIZATION", "DATE"]`
     - `Email/contact` → `["PERSON", "EMAIL", "PHONE", "ORGANIZATION"]`
   - `st.multiselect(options=DEFAULT_LABELS, default=DEFAULT_LABELS, accept_new_options=True)`
     so users can add labels not in the preset list.

3. **Threshold** — `st.slider("Threshold", 0.0, 1.0, 0.5, step=0.05)`

4. **Flat NER** — `st.checkbox("flat_ner (no nested entities)", value=True)`

5. **Chunking** (off by default)
   - `st.checkbox("Chunk long inputs")`
   - When ON, two sliders appear:
     - `chunk_size` (chars): 200..4000, default 1500, step 100
     - `overlap` (chars): 0..500, default 100, step 50
   - When ON, the `Gliner2Detector` is wrapped in `ChunkedDetector(detector, chunk_size, overlap)`.

### Main area (input + run + results)

- **Input mode** (`st.radio` horizontal at the top):
  - `Sample` → `st.selectbox` listing files in `samples/`. Content
    rendered read-only in `st.text_area(disabled=True, height=200)`.
  - `Paste` → empty `st.text_area(height=300)`.
  - `Upload` → `st.file_uploader(type=["txt"])`, decoded UTF-8 with
    `errors="replace"` and a warning if any byte was replaced.
- **Run button** — `st.button("Run detection", type="primary")`. No
  detection runs until the button is clicked, even if the user changes
  widgets in between (Streamlit reruns the script silently but the
  detection block is gated on the button).
- **Results area** (rendered only after a successful run):
  - Two `st.metric` columns: `Detections: {n}` and `Latency: {ms} ms`.
  - Highlighted text in an `st.container(border=True)`: the original
    text with each span wrapped in
    `<mark style="background:{color};padding:0.1em 0.2em;border-radius:0.2em">{text}<sub style="font-size:0.6em;color:#555;margin-left:0.2em">{label}</sub></mark>`.
    Color is stable per label via `f"hsl({hash(label) % 360}, 60%, 80%)"`.
  - `st.dataframe` (sortable) of detections: `text`, `label`, `start`,
    `end`, `score`.

## Data flow

User clicks **Run detection** →

1. Resolve the input text from the active input mode.
2. Read the resolved model id, labels, threshold, flat_ner, chunk
   toggle and chunk params from widget state.
3. Early returns:
   - empty text → `st.warning("Provide some text first")`, abort.
   - empty labels → `st.warning("Add at least one label")`, abort.
4. `model = load_gliner(model_id)` (cached).
5. `detector = Gliner2Detector(model, labels, threshold, flat_ner)`.
6. If chunk toggle ON: `detector = ChunkedDetector(detector, chunk_size, overlap)`.
7. `t0 = perf_counter()`; `detections = asyncio.run(detector.detect(text))`;
   `elapsed_ms = (perf_counter() - t0) * 1000`.
8. Render the highlighted text and the dataframe.

`asyncio.run` is invoked once per click, no persistent loop, no
event-loop conflict with Streamlit.

## Error handling

- `GLiNER2.from_pretrained(model_id)` raises (invalid id, offline,
  permission) → caught at the top of `load_gliner`, surfaced as
  `st.error(f"Failed to load model: {exc}")`. The user can correct
  the input and click Run again.
- File upload non-UTF-8 → forced decode `errors="replace"` plus
  `st.warning("Non-UTF-8 bytes were replaced.")`.
- Empty text or empty labels → handled in early returns above.
- `chunk_size <= overlap` is impossible given slider bounds, but a
  defensive `st.warning("chunk_size must exceed overlap")` is kept.

## Sample contents

Each `samples/*.txt` is 10–25 lines, in French, written to expose at
least four PII types so the playground always has something to show
on default settings. No real personal names.

| file | PII coverage |
|---|---|
| `email_pro.txt` | PERSON×2, EMAIL×2, PHONE, ORGANIZATION, DATE |
| `facture.txt` | ORGANIZATION×2, ADDRESS×2, IBAN, SIREN/TVA, DATE×2, amounts |
| `contrat_cdi.txt` | PERSON, ADDRESS, ORGANIZATION, SIRET, DATE×2, social-security number |
| `compte_rendu.txt` | PERSON×4, ORGANIZATION, DATE, room/location |
| `ticket_support.txt` | PERSON, EMAIL, PHONE, order number, ADDRESS |
| `cv_candidat.txt` | PERSON, EMAIL, PHONE, ADDRESS, ORGANIZATION×3, DATE×3 |

## Validation

Manual only. The acceptance pass before merge:

- Each of the six samples loaded under the default config (model
  `fastino/gliner2-multi-v1`, `Standard` labels, threshold 0.5,
  `flat_ner=True`, chunking OFF) produces a non-empty detection list
  and the highlighted rendering matches the dataframe.
- Switching the model to one of the other presets does not crash and
  reuses the cached model on the second run.
- Toggling chunking ON with default chunk params on `cv_candidat.txt`
  returns a result without errors.
- Pasting empty text and clicking Run produces the early-return
  warning, not an exception.
