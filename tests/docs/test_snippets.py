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
import json
import os
import re
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from piighost.config import load_config

SNIPPETS_DIR = Path(__file__).resolve().parents[2] / "docs" / "snippets"
"""Where the documentation's examples live."""

SNIPPETS: list[Any] = [
    "quickstart.en.py",
    "quickstart.fr.py",
    "first_pipeline.en.py",
    "first_pipeline.fr.py",
    "conversation.en.py",
    "conversation.fr.py",
    "basic_exact.en.py",
    "basic_exact.fr.py",
    "basic_factories.py",
    "testing.py",
    "test_testing.py",
    "overrides_allow_list.py",
    "overrides_allow_list_strategies.py",
    "overrides_deny_list_exact.py",
    "overrides_deny_list_provenance.py",
    "overrides_conflict.py",
    "extending.py",
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
    "langchain_start.en.py",
    "langchain_start.fr.py",
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
    "toml_loaders.py",
    "server_connect.py",
    "server_middleware.py",
    "server_proxy_upstream.py",
    # These reach the hub or download a model.
    pytest.param("basic.py", marks=pytest.mark.integration),
    pytest.param("detector_hub.py", marks=pytest.mark.integration),
    pytest.param("detector_gliner2.py", marks=pytest.mark.integration),
    pytest.param("overrides_deny_list_hub.py", marks=pytest.mark.integration),
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
    pytest.param("redis_run.py", marks=pytest.mark.integration),
    pytest.param("redis_load.py", marks=pytest.mark.integration),
    pytest.param("redis_two_workers.py", marks=pytest.mark.integration),
    # These call a piighost-api server, which the test starts.
    pytest.param("server_client.en.py", marks=pytest.mark.integration),
    pytest.param("server_client.fr.py", marks=pytest.mark.integration),
    pytest.param("server_forget.py", marks=pytest.mark.integration),
    pytest.param("server_api.py", marks=pytest.mark.integration),
    pytest.param("server_proxy.py", marks=pytest.mark.integration),
]
"""Every example, the ones that need the network or a model marked integration."""


DOCS_DIR = SNIPPETS_DIR.parent
"""The documentation root, holding one folder per language."""

WRITTEN_BY_HAND = ("reference/", "configuration/", "security.md")
"""The pages that write signatures, ports, import lists and sessions by hand.

They do not run, so tests/docs/test_reference_signatures.py, whose
CHECKED_PAGES names the same pages, compares them with the code instead.
"""

PAGES = sorted(
    page.relative_to(DOCS_DIR / "en").as_posix()
    for page in (DOCS_DIR / "en").rglob("*.md")
    if not page.relative_to(DOCS_DIR / "en").as_posix().startswith(WRITTEN_BY_HAND)
)
"""Every other page, whose Python all comes from docs/snippets/."""

FILES = {
    "overrides_config.py": {"pipeline.toml": "overrides_config.toml"},
    "loaders.py": {
        "pipeline.toml": "loaders.pipeline.toml",
        "thread.toml": "loaders.thread.toml",
    },
    "reference_langchain.py": {"pipeline.toml": "reference_langchain.toml"},
    "redis_run.py": {"pipeline.toml": "redis_pipeline.toml"},
    "redis_load.py": {"pipeline.toml": "redis_pipeline.toml"},
    "redis_two_workers.py": {"pipeline.toml": "redis_pipeline.toml"},
    "toml_loaders.py": {
        "pipeline.toml": "loaders.pipeline.toml",
        "thread.toml": "loaders.thread.toml",
    },
}
"""The files an example reads, copied from docs/snippets/ under the name it opens."""

REQUIRES = {
    "detector_gliner2.py": "gliner2",
    "extending_gliner2.py": "gliner2",
    "observation_langfuse.py": "langfuse",
    "tool_call_middleware.fr.py": "langchain",
    "tool_call_middleware.en.py": "langchain",
    "langchain_start.en.py": "langchain",
    "langchain_start.fr.py": "langchain",
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
    "redis_run.py": "fakeredis",
    "redis_load.py": "fakeredis",
    "redis_two_workers.py": "fakeredis",
    "server_connect.py": "httpx",
    "server_middleware.py": "langchain",
    "server_proxy_upstream.py": "openai",
    "server_client.en.py": "httpx",
    "server_client.fr.py": "httpx",
    "server_forget.py": "httpx",
    "server_api.py": "httpx",
    "server_proxy.py": "openai",
}
"""The optional package an example needs, skipped when it is absent."""

FAILS = {"reference_gliner2_guard.py": "piighost.exceptions.PIIRemainingError"}
"""The examples a page shows ending on an error, with the error they end on."""

BANNERS = {"reference_gliner2_pipeline.py"}
"""The examples whose model prints a banner of its own first: the output ends on the .out."""

SERVED = {
    "server_client.en.py",
    "server_client.fr.py",
    "server_forget.py",
    "server_api.py",
    "server_proxy.py",
}
"""The examples that call a piighost-api server, started for each on a free port."""

KEYED = {"server_api.py"}
"""The served examples that send an API key, so their server checks one."""

SERVER_CONFIG = "server_config.toml"
"""The configuration of that server, knowing the values the examples write."""

UPSTREAM_SECRETS = ("Jane Doe", "jane.doe@example.com")
"""What the fake OpenAI upstream must never receive in clear."""

TOKEN = re.compile(r"<<[A-Z_]+:\d+>>")
"""A token of the server's LabelCounterPlaceholderFactory."""

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


def _run(
    snippet: Path, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
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
        command,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class _Upstream(BaseHTTPRequestHandler):
    """An OpenAI provider that greets the tokens it receives, and fails on a clear value."""

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the test output quiet."""

    def do_POST(self) -> None:
        """Answer a chat completion, streamed when asked."""
        raw = self.rfile.read(int(self.headers["Content-Length"])).decode()
        if any(secret in raw for secret in UPSTREAM_SECRETS):
            self.send_error(500, "the provider received a value in clear")
            return
        body = json.loads(raw)
        tokens = TOKEN.findall(str(body["messages"][-1]["content"]))
        reply = f"Hello {', '.join(tokens)}."
        if body.get("stream"):
            self._stream(reply)
            return
        message = {"role": "assistant", "content": reply}
        choice = {"index": 0, "message": message, "finish_reason": "stop"}
        self._send("application/json", json.dumps(_completion([choice])))

    def _stream(self, reply: str) -> None:
        """Stream the reply in pieces of four characters, cutting its tokens."""
        events = [
            _completion([{"index": 0, "delta": {"content": reply[start : start + 4]}}])
            for start in range(0, len(reply), 4)
        ]
        data = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
        self._send("text/event-stream", data + "data: [DONE]\n\n")

    def _send(self, content_type: str, text: str) -> None:
        payload = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _completion(choices: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": "docs",
        "object": "chat.completion",
        "created": 0,
        "model": "docs",
        "choices": choices,
    }


def _api_keys(binary: Path) -> dict[str, str]:
    """An API key and its pepper, generated as the server tutorial does."""
    keys: dict[str, str] = {}
    for command in ("generate", "pepper"):
        printed = subprocess.run(
            [str(binary.with_name("keyshield")), command],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        keys.update(re.findall(r'"(\w+)=([^"]+)"', printed))
    return keys


@contextmanager
def _serving(name: str) -> Iterator[dict[str, str]]:
    """A piighost-api server and a fake upstream, and what the example needs to reach them."""
    found = os.environ.get("PIIGHOST_API_BIN") or shutil.which("piighost-api")
    if not found:
        pytest.skip("needs a piighost-api executable, on PATH or in PIIGHOST_API_BIN")
    binary = Path(found)
    upstream = ThreadingHTTPServer(("127.0.0.1", _free_port()), _Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    port = _free_port()
    keys = _api_keys(binary) if name in KEYED else {}
    env = {
        **os.environ,
        **keys,
        "PIIGHOST_OPENAI_UPSTREAM": f"http://127.0.0.1:{upstream.server_port}/v1",
    }
    if not keys:
        env["PIIGHOST_ALLOW_ANONYMOUS"] = "true"
    command = [str(binary), "serve", "--config", str(SNIPPETS_DIR / SERVER_CONFIG)]
    server = subprocess.Popen(
        [*command, "--port", str(port), "--log-level", "warning"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for(f"http://127.0.0.1:{port}/health", server)
        yield {**keys, "PIIGHOST_DOCS_SERVER": f"127.0.0.1:{port}"}
    finally:
        server.terminate()
        server.wait(timeout=30)
        upstream.shutdown()


def _wait_for(url: str, server: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if server.poll() is not None:
            pytest.fail(
                f"piighost-api stopped: {server.stdout and server.stdout.read()}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    pytest.fail(f"piighost-api did not answer on {url}")


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
    with ExitStack() as stack:
        env = stack.enter_context(_serving(name)) if name in SERVED else {}
        result = _run(snippet, tmp_path, env)
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
@pytest.mark.parametrize("page", PAGES)
def test_a_page_writes_no_python_by_hand(page: str, lang: str) -> None:
    """A Python block of a page is an include, so it cannot drift from its test."""
    text = (DOCS_DIR / lang / page).read_text(encoding="utf-8")
    blocks = re.findall(
        r"^([ \t]*)```python\n(.*?)^\1```", text, flags=re.DOTALL | re.MULTILINE
    )
    written = [body for _, body in blocks if "--8<--" not in body]
    assert written == []
