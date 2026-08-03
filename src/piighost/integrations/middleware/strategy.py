"""Handling strategies for the anonymization middleware.

Plain enums with no external dependency, kept out of the langchain-guarded
module so they can be imported and referenced, for example by the config loader,
without installing langchain.
"""

from enum import Enum


class ToolCallStrategy(Enum):
    """How the middleware handles the two directions of a tool call.

    The two directions are independent. INPUT deanonymizes the tool arguments so
    the tool receives real data; OUTPUT anonymizes a string tool response so any
    PII it returns is protected; FULL does both; PASSTHROUGH does neither, so the
    tool sees the placeholder tokens and its response is left untouched.

    - INPUT: deanonymize the arguments, leave the response for the next model
      pass to anonymize.
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


class AssistantEntityStrategy(Enum):
    """How the middleware treats entities the assistant introduces.

    A value's provenance is the role of its first occurrence in the thread. A
    value the assistant introduced is not user PII, so anonymizing it strips the
    model of its world knowledge of that entity.

    - PRESERVE: leave assistant-introduced values in clear.
    - ANONYMIZE: anonymize them like user PII.
    - IGNORE: do not analyze assistant messages at all, saving the detector.
    """

    PRESERVE = "preserve"
    ANONYMIZE = "anonymize"
    IGNORE = "ignore"
