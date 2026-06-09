"""The core package must import without any optional extra installed.

Runs in a subprocess so the parent test session (which has pydantic
installed and imported) cannot mask a hard dependency. A MetaPathFinder
raises ImportError for the blocked package, simulating its absence.
"""

import subprocess
import sys
import textwrap

CORE_MODULES = [
    "piighost",
    "piighost.anonymizer",
    "piighost.placeholder",
    "piighost.placeholder_tags",
    "piighost.detector.base",
    "piighost.linker.entity",
    "piighost.resolver.span",
    "piighost.resolver.entity",
    "piighost.guard",
    "piighost.models",
    "piighost.validators",
]


def _import_with_blocked(package: str) -> subprocess.CompletedProcess:
    code = textwrap.dedent(f"""
        import importlib.abc
        import sys

        class Blocker(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "{package}" or name.startswith("{package}."):
                    raise ImportError(name + " blocked (simulating missing extra)")

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
