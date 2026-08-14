"""Tests for the async streaming-safe placeholder decoder.

These exercise the situations a streamed model reply throws at the decoder: a
token whole in one chunk, a token split anywhere (delimiter, inner form, char by
char), several tokens adjacent or spread across chunks, an unknown token, an
unclosed token at the end, and plain text with no token at all.
"""

from collections.abc import Awaitable, Callable

import pytest

from piighost.components.placeholder import (
    AsyncPlaceholderStreamDecoder,
    LabelCounterPlaceholderFactory,
)

_MAPPING = {
    "<<PERSON:1>>": "Emma",
    "<<EMAIL:1>>": "emma@mail.com",
    "<<CITY:1>>": "Paris",
}
"""Known token to value map, standing in for a thread's deanonymization."""


async def _deanonymize(token: str) -> str:
    """Async replace: return the known value for a token, else the token itself."""
    return _MAPPING.get(token, token)


def _recording_replace() -> tuple[Callable[[str], Awaitable[str]], list[str]]:
    """Return an async replace and the list capturing every token it is called with."""
    calls: list[str] = []

    async def replace(token: str) -> str:
        calls.append(token)
        return _MAPPING.get(token, token)

    return replace, calls


async def _stream(decoder: AsyncPlaceholderStreamDecoder, chunks: list[str]) -> str:
    """Feed every chunk then flush, returning the concatenated output."""
    out: list[str] = []
    for chunk in chunks:
        emitted = await decoder.feed(chunk)
        out.append(emitted)
    out.append(decoder.flush())
    return "".join(out)


def _by_size(text: str, size: int) -> list[str]:
    """Split text into consecutive chunks of at most size characters."""
    return [text[index : index + size] for index in range(0, len(text), size)]


STREAM_CASES = [
    pytest.param(["Hello <<PERSON:1>>!"], "Hello Emma!", id="whole-token-in-one-chunk"),
    pytest.param(["<<PERSON:1>>"], "Emma", id="token-is-the-whole-stream"),
    pytest.param(["<<PERSON:1>> waves"], "Emma waves", id="token-at-the-start"),
    pytest.param(["waves at <<PERSON:1>>"], "waves at Emma", id="token-at-the-end"),
    pytest.param(
        ["Hello <<PER", "SON:1>>!"], "Hello Emma!", id="token-split-across-two-chunks"
    ),
    pytest.param(
        ["Hello <<", "PER", "SON:1", ">>!"],
        "Hello Emma!",
        id="token-split-across-four-chunks",
    ),
    pytest.param(
        ["Hi <", "<PERSON:1>>"], "Hi Emma", id="opening-delimiter-split-across-chunks"
    ),
    pytest.param(
        ["<<PERSON:1", ">", ">"], "Emma", id="closing-delimiter-split-across-chunks"
    ),
    pytest.param(
        ["<<PERSON:1>><<CITY:1>>"], "EmmaParis", id="two-adjacent-tokens-one-chunk"
    ),
    pytest.param(
        ["<<PERSON:1>", "><<CIT", "Y:1>>"],
        "EmmaParis",
        id="two-adjacent-tokens-split-between",
    ),
    pytest.param(
        ["<<PER", "SON:1>> mailed <<EMA", "IL:1>>"],
        "Emma mailed emma@mail.com",
        id="several-tokens-each-split",
    ),
    pytest.param(["just words"], "just words", id="plain-text-no-token"),
    pytest.param(["a >> b >> c"], "a >> b >> c", id="closing-delimiter-only-is-text"),
    pytest.param(["", "hi ", "", "<<PERSON:1>>", ""], "hi Emma", id="empty-chunks"),
    pytest.param(["see <<PERSON:9>>"], "see <<PERSON:9>>", id="unknown-token-kept"),
    pytest.param(
        ["oops <<PERSON:1"], "oops <<PERSON:1", id="unclosed-token-released-on-flush"
    ),
    pytest.param(["trailing <"], "trailing <", id="lone-prefix-fragment-on-flush"),
]
"""Each case is (chunks fed in order, text expected after feeding then flushing)."""

_FULL = "Hi <<PERSON:1>>, write to <<EMAIL:1>> from <<CITY:1>>."
"""A reply mixing prose and three tokens, used for the split-invariance test."""

_FULL_EXPECTED = "Hi Emma, write to emma@mail.com from Paris."
"""What _FULL deanonymizes to, independent of how it is chunked."""


class TestFeed:
    @pytest.mark.parametrize(("chunks", "expected"), STREAM_CASES)
    async def test_feeding_then_flushing_yields_expected_text(
        self, chunks: list[str], expected: str
    ) -> None:
        """Feeding the chunks then flushing rewrites tokens and keeps them whole."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        assert await _stream(decoder, chunks) == expected

    async def test_plain_text_emits_before_any_flush(self) -> None:
        """Text with no delimiter is emitted as it arrives, not held until flush."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        assert await decoder.feed("just words") == "just words"

    async def test_a_split_token_is_held_then_completed(self) -> None:
        """A held token emits only its safe prefix until its closing delimiter."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        first = await decoder.feed("Hi <<PER")
        assert first == "Hi "
        second = await decoder.feed("SON:1>>!")
        assert second == "Emma!"


class TestStreamInvariance:
    @pytest.mark.parametrize("size", range(1, len(_FULL) + 1))
    async def test_output_is_independent_of_chunk_size(self, size: int) -> None:
        """However the reply is chunked, the streamed output is the full restoration."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        chunks = _by_size(_FULL, size)
        assert await _stream(decoder, chunks) == _FULL_EXPECTED

    async def test_char_by_char_reconstructs_every_token(self) -> None:
        """Fed one character at a time, the decoder still restores every token."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        chunks: list[str] = list(_FULL)
        assert await _stream(decoder, chunks) == _FULL_EXPECTED


class TestReplaceContract:
    async def test_replace_is_awaited_once_per_completed_token(self) -> None:
        """The callback is awaited once per token, with the whole token, in order."""
        replace, calls = _recording_replace()
        decoder = AsyncPlaceholderStreamDecoder(replace)
        await _stream(decoder, ["<<PER", "SON:1>> and <<CITY:1>>"])
        assert calls == ["<<PERSON:1>>", "<<CITY:1>>"]

    async def test_replace_is_not_awaited_for_plain_text(self) -> None:
        """Text carrying no token never reaches the callback."""
        replace, calls = _recording_replace()
        decoder = AsyncPlaceholderStreamDecoder(replace)
        await _stream(decoder, ["no tokens here"])
        assert calls == []


class TestInventedToken:
    async def test_a_token_the_callback_keeps_is_emitted_unchanged(self) -> None:
        """A token the callback returns as-is passes through, invented or not."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        assert (
            await _stream(decoder, ["ping <<PERSON:9>> pong"])
            == "ping <<PERSON:9>> pong"
        )


class TestFlush:
    async def test_flush_releases_an_unclosed_token_raw(self) -> None:
        """An opening delimiter that never closes is released verbatim on flush."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        assert await decoder.feed("wait <<PER") == "wait "
        assert decoder.flush() == "<<PER"

    async def test_flush_is_empty_once_the_buffer_is_drained(self) -> None:
        """After a stream that ends on a token boundary, flush yields nothing."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        await decoder.feed("<<PERSON:1>>")
        assert decoder.flush() == ""

    async def test_flush_is_idempotent(self) -> None:
        """A second flush after the buffer is emptied returns the empty string."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        await decoder.feed("done <<PERSON:1")
        assert decoder.flush() == "<<PERSON:1"
        assert decoder.flush() == ""


class TestCustomDelimiters:
    async def test_custom_delimiters_are_recognized_across_chunks(self) -> None:
        """A decoder built with other delimiters holds and rewrites their tokens."""
        mapping = {"[[PERSON:1]]": "Emma"}

        async def replace(token: str) -> str:
            return mapping.get(token, token)

        decoder = AsyncPlaceholderStreamDecoder(replace, "[[", "]]")
        assert await _stream(decoder, ["Hi [[PER", "SON:1]]"]) == "Hi Emma"

    async def test_default_delimiters_ignore_a_different_grammar(self) -> None:
        """With the default delimiters, a token in other delimiters is left as text."""
        decoder = AsyncPlaceholderStreamDecoder(_deanonymize)
        assert await _stream(decoder, ["Hi [[PERSON:1]]"]) == "Hi [[PERSON:1]]"


class TestFromFactory:
    async def test_factory_builds_a_matching_async_decoder(self) -> None:
        """A factory hands out an async decoder that recognizes its own delimiters."""
        factory = LabelCounterPlaceholderFactory("[[", "]]")

        async def replace(token: str) -> str:
            return "Emma"

        decoder = factory.async_stream_decoder(replace)
        assert await _stream(decoder, ["Hi [[PER", "SON:1]]"]) == "Hi Emma"
