import pytest
from pydantic import ValidationError

from piighost.config.models.common import _ComponentConfig


class _Sample(_ComponentConfig):
    x: int


def test_component_config_forbids_extra_keys():
    with pytest.raises(ValidationError) as exc:
        _Sample.model_validate({"x": 1, "rogue": True})
    assert "rogue" in str(exc.value)


def test_component_config_is_frozen():
    s = _Sample.model_validate({"x": 1})
    with pytest.raises(ValidationError):
        s.x = 2
