"""Tests for the ModerationGuardRail, driven by a fake moderation client."""

from piighost.guard import AnyGuardRail, ModerationGuardRail


class _FakeResult:
    """A moderation result carrying preset category scores."""

    def __init__(self, category_scores: dict[str, float] | None) -> None:
        self.category_scores = category_scores


class _FakeClassifiers:
    """A classifiers namespace returning a preset moderation response."""

    def __init__(self, category_scores: dict[str, float] | None) -> None:
        self._category_scores = category_scores
        self.calls: list[tuple[str, str]] = []

    async def moderate_async(self, model: str, inputs: str) -> object:
        """Record the call and return one result with the preset scores."""
        self.calls.append((model, inputs))
        return _FakeResponse([_FakeResult(self._category_scores)])


class _FakeResponse:
    """A moderation response holding one result per input."""

    def __init__(self, results: list[_FakeResult]) -> None:
        self.results = results


class _FakeClient:
    """A stand-in moderation client exposing the classifiers namespace."""

    def __init__(self, category_scores: dict[str, float] | None = None) -> None:
        self.classifiers = _FakeClassifiers(category_scores)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """ModerationGuardRail is an AnyGuardRail."""
        assert isinstance(ModerationGuardRail(_FakeClient()), AnyGuardRail)


class TestCheck:
    async def test_flags_when_pii_score_reaches_the_threshold(self) -> None:
        """A PII score at or above the threshold flags the verdict."""
        guard = ModerationGuardRail(_FakeClient({"pii": 0.9}), threshold=0.5)
        verdict = await guard.check("<<PERSON:1>> lives in Paris")
        assert verdict.flagged is True
        assert verdict.score == 0.9

    async def test_does_not_flag_below_the_threshold(self) -> None:
        """A PII score below the threshold leaves the verdict unflagged."""
        guard = ModerationGuardRail(_FakeClient({"pii": 0.1}), threshold=0.5)
        verdict = await guard.check("nothing sensitive")
        assert verdict.flagged is False
        assert verdict.score == 0.1

    async def test_threshold_is_configurable(self) -> None:
        """The same score flags or not depending on the threshold."""
        client = _FakeClient({"pii": 0.4})
        assert (await ModerationGuardRail(client, threshold=0.3).check("x")).flagged
        assert not (await ModerationGuardRail(client, threshold=0.5).check("x")).flagged

    async def test_missing_pii_category_is_not_flagged(self) -> None:
        """A response without a PII score scores zero and does not flag."""
        guard = ModerationGuardRail(_FakeClient({"violence": 0.9}))
        verdict = await guard.check("safe text")
        assert verdict.flagged is False
        assert verdict.score == 0.0

    async def test_calls_the_configured_model_with_the_text(self) -> None:
        """The guard moderates the given text with its configured model."""
        client = _FakeClient({"pii": 0.2})
        await ModerationGuardRail(client, model="mistral-moderation-latest").check("hi")
        assert client.classifiers.calls == [("mistral-moderation-latest", "hi")]
