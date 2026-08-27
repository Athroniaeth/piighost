"""The pre-1.4.0 piighost.integrations.middleware path still works, with a warning.

The LangChain integration moved to piighost.integrations.langchain. The old path
stays importable as a thin alias that re-exports the same objects and emits a
DeprecationWarning, so existing user code keeps working. These checks use the
dependency-free strategy enums, so they run without the langchain extra.
"""

import importlib
import sys
from typing import Any

import pytest

_OLD = "piighost.integrations.middleware"
_OLD_STRATEGY = "piighost.integrations.middleware.strategy"
_NEW = "piighost.integrations.langchain"


def _reimport(name: str) -> Any:
    """Drop a module from the cache and import it again so its code re-runs."""
    sys.modules.pop(name, None)
    return importlib.import_module(name)


class TestDeprecatedMiddlewareAlias:
    def test_importing_the_old_package_warns(self) -> None:
        sys.modules.pop(_OLD, None)
        with pytest.warns(DeprecationWarning, match=_NEW):
            importlib.import_module(_OLD)

    def test_old_enums_are_the_new_objects(self) -> None:
        from piighost.integrations.langchain import (
            EntityCreateByAssistantStrategy,
            InventedPlaceholderStrategy,
            ToolCallStrategy,
        )

        old = _reimport(_OLD)
        assert old.ToolCallStrategy is ToolCallStrategy
        assert old.InventedPlaceholderStrategy is InventedPlaceholderStrategy
        assert old.EntityCreateByAssistantStrategy is EntityCreateByAssistantStrategy

    def test_old_strategy_submodule_reexports(self) -> None:
        from piighost.integrations.langchain.strategy import ToolCallStrategy

        sys.modules.pop(_OLD, None)
        old_strategy = _reimport(_OLD_STRATEGY)
        assert old_strategy.ToolCallStrategy is ToolCallStrategy

    def test_new_import_does_not_warn(self, recwarn: pytest.WarningsRecorder) -> None:
        _reimport(_NEW)
        messages = [str(w.message) for w in recwarn]
        assert not any("is deprecated" in m for m in messages)
