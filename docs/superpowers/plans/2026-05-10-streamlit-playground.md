# Streamlit detection playground — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Streamlit playground at `examples/streamlit/playground.py` that lets a user iteratively tweak GLiNER detection settings against text or business `.txt` documents and inspect detected spans.

**Architecture:** Single PEP 723 inline-metadata script + a `samples/` folder with six French business sample texts + a README. The script keeps GLiNER instances in `@st.cache_resource`, gates detection behind an explicit Run button, and renders highlighted HTML spans plus a sortable dataframe. No anonymization, no Composite, no chunking unless the user toggles it.

**Tech Stack:** Python 3.12+, Streamlit ≥1.46 (for `multiselect(accept_new_options=True)`), piighost (editable via `[tool.uv.sources]`), GLiNER2.

**Spec:** `docs/superpowers/specs/2026-05-10-streamlit-playground-design.md`

**No automated tests:** Examples in this repo are not under pytest. Each task ends with a syntax-parse check and a manual smoke screen. Validation pass at the very end (Task 10) covers the cases listed in the spec.

---

## File map

- Create `examples/streamlit/playground.py` — full app
- Create `examples/streamlit/README.md` — how to run + what each sample contains
- Create `examples/streamlit/samples/email_pro.txt`
- Create `examples/streamlit/samples/facture.txt`
- Create `examples/streamlit/samples/contrat_cdi.txt`
- Create `examples/streamlit/samples/compte_rendu.txt`
- Create `examples/streamlit/samples/ticket_support.txt`
- Create `examples/streamlit/samples/cv_candidat.txt`
- Modify `pyproject.toml` — add `streamlit>=1.46` to `[dependency-groups].dev`

All paths are absolute from the repo root `/home/secondary/PycharmProjects/piighost/`.

---

## Task 1: Add streamlit to dev deps and scaffold the directory

**Files:**
- Modify: `pyproject.toml` (the `dev` list inside `[dependency-groups]`)
- Create: `examples/streamlit/README.md`

- [ ] **Step 1: Add streamlit to the dev dependency group**

Open `pyproject.toml`, find the `[dependency-groups]` section and the `dev = [ ... ]` list. Append a new entry. The list currently ends with `"bandit>=1.9.4",`. The result must look like:

```toml
[dependency-groups]
dev = [
    "ruff>=0.15.5",
    "pytest>=9.0.2",
    "pytest-cov>=6.0",
    "pyrefly>=0.55.0",
    "zensical>=0.0.27",
    "commitizen>=4.13.9",
    "pytest-asyncio>=0.25",
    "bandit>=1.9.4",
    "streamlit>=1.46",
]
```

- [ ] **Step 2: Sync the dev environment**

Run: `uv sync --group dev`
Expected: streamlit and its transitive deps install without errors. `uv pip show streamlit` should report `Version: 1.46.x` or higher.

- [ ] **Step 3: Create the README**

Create `examples/streamlit/README.md` with this exact content:

````markdown
# Streamlit detection playground

Interactive playground for testing piighost's GLiNER detection on text or
`.txt` documents. Tweak the model, labels, threshold, `flat_ner`, and
chunking on the fly, then click **Run detection** to see highlighted
spans and a sortable dataframe.

## Run it

After `uv sync --group dev` at the repo root:

```bash
uv run streamlit run examples/streamlit/playground.py
```

Or, in a fresh checkout without dev deps installed:

```bash
uv run --with streamlit streamlit run examples/streamlit/playground.py
```

The PEP 723 header in `playground.py` resolves piighost in editable mode
plus `gliner2` in an ephemeral venv. The first run downloads the default
model (`fastino/gliner2-multi-v1`, ~500 MB) from HuggingFace.

## Samples

`samples/` ships six short French business documents covering the most
common PII shapes you'll meet in entreprise data:

| file | typical PII |
| --- | --- |
| `email_pro.txt` | PERSON, EMAIL, PHONE, ORGANIZATION, DATE |
| `facture.txt` | ORGANIZATION, ADDRESS, IBAN, SIREN/TVA, DATE |
| `contrat_cdi.txt` | PERSON, ADDRESS, ORGANIZATION, SIRET, DATE, social security number |
| `compte_rendu.txt` | PERSON, ORGANIZATION, DATE, room/location |
| `ticket_support.txt` | PERSON, EMAIL, PHONE, order number, ADDRESS |
| `cv_candidat.txt` | PERSON, EMAIL, PHONE, ADDRESS, ORGANIZATION, DATE |

All names and identifiers are fictitious.
````

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock examples/streamlit/README.md
git commit -m "chore(examples): scaffold streamlit playground directory

Add streamlit>=1.46 to [dependency-groups].dev for the upcoming
detection playground under examples/streamlit/. Drops the README in
place; the script and samples land in subsequent commits."
```

---

## Task 2: Author the six sample documents

**Files:**
- Create: `examples/streamlit/samples/email_pro.txt`
- Create: `examples/streamlit/samples/facture.txt`
- Create: `examples/streamlit/samples/contrat_cdi.txt`
- Create: `examples/streamlit/samples/compte_rendu.txt`
- Create: `examples/streamlit/samples/ticket_support.txt`
- Create: `examples/streamlit/samples/cv_candidat.txt`

Each file: 10–25 lines, French, fictitious names, expose ≥4 PII types so the playground always has something to show on default settings.

- [ ] **Step 1: Write `email_pro.txt`**

```
De : Camille Lefèvre <camille.lefevre@atlantis-conseil.fr>
À : Pôle Support Client <support@atlantis-conseil.fr>
Date : mardi 14 avril 2026, 09:42
Objet : Suivi du dossier 2026-AT-0421

Bonjour,

Je transmets en copie Julien Marchand qui prendra le relais sur le
dossier de Madame Camille Bernard à compter de la semaine prochaine.

Pouvez-vous lui faire parvenir l'ensemble des échanges déjà archivés ?
Pour rappel, son numéro de téléphone direct est le 06 18 42 91 03.

Bien cordialement,

Camille Lefèvre
Responsable comptes clés
Atlantis Conseil — 12 quai de la Râpée, 75012 Paris
camille.lefevre@atlantis-conseil.fr · +33 1 44 87 22 10
```

- [ ] **Step 2: Write `facture.txt`**

```
FACTURE n° FA-2026-00482
Émise le 03 mars 2026 — Échéance : 02 avril 2026

Émetteur :
  Borealis Logistique SAS
  17 rue des Pinsons, 33000 Bordeaux
  SIREN 812 345 678 — TVA FR12 812345678

Destinataire :
  Société Atlantis Conseil
  12 quai de la Râpée, 75012 Paris
  SIREN 521 998 110

Détail :
  Prestation de transport — Lyon → Paris        1 250,00 €
  Frais de manutention                            180,00 €

Total HT                                       1 430,00 €
TVA 20 %                                         286,00 €
Total TTC                                      1 716,00 €

Règlement par virement :
  IBAN : FR76 3000 4000 0312 3456 7890 143
  BIC  : BNPAFRPPXXX
```

- [ ] **Step 3: Write `contrat_cdi.txt`**

```
CONTRAT DE TRAVAIL À DURÉE INDÉTERMINÉE

Entre les soussignés :

L'employeur :
  Borealis Logistique SAS, SIRET 812 345 678 00021,
  dont le siège est 17 rue des Pinsons, 33000 Bordeaux,
  représenté par Monsieur Olivier Dubreuil en qualité de Directeur
  des ressources humaines,

Et le salarié :
  Madame Léa Mercier, née le 04 février 1994,
  demeurant 8 allée des Magnolias, 33700 Mérignac,
  numéro de sécurité sociale 2 94 02 33 281 042 18,

Il a été convenu ce qui suit :

Article 1 — Engagement
  Madame Léa Mercier est engagée à compter du 1er juin 2026 en qualité
  de Chargée de planification, statut Agent de maîtrise.

Article 2 — Rémunération
  La rémunération brute mensuelle est fixée à 2 850 € pour 35 heures
  hebdomadaires, payable le dernier jour ouvré de chaque mois.
```

- [ ] **Step 4: Write `compte_rendu.txt`**

```
Compte-rendu — Comité projet "Phoenix"
Date : jeudi 7 mai 2026, 14h00 — Salle Albatros, Bordeaux

Présents :
  - Olivier Dubreuil (DRH, Borealis Logistique)
  - Léa Mercier (Chargée de planification)
  - Camille Lefèvre (Atlantis Conseil, prestataire externe)
  - Hugo Tanaka (DSI)

Décisions :
  1. Le pilote est lancé le 1er juin 2026 sur le périmètre Aquitaine.
  2. Atlantis Conseil cadre les ateliers utilisateurs avant le 22 mai.
  3. Hugo Tanaka livre la maquette technique avant le prochain comité.

Actions :
  - Léa Mercier : préparer la liste des sites pilotes (échéance 14 mai)
  - Camille Lefèvre : envoyer la grille d'entretien aux managers
  - Olivier Dubreuil : valider la communication interne RH

Prochain comité : jeudi 28 mai 2026, 14h00.
```

- [ ] **Step 5: Write `ticket_support.txt`**

```
Ticket #INC-2026-00917
Statut : ouvert — Priorité : normale
Ouvert le : 22 avril 2026, 11:18

Client :
  Nom        : Jean-Marc Rousseau
  Email      : jm.rousseau@example.fr
  Téléphone  : 07 62 19 84 53
  Commande   : CMD-208374
  Livraison  : 4 rue de la Bergerie, 14000 Caen

Message du client :
  Bonjour, je n'ai toujours pas reçu ma commande passée le 9 avril.
  Le suivi du transporteur indique qu'elle est en attente depuis
  une semaine au centre de tri de Rouen. Pouvez-vous me dire ce qu'il
  en est et me proposer un nouveau créneau de livraison ?

Réponse interne (brouillon) :
  Vérifier auprès de Borealis Logistique l'état du colis et confirmer
  la nouvelle date avec Monsieur Rousseau avant 17h.
```

- [ ] **Step 6: Write `cv_candidat.txt`**

```
LÉA MERCIER
Chargée de planification logistique
8 allée des Magnolias, 33700 Mérignac
lea.mercier@email-fictif.fr — 06 73 22 18 47

EXPÉRIENCE PROFESSIONNELLE

Borealis Logistique SAS — Bordeaux                  juin 2022 – aujourd'hui
  Chargée de planification
  - Pilotage du planning de tournées sur la région Aquitaine
  - Suivi des indicateurs OTIF avec un gain de 6 points en 18 mois

Cargo Express SARL — Toulouse                       sept. 2018 – mai 2022
  Coordinatrice transport
  - Gestion d'une flotte de 14 véhicules et 22 chauffeurs

FORMATION

Master Supply Chain — IAE Bordeaux                  2016 – 2018
Licence Économie-Gestion — Université de Pau         2013 – 2016

LANGUES
  Français (natif) — Anglais (C1) — Espagnol (B2)
```

- [ ] **Step 7: Commit**

```bash
git add examples/streamlit/samples/
git commit -m "examples(streamlit): add six French business .txt samples

Cover the common PII shapes met in entreprise data: email pro, B2B
invoice, CDI contract, meeting minutes, support ticket, CV. All names
and identifiers are fictitious; each file exposes at least four PII
types so the upcoming playground always has something to highlight."
```

---

## Task 3: Skeleton playground.py with PEP 723 header and a runnable empty page

**Files:**
- Create: `examples/streamlit/playground.py`

- [ ] **Step 1: Write the script skeleton**

Create `examples/streamlit/playground.py` with this exact content:

```python
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
```

- [ ] **Step 2: Syntax-parse the file**

Run: `uv run python -c "import ast, pathlib; ast.parse(pathlib.Path('examples/streamlit/playground.py').read_text())"`
Expected: no output, exit code 0.

- [ ] **Step 3: Smoke-launch Streamlit**

Run (in a separate terminal, kill it after a few seconds):

```bash
uv run streamlit run examples/streamlit/playground.py --server.headless true --server.port 8702
```

Expected: terminal prints `You can now view your Streamlit app in your browser.` followed by `http://localhost:8702`. No traceback. Curl-check:

```bash
curl -sf http://localhost:8702/ -o /dev/null && echo OK
```

Expected output: `OK`. Then stop the server.

- [ ] **Step 4: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): scaffold streamlit playground entrypoint

PEP 723 single-file script wiring an empty page with the project title
and caption. Subsequent commits add the sidebar config, input area,
detection runner, and result rendering."
```

---

## Task 4: Sidebar — model selection with cached loader

**Files:**
- Modify: `examples/streamlit/playground.py`

- [ ] **Step 1: Add imports and the cached loader**

Add the imports and a cache-decorated loader near the top of `playground.py`. Replace the `from __future__ import annotations` block plus the `import streamlit as st` line with the following block (everything below the docstring):

```python
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
```

- [ ] **Step 2: Wire the selector inside `main()`**

Replace the `main()` body (the `set_page_config`/`title`/`caption` block stays at the top) with:

```python
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
```

- [ ] **Step 3: Smoke-launch and verify**

```bash
uv run streamlit run examples/streamlit/playground.py --server.headless true --server.port 8702
curl -sf http://localhost:8702/ -o /dev/null && echo OK
```

Expected: `OK`. Stop the server. (The model is not loaded yet — only the selector is rendered. Loading happens in Task 8.)

- [ ] **Step 4: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): add streamlit model selector with cached loader

Sidebar selectbox lists four GLiNER2 presets plus a 'Custom...' entry
that reveals a free-form text input. load_gliner is wrapped in
@st.cache_resource keyed on the resolved id so each model loads once
per Streamlit process."
```

---

## Task 5: Sidebar — labels widget with preset buttons

**Files:**
- Modify: `examples/streamlit/playground.py`

- [ ] **Step 1: Add label preset constants**

Below `CUSTOM_MODEL_SENTINEL` and above `load_gliner`, insert:

```python
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
```

- [ ] **Step 2: Add the labels widget helper**

Below `_model_selector`, insert:

```python
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
```

- [ ] **Step 3: Wire it into `main()`**

In `main()`, inside the `with st.sidebar:` block, after `model_id = _model_selector()`, add:

```python
        st.divider()
        labels = _labels_widget()
```

Then below the existing `if not model_id: ...` early return, add:

```python
    if not labels:
        st.info("Add at least one label in the sidebar.")
        return

    st.write(f"**Selected model:** `{model_id}`")
    st.write(f"**Labels ({len(labels)}):** {', '.join(labels)}")
```

(Replace the previous `st.write(f"**Selected model:** ...")` line, since we now want both lines together.)

- [ ] **Step 4: Smoke-launch and verify**

Same launch + curl command as Task 4 step 3. Expected: `OK`, no traceback.

- [ ] **Step 5: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): add streamlit labels widget with presets

Three preset buttons (Standard / FR notarial / Email/contact) overwrite
a multiselect that accepts new options. Selection is mirrored into
st.session_state so preset clicks reseed it across reruns."
```

---

## Task 6: Sidebar — threshold, flat_ner, and chunking toggle

**Files:**
- Modify: `examples/streamlit/playground.py`

- [ ] **Step 1: Add the chunking helper**

Below `_labels_widget`, insert:

```python
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
```

- [ ] **Step 2: Wire it into `main()`**

In `main()`'s sidebar block, after `labels = _labels_widget()`, add:

```python
        st.divider()
        threshold, flat_ner, chunk_params = _detection_params()
```

Then in the body (after the `st.write(f"**Labels ...")` line), append:

```python
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
```

- [ ] **Step 3: Smoke-launch and verify**

Same launch + curl as before. Expected: `OK`, no traceback. The body should now show four lines: model, labels count + list, params summary.

- [ ] **Step 4: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): add streamlit threshold, flat_ner, chunking sidebar

Threshold slider (0..1), flat_ner checkbox, plus a collapsible chunking
expander with chunk_size / overlap sliders gated by a toggle. Chunking
defaults OFF; when ON the helper returns (chunk_size, overlap)."
```

---

## Task 7: Main area — input mode (Sample / Paste / Upload)

**Files:**
- Modify: `examples/streamlit/playground.py`

- [ ] **Step 1: Add `pathlib` import**

In the import block at the top, after `from __future__ import annotations`, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Add the input helper**

Below `_detection_params`, insert:

```python
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
```

- [ ] **Step 3: Wire it into `main()`**

After the existing body lines that print model / labels / params, append:

```python
    st.divider()
    text = _input_widget()
    st.caption(f"Text length: {len(text)} chars")
```

- [ ] **Step 4: Smoke-launch and verify**

Same launch + curl. Switch between Sample / Paste / Upload mentally (we can't drive the UI from CLI, but the page must not error on initial render). Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): add streamlit input source switcher

Horizontal radio choosing between bundled samples (selectbox + readonly
preview), free paste textarea, or .txt upload. Uploads decode UTF-8
with errors='replace' and surface a warning if any byte was lossy."
```

---

## Task 8: Run button + detection orchestration

**Files:**
- Modify: `examples/streamlit/playground.py`

- [ ] **Step 1: Extend imports**

In the import block, add:

```python
import asyncio
from time import perf_counter

from piighost.detector import ChunkedDetector
from piighost.detector.gliner2 import Gliner2Detector
from piighost.models import Detection
```

- [ ] **Step 2: Add the run helper**

Below `_input_widget`, insert:

```python
def _run_detection(
    *,
    model_id: str,
    text: str,
    labels: list[str],
    threshold: float,
    flat_ner: bool,
    chunk_params: tuple[int, int] | None,
) -> tuple[list[Detection], float]:
    """Build the detector, run it, return (detections, latency_ms).

    Raises whatever ``GLiNER2.from_pretrained`` or ``detector.detect``
    raise; the caller surfaces the error via ``st.error``.
    """
    model = load_gliner(model_id)
    detector = Gliner2Detector(
        model=model,
        labels=labels,
        threshold=threshold,
        flat_ner=flat_ner,
    )
    if chunk_params is not None:
        chunk_size, overlap = chunk_params
        detector = ChunkedDetector(
            detector=detector,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    t0 = perf_counter()
    detections = asyncio.run(detector.detect(text))
    return detections, (perf_counter() - t0) * 1000.0
```

> **Note on `ChunkedDetector` constructor:** verify the keyword names against `src/piighost/detector/chunked.py` before running. If the actual signature uses positional args or different names (`max_chunk_size`, `chunk_overlap`, etc.), adjust the call. This task assumes `ChunkedDetector(detector=..., chunk_size=..., overlap=...)`.

- [ ] **Step 3: Wire the Run button**

Replace the `st.caption(f"Text length: {len(text)} chars")` line at the end of `main()` with:

```python
    st.caption(f"Text length: {len(text)} chars")

    if not st.button("Run detection", type="primary"):
        return

    if not text.strip():
        st.warning("Provide some text first.")
        return

    try:
        detections, elapsed_ms = _run_detection(
            model_id=model_id,
            text=text,
            labels=labels,
            threshold=threshold,
            flat_ner=flat_ner,
            chunk_params=chunk_params,
        )
    except Exception as exc:  # noqa: BLE001 — surface any model/detector error
        st.error(f"Detection failed: {exc}")
        return

    st.session_state["last_run"] = {
        "text": text,
        "detections": detections,
        "elapsed_ms": elapsed_ms,
    }
```

- [ ] **Step 4: Verify `ChunkedDetector` signature**

Run: `uv run python -c "import inspect; from piighost.detector import ChunkedDetector; print(inspect.signature(ChunkedDetector.__init__))"`

If the printed signature does not match `(self, detector, chunk_size, overlap)` (or accept those as keyword args), update the call inside `_run_detection` accordingly and rerun this command until it matches.

- [ ] **Step 5: Smoke-launch and click Run via the page**

Smoke-launch as before. The page should render without traceback. Manual: open `http://localhost:8702`, pick the default sample, click **Run detection**, confirm no error banner. Stop the server.

- [ ] **Step 6: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): wire streamlit run button to gliner detection

A primary 'Run detection' button gates the GLiNER call. Builds a
Gliner2Detector (optionally wrapped in ChunkedDetector), runs detect()
via asyncio.run, captures latency in ms, and stashes the result under
st.session_state['last_run'] for the renderer added next."
```

---

## Task 9: Render results — metrics, highlighted spans, dataframe

**Files:**
- Modify: `examples/streamlit/playground.py`

- [ ] **Step 1: Add the renderer helpers**

Below `_run_detection`, insert:

```python
def _label_color(label: str) -> str:
    """Stable pastel color per label for the current Streamlit process."""
    hue = abs(hash(label)) % 360
    return f"hsl({hue}, 60%, 80%)"


def _render_highlighted(text: str, detections: list[Detection]) -> str:
    """Return an HTML string of ``text`` with each detection wrapped in <mark>.

    Detections are sorted by start position; overlapping spans are
    skipped (the ConfidenceSpanConflictResolver normally runs before
    this, but we keep a guard for raw GLiNER output).
    """
    sorted_dets = sorted(detections, key=lambda d: d.position.start_pos)
    out: list[str] = []
    cursor = 0
    for det in sorted_dets:
        start, end = det.position.start_pos, det.position.end_pos
        if start < cursor:
            continue  # overlap, drop
        out.append(_html_escape(text[cursor:start]))
        color = _label_color(det.label)
        out.append(
            f'<mark style="background:{color};padding:0.1em 0.2em;'
            f'border-radius:0.2em">'
            f"{_html_escape(text[start:end])}"
            f'<sub style="font-size:0.6em;color:#555;margin-left:0.2em">'
            f"{_html_escape(det.label)}</sub>"
            f"</mark>"
        )
        cursor = end
    out.append(_html_escape(text[cursor:]))
    return "<div style='white-space:pre-wrap;font-family:monospace'>" + "".join(out) + "</div>"


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_results() -> None:
    last = st.session_state.get("last_run")
    if not last:
        return
    text: str = last["text"]
    detections: list[Detection] = last["detections"]
    elapsed_ms: float = last["elapsed_ms"]

    col_n, col_t = st.columns(2)
    col_n.metric("Detections", len(detections))
    col_t.metric("Latency", f"{elapsed_ms:.0f} ms")

    st.subheader("Highlighted text")
    with st.container(border=True):
        st.markdown(_render_highlighted(text, detections), unsafe_allow_html=True)

    st.subheader("Detections")
    if detections:
        st.dataframe(
            [
                {
                    "text": d.text,
                    "label": d.label,
                    "start": d.position.start_pos,
                    "end": d.position.end_pos,
                    "score": round(d.confidence, 3),
                }
                for d in detections
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No detection at the current settings.")
```

- [ ] **Step 2: Call the renderer at the end of `main()`**

At the very end of `main()`, after the `st.session_state["last_run"] = {...}` assignment, append:

```python
    _render_results()
```

- [ ] **Step 3: Smoke-launch and run the default sample**

```bash
uv run streamlit run examples/streamlit/playground.py --server.headless true --server.port 8702
```

Open `http://localhost:8702`, click **Run detection** with default settings on `email_pro.txt`. Expected behavior:
- Top of results: `Detections: ≥4`, `Latency: <several_thousand_ms>` (first run downloads the model).
- Highlighted text shows the original email with `<mark>`-wrapped spans for at least the email addresses, the phone number, and the names.
- Dataframe lists the same spans with text/label/start/end/score columns.

Stop the server.

- [ ] **Step 4: Commit**

```bash
git add examples/streamlit/playground.py
git commit -m "feat(examples): render highlighted spans and detection table

Two-column metric strip (count + latency), an HTML-escaped span
renderer with a stable pastel color per label, and a sortable
dataframe of (text, label, start, end, score). Falls back to an info
message when no detection matches the current settings."
```

---

## Task 10: Validation pass and final commit

**Files:** none modified — this is a manual acceptance pass against the spec's validation list.

- [ ] **Step 1: Default config on every sample**

Launch the app: `uv run streamlit run examples/streamlit/playground.py`.

For each of the six samples, with default settings (model `fastino/gliner2-multi-v1`, `Standard` labels, threshold 0.5, `flat_ner=True`, chunking OFF), click **Run detection** and verify:

- The detection list is non-empty.
- The number of `<mark>` spans in the highlighted text equals the dataframe row count.
- No traceback in the terminal.

- [ ] **Step 2: Model swap reuses cache**

Switch to `urchade/gliner_multi-v2.1`, run, then switch back to `fastino/gliner2-multi-v1`. Second time on `fastino` should not show the loading spinner — the `@st.cache_resource` keeps it warm.

- [ ] **Step 3: Chunking toggle**

On `cv_candidat.txt`, enable **Chunk long inputs** with default `chunk_size=1500`, `overlap=100`. Click **Run detection**. The app must not crash; the dataframe should remain populated.

- [ ] **Step 4: Empty-text guard**

Switch to **Paste**, leave the textarea empty, click **Run detection**. Expected: `Provide some text first.` warning, no traceback.

- [ ] **Step 5: Empty-labels guard**

In the sidebar multiselect, remove every label. Expected: the body shows `Add at least one label in the sidebar.` and the Run button area is not reached.

- [ ] **Step 6: Lint and type-check**

Run: `make lint`
Expected: ruff format / lint / pyrefly all clean. Note: the example script is included in the repo, so it must pass the project's lint config.

- [ ] **Step 7: Final commit if any cleanup was needed**

If steps 1–6 surfaced lint hits or small fixes:

```bash
git add examples/streamlit/playground.py
git commit -m "chore(examples): cleanup after streamlit playground validation"
```

If no cleanup was needed, skip this step. Either way, the playground is now ready to ship.
