"""Pin the piighost-docs audit script against violations it must and must not flag.

The script is the only mechanical gate on the documentation, so a regression that
makes it silently inert would report zero findings for the wrong reason. These
cases run it over temporary docs/en and docs/fr trees, asserting both directions:
a known violation is reported, and a look-alike that is legitimate is not.

The script lives under .claude, which is not a package and is excluded from ruff
and pyrefly, so it is loaded by path rather than imported.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_AUDIT_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude"
    / "skills"
    / "piighost-docs"
    / "scripts"
    / "audit.py"
)
"""Path to the audit script, resolved from this file so the cwd does not matter."""

_MECHANICAL_CASES: dict[str, tuple[str, str | None]] = {
    "semicolon in prose": ("Une phrase ; une autre phrase.\n", "point-virgule"),
    "semicolon in a fenced block": ("```python\na = 1; b = 2\n```\n", None),
    "semicolon in an inline span": ("Le code `a; b` reste du code.\n", None),
    "em dash in prose": ("Une phrase — coupée en deux.\n", "tiret cadratin"),
    "french quotes": ("Il écrit « bonjour ».\n", "guillemets francais"),
    "bold brand": ("**PIIGhost** est une librairie Python.\n", "en gras"),
    "bare package name": ("La librairie piighost fait le travail.\n", "police code"),
    "package name in code font": ("La librairie `piighost` travaille.\n", None),
    "cross-language link": ("Voir [la page](../en/index.md).\n", "lien inter-langue"),
}
"""Body of a single FR page, mapped to the finding marker it must produce, or None."""

_TERMINOLOGY_CASES: dict[str, tuple[str, str, str | None]] = {
    "anonymisation in french prose": (
        "fr",
        "L'anonymisation du texte est faite avant l'envoi.\n",
        "anonymisation en prose",
    ),
    "anonymisation drawing the contrast": (
        "fr",
        "La dé-identification n'est pas de l'anonymisation.\n",
        None,
    ),
    "banned inverse verb": (
        "fr",
        "Il faut désanonymiser le texte avant de le lire.\n",
        "vocabulaire inverse interdit",
    ),
    "anonymization in english prose": (
        "en",
        "The anonymization step runs before the model call.\n",
        "anonymisation en prose",
    ),
}
"""Language and body of a single page, mapped to the finding marker, or None."""

_PARITY_CASES: dict[str, tuple[str | None, str | None, str | None]] = {
    "page missing from the french mirror": (
        "# Title\n\nBody.\n",
        None,
        "le miroir FR manque",
    ),
    "page missing from the english mirror": (
        None,
        "# Titre\n\nCorps.\n",
        "le miroir EN manque",
    ),
    "different heading skeleton": (
        "# Title\n\n## Section\n\nBody.\n",
        "# Titre\n\nCorps.\n",
        "structure de titres differente",
    ),
    "different number of code blocks": (
        "# Title\n\n```python\nx = 1\n```\n",
        "# Titre\n",
        "blocs de code differents",
    ),
    "mirrored page": ("# Title\n\nBody.\n", "# Titre\n\nCorps.\n", None),
}
"""EN body and FR body of one page, mapped to the finding marker, or None."""


@pytest.fixture(scope="module")
def audit() -> ModuleType:
    """Load the audit script by path, since .claude is not an importable package."""
    spec = importlib.util.spec_from_file_location("piighost_docs_audit", _AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the docs audit script at {_AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_page(root: Path, lang: str, body: str) -> None:
    """Create docs/<lang>/page.md under a root, parents included."""
    page = root / "docs" / lang / "page.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(body, encoding="utf-8")


def _prepare_tree(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Create both language directories and make the root the working directory."""
    for lang in ("en", "fr"):
        (root / "docs" / lang).mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(root)


def _assert_marker(findings: list[str], marker: str | None) -> None:
    """Assert the marker appears in the findings, or that there are none at all."""
    if marker is None:
        assert findings == []
    else:
        assert any(marker in finding for finding in findings), findings


class TestMechanicalRules:
    @pytest.mark.parametrize(
        ("body", "marker"), _MECHANICAL_CASES.values(), ids=list(_MECHANICAL_CASES)
    )
    def test_flags_a_violation_and_spares_a_look_alike(
        self,
        audit: ModuleType,
        body: str,
        marker: str | None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A house-style violation is reported, and the same shape in code is not."""
        _prepare_tree(tmp_path, monkeypatch)
        _write_page(tmp_path, "fr", body)
        findings: list[str] = []
        audit.mechanical(findings)
        _assert_marker(findings, marker)


class TestTerminology:
    @pytest.mark.parametrize(
        ("lang", "body", "marker"),
        _TERMINOLOGY_CASES.values(),
        ids=list(_TERMINOLOGY_CASES),
    )
    def test_flags_the_wrong_word_and_spares_the_contrast(
        self,
        audit: ModuleType,
        lang: str,
        body: str,
        marker: str | None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A misused term is reported, and a sentence drawing the contrast is not."""
        _prepare_tree(tmp_path, monkeypatch)
        _write_page(tmp_path, lang, body)
        findings: list[str] = []
        audit.terminology(findings)
        _assert_marker(findings, marker)


class TestParity:
    @pytest.mark.parametrize(
        ("en_body", "fr_body", "marker"),
        _PARITY_CASES.values(),
        ids=list(_PARITY_CASES),
    )
    def test_flags_a_mirror_that_diverges(
        self,
        audit: ModuleType,
        en_body: str | None,
        fr_body: str | None,
        marker: str | None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A page missing or shaped differently in the other language is reported."""
        _prepare_tree(tmp_path, monkeypatch)
        if en_body is not None:
            _write_page(tmp_path, "en", en_body)
        if fr_body is not None:
            _write_page(tmp_path, "fr", fr_body)
        findings: list[str] = []
        audit.parity(findings)
        _assert_marker(findings, marker)


class TestGate:
    def test_a_clean_tree_reports_nothing(
        self, audit: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mirrored, style-clean pair of pages yields no finding at all."""
        _prepare_tree(tmp_path, monkeypatch)
        _write_page(tmp_path, "en", "# Title\n\nA plain sentence.\n")
        _write_page(tmp_path, "fr", "# Titre\n\nUne phrase simple.\n")
        assert audit.main() == 0
