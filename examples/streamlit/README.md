# Streamlit detection playground

Interactive playground for testing piighost's GLiNER detection on text or
`.txt` documents. Tweak the model, labels, threshold, `flat_ner`, and
chunking on the fly, then click **Run detection** to see highlighted
spans and a sortable dataframe.

## Run it

`streamlit run` imports the script from the active environment (PEP 723
metadata is only honoured when `uv run` executes the script directly,
which `streamlit run` does not). So both `streamlit` and `gliner2` need
to be importable.

```bash
uv sync --group dev --group gliner2
uv run streamlit run examples/streamlit/playground.py
```

Or, in a fresh checkout without syncing:

```bash
uv run --with gliner2 --with streamlit streamlit run examples/streamlit/playground.py
```

The first run downloads the default model
(`fastino/gliner2-multi-v1`, ~500 MB) from HuggingFace.

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
