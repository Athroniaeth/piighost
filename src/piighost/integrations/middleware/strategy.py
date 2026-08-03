"""Tool-call handling strategy for the anonymization middleware.

A plain enum with no external dependency, kept out of the langchain-guarded
module so it can be imported and referenced, for example by the config loader,
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
