"""Tests for the ModerationGuardRail and its optional-dependency guard."""

import importlib
import importlib.util
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from piighost.components.guard.moderation import ModerationGuardRail

_MODULE = "piighost.components.guard.moderation"


class _Result:
    """A moderation result carrying preset category scores."""

    def __init__(self, category_scores: dict[str, float] | None) -> None:
        self.category_scores = category_scores


class _Response:
    """A moderation response holding one result per input."""

    def __init__(self, category_scores: dict[str, float] | None) -> None:
        self.results = [_Result(category_scores)]


def _guard(
    scores: dict[str, float] | None,
    monkeypatch: pytest.MonkeyPatch,
    threshold: float = 0.5,
) -> "ModerationGuardRail":
    """Build a guard over a real Mistral client whose moderation is faked."""
    from mistralai.client import Mistral

    from piighost.components.guard import ModerationGuardRail

    client = Mistral(api_key="test")

    async def fake_moderate(model: str, inputs: str) -> _Response:
        return _Response(scores)

    monkeypatch.setattr(client.classifiers, "moderate_async", fake_moderate)
    return ModerationGuardRail(client, threshold=threshold)


class TestOptionalDependencyGuard:
    def test_missing_mistralai_explains_how_to_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing without mistralai points the user at piighost[mistral]."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: object, **kwargs: object) -> object:
            if name == "mistralai":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        sys.modules.pop(_MODULE, None)

        with pytest.raises(ImportError, match=r"piighost\[mistral\]"):
            importlib.import_module(_MODULE)

        sys.modules.pop(_MODULE, None)


class TestUsableWhenInstalled:
    def test_conforms_to_the_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With mistralai installed, ModerationGuardRail is an AnyGuardRail."""
        pytest.importorskip("mistralai")
        from piighost.components.guard import AnyGuardRail

        assert isinstance(_guard({"pii": 0.1}, monkeypatch), AnyGuardRail)

    def test_real_client_exposes_moderate_async(self) -> None:
        """The installed SDK really has the async moderation call the guard uses."""
        pytest.importorskip("mistralai")
        from mistralai.client import Mistral

        assert hasattr(Mistral(api_key="test").classifiers, "moderate_async")

    async def test_flags_when_pii_reaches_the_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PII score at or above the threshold flags the verdict."""
        pytest.importorskip("mistralai")
        guard = _guard({"pii": 0.9}, monkeypatch, threshold=0.5)
        verdict = await guard.check("<<PERSON:1>> lives in Paris")
        assert verdict.flagged is True
        assert verdict.score == 0.9

    async def test_does_not_flag_below_the_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PII score below the threshold leaves the verdict unflagged."""
        pytest.importorskip("mistralai")
        guard = _guard({"pii": 0.1}, monkeypatch, threshold=0.5)
        verdict = await guard.check("nothing sensitive")
        assert verdict.flagged is False

    async def test_threshold_is_configurable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same score flags or not depending on the threshold."""
        pytest.importorskip("mistralai")
        lenient = _guard({"pii": 0.4}, monkeypatch, threshold=0.3)
        strict = _guard({"pii": 0.4}, monkeypatch, threshold=0.5)
        assert (await lenient.check("x")).flagged is True
        assert (await strict.check("x")).flagged is False

    async def test_missing_pii_category_is_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A response without a PII score scores zero and does not flag."""
        pytest.importorskip("mistralai")
        guard = _guard({"violence": 0.9}, monkeypatch)
        verdict = await guard.check("safe text")
        assert verdict.flagged is False
        assert verdict.score == 0.0
