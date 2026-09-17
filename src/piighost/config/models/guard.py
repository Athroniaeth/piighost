"""Guard rail configuration models, discriminated on type."""

import os
from typing import Annotated, Literal

from pydantic import Discriminator, Field, field_validator

from piighost.components.guard.base import AnyGuardRail
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig
from piighost.exceptions import ConfigError

_DEFAULT_MODERATION_MODEL = "mistral-moderation-latest"
"""The Mistral moderation model the moderation guard scores with by default."""

_DEFAULT_MODERATION_THRESHOLD = 0.5
"""The category score above which the moderation guard flags the text."""

_MODERATION_API_KEY_ENV = "MISTRAL_API_KEY"
"""The environment variable holding the Mistral key the moderation guard needs."""

_DEFAULT_GLINER2_MODEL = "fastino/GLiNER2-Guardrails-PII-Multi"
"""The local checkpoint the GLiNER2 guard classifies with by default."""

_DEFAULT_GLINER2_TASK = "response_safety"
"""The task read: whether a produced text is safe to return."""

_DEFAULT_GLINER2_LABELS = ("safe", "unsafe")
"""The two answers the safety tasks choose between, the refused one last."""

_DEFAULT_GLINER2_THRESHOLD = 0.5
"""Confidence at or above which an unsafe answer flags the verdict."""


class DetectorGuardRailConfig(_ComponentConfig):
    """Config for the detector guard, re-running a detector on the output."""

    type: Literal["detector"]
    detector: DetectorConfig

    def build(self) -> AnyGuardRail:
        """Build a DetectorGuardRail over the built detector."""
        from piighost.components.guard.detector import DetectorGuardRail

        detector = self.detector.build()
        return DetectorGuardRail(detector)


class LLMGuardRailConfig(_ComponentConfig):
    """Config for the LLM guard, prompting a model to find residual PII.

    Attributes:
        model: The chat model identifier the guard prompts.
        labels: The labels the guard is told to look for, a list or an emitted to
            model mapping.
        prompt: The prompt overriding the default guard instructions, or None.
        provider: The chat model provider, or None to infer it from the model.
    """

    type: Literal["llm"]
    model: str
    labels: list[str] | dict[str, str]
    prompt: str | None = None
    provider: str | None = None

    def build(self) -> AnyGuardRail:
        """Build an LLMGuardRail from the model, labels, prompt, and provider."""
        from piighost.components.guard.llm import LLMGuardRail

        return LLMGuardRail(
            model=self.model,
            labels=self.labels,
            prompt=self.prompt,
            provider=self.provider,
        )


class ModerationGuardRailConfig(_ComponentConfig):
    """Config for the moderation guard, scoring the output with Mistral.

    The Mistral credential is read from the MISTRAL_API_KEY environment variable,
    the Mistral SDK's own variable, not from the TOML, so a secret is never
    committed. build() requires it to be present and raises a ConfigError when it
    is not, rather than deferring an opaque authentication failure to the first
    moderation call.

    Attributes:
        model: The Mistral moderation model the guard scores with.
        threshold: The category score at or above which the guard flags the text.
    """

    type: Literal["moderation"]
    model: str = _DEFAULT_MODERATION_MODEL
    threshold: float = Field(default=_DEFAULT_MODERATION_THRESHOLD, ge=0.0, le=1.0)

    def build(self) -> AnyGuardRail:
        """Build a ModerationGuardRail over a Mistral client read from the env.

        Raises:
            ConfigError: If the MISTRAL_API_KEY environment variable is unset, so
                the missing credential surfaces at build time, not at first call.
        """
        from mistralai.client import Mistral

        from piighost.components.guard.moderation import ModerationGuardRail

        api_key = os.environ.get(_MODERATION_API_KEY_ENV)
        if not api_key:
            raise ConfigError(
                f"the moderation guard requires the {_MODERATION_API_KEY_ENV} "
                "environment variable to be set"
            )
        client = Mistral(api_key=api_key)
        return ModerationGuardRail(
            client=client, model=self.model, threshold=self.threshold
        )


class Gliner2GuardRailConfig(_ComponentConfig):
    """Config for the GLiNER2 guard, classifying the output with a local model.

    It needs no credential: the model runs in the process, which is the whole
    point of preferring it to the moderation guard. The checkpoint is downloaded
    on first build and cached by Hugging Face afterwards.

    Attributes:
        model: The GLiNER2 checkpoint the guard classifies with.
        task: The classification task read from the model's answer.
        labels: The answers the task chooses between, the unsafe one last.
        threshold: The confidence at or above which an unsafe answer flags.
    """

    type: Literal["gliner2"]
    model: str = _DEFAULT_GLINER2_MODEL
    task: str = _DEFAULT_GLINER2_TASK
    labels: tuple[str, ...] = _DEFAULT_GLINER2_LABELS
    threshold: float = Field(default=_DEFAULT_GLINER2_THRESHOLD, ge=0.0, le=1.0)

    @field_validator("labels")
    @classmethod
    def _two_labels_at_least(cls, labels: tuple[str, ...]) -> tuple[str, ...]:
        """Require the pair the guard reads: an accepted answer and a refused one."""
        if len(labels) < 2:
            raise ValueError("a gliner2 guard needs at least two labels")
        return labels

    def build(self) -> AnyGuardRail:
        """Build a Gliner2GuardRail over the named checkpoint."""
        from piighost.components.guard.gliner2 import Gliner2GuardRail

        return Gliner2GuardRail(
            model=self.model,
            task=self.task,
            labels=self.labels,
            threshold=self.threshold,
        )


GuardConfig = Annotated[
    DetectorGuardRailConfig
    | Gliner2GuardRailConfig
    | LLMGuardRailConfig
    | ModerationGuardRailConfig,
    Discriminator("type"),
]
