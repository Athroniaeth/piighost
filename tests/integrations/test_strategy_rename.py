"""AssistantEntityStrategy is a deprecated alias for EntityCreateByAssistantStrategy.

The strategy enums are dependency-free, so this runs without the langchain extra.
"""

import pytest

from piighost.integrations.langchain.strategy import EntityCreateByAssistantStrategy


def test_deprecated_alias_warns_and_returns_the_renamed_enum() -> None:
    """Reaching for the old name warns and yields the renamed enum."""
    with pytest.warns(DeprecationWarning, match="EntityCreateByAssistantStrategy"):
        from piighost.integrations.langchain.strategy import AssistantEntityStrategy

    assert AssistantEntityStrategy is EntityCreateByAssistantStrategy


def test_deprecated_alias_on_the_package_warns() -> None:
    """The alias is also served, with the warning, from the langchain package."""
    from piighost.integrations import langchain

    with pytest.warns(DeprecationWarning, match="EntityCreateByAssistantStrategy"):
        strategy = langchain.AssistantEntityStrategy

    assert strategy is EntityCreateByAssistantStrategy


def test_new_name_does_not_warn(recwarn: pytest.WarningsRecorder) -> None:
    """Accessing the current name emits no deprecation warning."""
    from piighost.integrations.langchain import strategy

    assert strategy.EntityCreateByAssistantStrategy is EntityCreateByAssistantStrategy
    assert not any("deprecated" in str(warning.message) for warning in recwarn)
