from pathlib import Path

from pydantic import BaseModel, ValidationError

from piighost.config.errors import ConfigError


class _Sample(BaseModel):
    x: int


def test_config_error_is_an_exception():
    err = ConfigError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"


def test_from_pydantic_renders_dotted_path_and_reason():
    try:
        _Sample.model_validate({"x": "not-an-int"})
    except ValidationError as e:
        ce = ConfigError.from_pydantic(e, Path("/tmp/conf.toml"))
    assert "/tmp/conf.toml" in str(ce)
    assert "x" in str(ce)
    assert "int" in str(ce).lower()


def test_from_pydantic_handles_nested_paths():
    class Inner(BaseModel):
        n: int

    class Outer(BaseModel):
        inner: Inner

    try:
        Outer.model_validate({"inner": {"n": "bad"}})
    except ValidationError as e:
        ce = ConfigError.from_pydantic(e, Path("/tmp/c.toml"))
    assert "inner.n" in str(ce)
