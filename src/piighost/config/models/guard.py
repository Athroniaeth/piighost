"""Guard rail configuration models, discriminated on type."""

import os
from typing import Annotated, Literal

from pydantic import Discriminator, Field

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
    """Config for the LLM guard, prompting a model to find residual PII."""

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


GuardConfig = Annotated[
    DetectorGuardRailConfig | LLMGuardRailConfig | ModerationGuardRailConfig,
    Discriminator("type"),
]
