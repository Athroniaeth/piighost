"""Every code example the documentation shows runs, and prints what the page shows.

The examples live in docs/snippets/, one file per example, shared by the French
and English pages, which include them with `--8<-- "snippets/<file>:<section>"`.
A file that prints has a sibling .out holding its expected output, which the
page includes too: the output a reader sees is the output the code gives. A
file named test_*.py is a test file the page shows, and runs under pytest.

An example that calls a model provider swaps it, in lines the page does not
include, for a scripted model of `_offline.py`, which fails if a clear value
reaches it. A file named _*.py is such a helper, never shown.
"""

import importlib
import inspect
import re
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from piighost.config import load_config

SNIPPETS_DIR = Path(__file__).resolve().parents[2] / "docs" / "snippets"
"""Where the documentation's examples live."""

SNIPPETS: list[Any] = [
    "quickstart.en.py",
    "quickstart.fr.py",
    "first_pipeline.py",
    "conversation.py",
    "basic_exact.py",
    "basic_factories.py",
    "testing.py",
    "test_testing.py",
    "overrides_blacklist.py",
    "overrides_blacklist_strategies.py",
    "overrides_whitelist_exact.py",
    "overrides_whitelist_provenance.py",
    "overrides_conflict.py",
    "extending.py",
    "extending_models.py",
    "ports.py",
    "architecture_port.py",
    "architecture_template.fr.py",
    "architecture_template.en.py",
    "architecture_pipeline.py",
    "architecture_signature.fr.py",
    "architecture_signature.en.py",
    "architecture_thread.py",
    "loaders.py",
    "observation_tracer.py",
    "observation_redactor.py",
    "observation_clear_text.py",
    "observation_langfuse.py",
    "tool_call_middleware.fr.py",
    "tool_call_middleware.en.py",
    "placeholder_builtins.py",
    "placeholder_uuid.py",
    "placeholder_bracket.py",
    "placeholder_hashed_email.py",
    "langchain_start.py",
    "langchain_agent.py",
    "pydantic_ai_agent.py",
    "llama_index_rag.py",
    "reference_anonymizer.py",
    "reference_detectors.py",
    "reference_text.en.py",
    "reference_text.fr.py",
    "reference_llm_detector.py",
    "reference_langchain.py",
    "reference_models.py",
    "reference_span.en.py",
    "reference_span.fr.py",
    "reference_pipeline.py",
    "reference_thread_pipeline.py",
    "security_redactor.py",
    "upgrading.py",
    # These reach the hub or download a model.
    pytest.param("basic.py", marks=pytest.mark.integration),
    pytest.param("detector_hub.py", marks=pytest.mark.integration),
    pytest.param("detector_gliner2.py", marks=pytest.mark.integration),
    pytest.param("overrides_whitelist_hub.py", marks=pytest.mark.integration),
    pytest.param("overrides_config.py", marks=pytest.mark.integration),
    pytest.param("detectors_hub.py", marks=pytest.mark.integration),
    pytest.param("detectors_merge.py", marks=pytest.mark.integration),
    pytest.param("detectors_pick.py", marks=pytest.mark.integration),
    pytest.param("detectors_composite.py", marks=pytest.mark.integration),
    pytest.param("detectors_chunked.py", marks=pytest.mark.integration),
    pytest.param("extending_gliner2.py", marks=pytest.mark.integration),
    pytest.param("langchain_pipeline.py", marks=pytest.mark.integration),
    pytest.param("pydantic_ai_pipeline.py", marks=pytest.mark.integration),
    pytest.param("reference_regex_hub.py", marks=pytest.mark.integration),
    pytest.param("reference_guard.py", marks=pytest.mark.integration),
    pytest.param("reference_hub_pipeline.py", marks=pytest.mark.integration),
    pytest.param("reference_composite.py", marks=pytest.mark.integration),
    pytest.param("reference_chunked.py", marks=pytest.mark.integration),
    pytest.param("reference_transformers.py", marks=pytest.mark.integration),
    pytest.param("reference_guard_gliner2.py", marks=pytest.mark.integration),
    pytest.param("reference_gliner2_guard.py", marks=pytest.mark.integration),
    pytest.param("reference_gliner2_pipeline.py", marks=pytest.mark.integration),
    pytest.param("upgrading_catalogs.py", marks=pytest.mark.integration),
]
"""Every example, the ones that need the network or a model marked integration."""

MIGRATED = [
    "getting-started/quickstart.md",
    "getting-started/first-pipeline.md",
    "getting-started/conversation.md",
    "examples/basic.md",
    "examples/testing.md",
    "examples/overrides.md",
    "examples/detectors.md",
    "extending.md",
    "architecture.md",
    "observation.md",
    "tool-call-strategies.md",
    "placeholder-factories.md",
    "getting-started/langchain.md",
    "examples/langchain.md",
    "examples/pydantic-ai.md",
    "examples/llama-index.md",
    "getting-started/configuration.md",
]
"""The pages whose Python examples all come from docs/snippets/, in both languages."""

DOCS_DIR = SNIPPETS_DIR.parent
"""The documentation root, holding one folder per language."""

FILES = {
    "overrides_config.py": {"piighost.toml": "overrides_config.toml"},
    "loaders.py": {
        "pipeline.toml": "loaders.pipeline.toml",
        "thread.toml": "loaders.thread.toml",
    },
    "reference_langchain.py": {"pipeline.toml": "reference_langchain.toml"},
}
"""The files an example reads, copied from docs/snippets/ under the name it opens."""

REQUIRES = {
    "detector_gliner2.py": "gliner2",
    "extending_gliner2.py": "gliner2",
    "observation_langfuse.py": "langfuse",
    "tool_call_middleware.fr.py": "langchain",
    "tool_call_middleware.en.py": "langchain",
    "langchain_start.py": "langchain",
    "langchain_agent.py": "langchain",
    "langchain_pipeline.py": "gliner2",
    "pydantic_ai_agent.py": "pydantic_ai",
    "pydantic_ai_pipeline.py": "gliner2",
    "llama_index_rag.py": "llama_index.core",
    "reference_llm_detector.py": "langchain",
    "reference_langchain.py": "langchain",
    "reference_hub_pipeline.py": "gliner2",
    "reference_composite.py": "gliner2",
    "reference_chunked.py": "spacy",
    "reference_transformers.py": "transformers",
    "reference_guard_gliner2.py": "gliner2",
    "reference_gliner2_guard.py": "gliner2",
    "reference_gliner2_pipeline.py": "gliner2",
    "upgrading.py": "langchain",
}
"""The optional package an example needs, skipped when it is absent."""

FAILS = {"reference_gliner2_guard.py": "piighost.exceptions.PIIRemainingError"}
"""The examples a page shows ending on an error, with the error they end on."""

BANNERS = {"reference_gliner2_pipeline.py"}
"""The examples whose model prints a banner of its own first: the output ends on the .out."""

TIMEOUT = 300
"""Seconds an example may take, a model download included."""


def _name(case: Any) -> str:
    """The file name a case of SNIPPETS stands for."""
    return case if isinstance(case, str) else case.values[0]


def _expected(snippet: Path) -> str | None:
    """The output a snippet's .out declares, its section markers removed."""
    out = snippet.with_suffix(".out")
    if not out.exists():
        return None
    lines = out.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(line for line in lines if "--8<--" not in line)


RUNNER = """
import ast, asyncio, os, sys
path = sys.argv[1]
sys.path.insert(0, os.path.dirname(path))
code = compile(open(path, encoding="utf-8").read(), path, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
result = eval(code, {"__name__": "__main__", "__file__": path})
if asyncio.iscoroutine(result):
    asyncio.run(result)
"""
"""Run a file as `python <file>` does, a top-level await included, as a page may show one."""


def _run(snippet: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run an example as a reader would, or a test file under pytest."""
    command = [sys.executable, "-c", RUNNER, str(snippet)]
    if snippet.name.startswith("test_"):
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(snippet),
        ]
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )


@pytest.mark.parametrize("name", SNIPPETS)
def test_an_example_runs_and_prints_what_the_page_shows(
    name: str, tmp_path: Path
) -> None:
    """An example exits cleanly, or on the error FAILS names, and prints its .out."""
    if name in REQUIRES:
        pytest.importorskip(REQUIRES[name])
    snippet = SNIPPETS_DIR / name
    for opened, source in FILES.get(name, {}).items():
        (tmp_path / opened).write_text(
            (SNIPPETS_DIR / source).read_text(encoding="utf-8"), encoding="utf-8"
        )
    result = _run(snippet, tmp_path)
    if name in FAILS:
        assert result.returncode != 0, result.stdout
        assert result.stderr.splitlines()[-1].startswith(FAILS[name]), result.stderr
        return
    assert result.returncode == 0, result.stdout + result.stderr
    expected = _expected(snippet)
    if expected is not None and name in BANNERS:
        assert result.stdout.endswith(expected)
    elif expected is not None:
        assert result.stdout == expected


def test_every_example_is_listed() -> None:
    """A file added to docs/snippets/ without a case here would never run."""
    listed = {_name(case) for case in SNIPPETS}
    on_disk = {path.name for path in SNIPPETS_DIR.glob("[!_]*.py")}
    assert on_disk == listed


@pytest.mark.parametrize(
    "config", sorted(path.name for path in SNIPPETS_DIR.glob("*.toml"))
)
def test_a_config_example_is_valid(config: str) -> None:
    """A configuration a page shows parses, hub references included."""
    load_config(SNIPPETS_DIR / config)


SHOWN_CLASSES = {
    "ports.py": "the ports of extending.md",
    "architecture_port.py": "the detector port of architecture.md",
    "architecture_template.fr.py": "the linker template, French comments",
    "architecture_template.en.py": "the linker template, English comments",
    "placeholder_builtins.py": "the built-in factories of placeholder-factories.md",
}
"""The examples that show a class of piighost, which must match the real one."""

REAL_CLASSES = {
    "AnyDetector": "piighost.components.detector.base",
    "AnyOverlapResolver": "piighost.components.overlap_resolver.base",
    "AnyDetectionExpander": "piighost.components.expander.base",
    "AnyEntityLinker": "piighost.components.linker.base",
    "AnyEntityResolver": "piighost.components.entity_resolver.base",
    "AnyPlaceholderFactory": "piighost.components.placeholder.base",
    "AnyGuardRail": "piighost.components.guard.base",
    "BaseEntityLinker": "piighost.components.linker.base",
    "LabelCounterPlaceholderFactory": "piighost.components.placeholder",
    "LabelHashPlaceholderFactory": "piighost.components.placeholder",
    "LabelPlaceholderFactory": "piighost.components.placeholder",
    "MaskPlaceholderFactory": "piighost.components.placeholder",
    "RedactPlaceholderFactory": "piighost.components.placeholder",
}
"""Where each class a page shows really lives."""


@pytest.mark.parametrize("name", SHOWN_CLASSES)
def test_a_class_a_page_shows_matches_the_code(name: str) -> None:
    """Its methods have the real signatures, and its bases are real bases of it."""
    shown = runpy.run_path(str(SNIPPETS_DIR / name))
    classes = {
        key: value
        for key, value in shown.items()
        if isinstance(value, type) and key in REAL_CLASSES
    }
    assert classes, f"{name} shows no class of piighost"
    for class_name, fake in classes.items():
        real = getattr(importlib.import_module(REAL_CLASSES[class_name]), class_name)
        for method, function in vars(fake).items():
            if callable(function) and not method.startswith("__"):
                assert inspect.signature(function) == inspect.signature(
                    getattr(real, method)
                ), f"{class_name}.{method}"
        for base in fake.__bases__:
            real_base = REAL_CLASSES.get(base.__name__) and getattr(
                importlib.import_module(REAL_CLASSES[base.__name__]), base.__name__
            )
            if real_base:
                assert issubclass(real, real_base), (
                    f"{class_name} is not a {base.__name__}"
                )


def test_every_output_has_its_example() -> None:
    """A .out without its .py would show an output no code produces."""
    orphans = [
        out.name
        for out in SNIPPETS_DIR.glob("*.out")
        if not out.with_suffix(".py").exists()
    ]
    assert orphans == []


@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("page", MIGRATED)
def test_a_migrated_page_writes_no_python_by_hand(page: str, lang: str) -> None:
    """A Python block of a migrated page is an include, so it cannot drift from its test."""
    text = (DOCS_DIR / lang / page).read_text(encoding="utf-8")
    blocks = re.findall(
        r"^([ \t]*)```python\n(.*?)^\1```", text, flags=re.DOTALL | re.MULTILINE
    )
    written = [body for _, body in blocks if "--8<--" not in body]
    assert written == []
