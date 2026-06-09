"""The core package must import without any optional extra installed.

Runs in a subprocess so the parent test session (which has pydantic
installed and imported) cannot mask a hard dependency. A MetaPathFinder
raises ModuleNotFoundError for the blocked package, simulating its absence.
"""

import subprocess
import sys
import textwrap

CORE_MODULES = [
    "piighost",
    "piighost.anonymizer",
    "piighost.placeholder",
    "piighost.placeholder_tags",
    "piighost.detector",
    "piighost.detector.base",
    "piighost.detector.chunked",
    "piighost.linker",
    "piighost.linker.entity",
    "piighost.resolver",
    "piighost.resolver.span",
    "piighost.resolver.entity",
    "piighost.guard",
    "piighost.models",
    "piighost.validators",
    "piighost.similarity",
    "piighost.utils",
    "piighost.labels",
    "piighost.exceptions",
    "piighost.pipeline",
    "piighost.pipeline.base",
    "piighost.pipeline.thread",
]


def _import_with_blocked(package: str) -> subprocess.CompletedProcess:
    code = textwrap.dedent(f"""
        import importlib.abc
        import sys

        class Blocker(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                # This blocker raises from find_spec rather than returning None,
                # so it must not be used to simulate packages that core guards via
                # importlib.util.find_spec (e.g. aiocache, faker).
                if name == "{package}" or name.startswith("{package}."):
                    raise ModuleNotFoundError(name + " blocked (simulating missing extra)")

        sys.meta_path.insert(0, Blocker())
        import importlib
        for module in {CORE_MODULES!r}:
            importlib.import_module(module)
        print("ok")
    """)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_core_importable_without_pydantic():
    result = _import_with_blocked("pydantic")
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
