"""Handling strategies for the anonymization middleware.

Plain enums with no external dependency, kept out of the langchain-guarded
module so they can be imported and referenced, for example by the config loader,
without installing langchain.
"""

import warnings
from enum import Enum
from typing import Any


class ToolCallStrategy(Enum):
    """How the middleware handles the two directions of a tool call.

    The two directions are independent, and the middleware acts only in the tool
    wrapper, never on the stored response afterwards. INPUT deanonymizes the tool
    arguments so the tool receives real data; OUTPUT anonymizes a string tool
    response so any PII it returns is protected; FULL does both; PASSTHROUGH does
    neither. A strategy that does not anonymize the response leaves it as the tool
    returned it, and the model sees it that way.

    - INPUT: deanonymize the arguments, leave the response raw, so the model sees
      the tool's output unchanged.
    - OUTPUT: anonymize the response, leave the arguments tokenized.
    - FULL: INPUT and OUTPUT together.
    - PASSTHROUGH: touch neither.
    """

    INPUT = "input"
    OUTPUT = "output"
    FULL = "full"
    PASSTHROUGH = "passthrough"


class InventedPlaceholderStrategy(Enum):
    """How the middleware treats a placeholder token the pipeline never issued.

    After deanonymizing, every issued token has been replaced by its value, so
    any token still matching the placeholder grammar was invented by the model,
    whether hallucinated or injected.

    - KEEP: leave the invented token in the text.
    - DROP: remove the invented token from the text.
    - RAISE: raise InventedPlaceholderError.
    """

    KEEP = "keep"
    DROP = "drop"
    RAISE = "raise"


class EntityCreateByAssistantStrategy(Enum):
    """How the middleware treats entities the assistant introduces.

    A value's provenance is the role of its first occurrence in the thread. A
    value the assistant introduced is not user PII, so anonymizing it strips the
    model of its world knowledge of that entity.

    - PRESERVE: leave assistant-introduced values in clear.
    - ANONYMIZE: anonymize them like user PII.
    - IGNORE: do not analyze assistant messages at all, saving the detector.

    Formerly named AssistantEntityStrategy, which stays importable as a deprecated
    alias.
    """

    PRESERVE = "preserve"
    ANONYMIZE = "anonymize"
    IGNORE = "ignore"


_RENAMED_STRATEGIES = {"AssistantEntityStrategy": EntityCreateByAssistantStrategy}
"""Deprecated strategy names mapped to their current class."""


def __getattr__(name: str) -> Any:
    """Return a renamed strategy under its old name, warning that it is deprecated."""
    renamed = _RENAMED_STRATEGIES.get(name)
    if renamed is not None:
        warnings.warn(
            f"{name} is deprecated and renamed to {renamed.__name__}; "
            f"import {renamed.__name__} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return renamed
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
