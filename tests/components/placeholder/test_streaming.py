"""Tests for the streaming-safe placeholder decoder."""

from collections.abc import Callable

import pytest

from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PlaceholderStreamDecoder,
)

_MAPPING = {"<<PERSON:1>>": "Emma", "<<EMAIL:1>>": "emma@mail.com"}

STREAM_CASES = [
    pytest.param(["Hello <<PERSON:1>>!"], "Hello Emma!", id="whole-token-in-one-chunk"),
    pytest.param(
        ["Hello <<PER", "SON:1>>!"], "Hello Emma!", id="token-split-across-chunks"
    ),
    pytest.param(
        ["<<PER", "SON:1>> mailed <<EMA", "IL:1>>"],
        "Emma mailed emma@mail.com",
        id="several-tokens-each-rewritten",
    ),
    pytest.param(["see <<PERSON:9>>"], "see <<PERSON:9>>", id="unknown-token-kept"),
    pytest.param(
        ["oops <<PERSON:1"], "oops <<PERSON:1", id="unclosed-released-on-flush"
    ),
]
"""Each case is (chunks fed in order, text expected after feeding then flushing)."""


def _replace() -> Callable[[str], str]:
    """Return a replace callback deanonymizing known tokens, keeping the rest."""
    return lambda token: _MAPPING.get(token, token)


def _stream(decoder: PlaceholderStreamDecoder, chunks: list[str]) -> str:
    """Feed every chunk then flush, returning the concatenated output."""
    out = [decoder.feed(chunk) for chunk in chunks]
    out.append(decoder.flush())
    return "".join(out)


class TestFeed:
    @pytest.mark.parametrize(("chunks", "expected"), STREAM_CASES)
    def test_feeding_then_flushing_yields_expected_text(
        self, chunks: list[str], expected: str
    ) -> None:
        """Feeding the chunks then flushing rewrites tokens and keeps them whole."""
        decoder = PlaceholderStreamDecoder(_replace())
        assert _stream(decoder, chunks) == expected

    def test_split_delimiter_is_held(self) -> None:
        """A single delimiter char at a boundary is not emitted early."""
        decoder = PlaceholderStreamDecoder(_replace())
        first = decoder.feed("Hi <")
        assert first == "Hi "
        assert _stream(decoder, ["<PERSON:1>>"]) == "Emma"

    def test_plain_text_streams_through_untouched(self) -> None:
        """Text with no delimiters is emitted as it arrives, before any flush."""
        decoder = PlaceholderStreamDecoder(_replace())
        assert decoder.feed("just words") == "just words"


class TestFromFactory:
    def test_factory_builds_a_matching_decoder(self) -> None:
        """A factory hands out a decoder that recognizes its own delimiters."""
        factory = LabelCounterPlaceholderFactory("[[", "]]")
        decoder = factory.stream_decoder(lambda token: "Emma")
        assert _stream(decoder, ["Hi [[PER", "SON:1]]"]) == "Hi Emma"
