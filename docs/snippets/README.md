# Code examples of the documentation

Every Python example a page shows lives here, one file per example, shared by
the French and English pages. A page includes a file, or one section of it:

````markdown
```python
--8<-- "snippets/first_pipeline.py:run"
```
````

A section is delimited in the file by `# --8<-- [start:run]` and
`# --8<-- [end:run]`; the marker lines never reach the page. A file that prints
has a sibling `.out` with its expected output, which the page includes too, so
the output a reader sees is the one the code gives.

`tests/docs/test_snippets.py` runs every file and compares its output:

```bash
uv run pytest tests/docs                  # the examples that need nothing
uv run pytest tests/docs -m integration   # the ones that reach the hub or load a model
```

The configuration tutorial keeps its files in `configuration/`, which
`tests/docs/test_configuration_tutorial.py` replays step by step, the CLI
commands included.

A new file goes in the `SNIPPETS` list of that test, and a page whose examples
all come from here goes in `MIGRATED`, after which a Python block written by
hand in it fails the test. An example only differs between languages when its
data does (`quickstart.fr.py`, `quickstart.en.py`).

An example that calls a model provider (LangChain, Pydantic AI, LlamaIndex)
keeps the provider's name on the page. Lines above its first section, which
the page does not include, replace the provider with a scripted model of
`_offline.py`. That model answers from the tokens it receives and fails if a
clear value reaches it, so the example checks the de-identification without a
network or an API key. A file named `_*.py` is such a helper and is never
shown.
