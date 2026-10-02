from piighost.components.placeholder import AnyPlaceholderFactory
from piighost.components.placeholder.base import BaseCounterPlaceholderFactory
from piighost.components.placeholder.tags import (
    PreservesLabel,
    PreservesNothing,
    PreservesShape,
)


# isort: split
# --8<-- [start:example]
class LabelCounterPlaceholderFactory(
    BaseCounterPlaceholderFactory
): ...  # PreservesLabeledIdentityOpaque


class LabelHashPlaceholderFactory(
    BaseCounterPlaceholderFactory
): ...  # PreservesLabeledIdentityOpaque


class LabelPlaceholderFactory(AnyPlaceholderFactory[PreservesLabel]): ...


class MaskPlaceholderFactory(AnyPlaceholderFactory[PreservesShape]): ...


class RedactPlaceholderFactory(AnyPlaceholderFactory[PreservesNothing]): ...


# No built-in for the id-only branch nor the realistic hashed one,
# implement your own with PreservesIdentityOnly or PreservesLabeledIdentityHashed.
# --8<-- [end:example]
