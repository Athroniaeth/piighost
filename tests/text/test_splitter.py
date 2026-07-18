"""Tests for the RecursiveCharacterTextSplitter and its Chunk."""

import pytest

from piighost.models import Chunk
from piighost.text import AnySplitter, RecursiveCharacterTextSplitter


class TestConformance:
    def test_recursive_splitter_satisfies_the_port(self) -> None:
        """RecursiveCharacterTextSplitter is an AnySplitter."""
        assert isinstance(RecursiveCharacterTextSplitter(), AnySplitter)


class TestChunk:
    def test_end_is_start_plus_length(self) -> None:
        """end is the start offset plus the text length."""
        assert Chunk(text="Emma", start=3).end == 7


class TestConstruction:
    def test_non_positive_chunk_size_raises(self) -> None:
        """A non-positive chunk_size raises ValueError."""
        with pytest.raises(ValueError):
            RecursiveCharacterTextSplitter(chunk_size=0)

    def test_overlap_not_smaller_than_size_raises(self) -> None:
        """An overlap not smaller than chunk_size raises ValueError."""
        with pytest.raises(ValueError):
            RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=10)


class TestSplit:
    def test_short_text_is_a_single_chunk(self) -> None:
        """Text shorter than chunk_size yields one chunk from offset zero."""
        chunks = RecursiveCharacterTextSplitter().split("Hi Emma")
        assert chunks == [Chunk(text="Hi Emma", start=0)]

    def test_empty_text_yields_no_chunk(self) -> None:
        """Empty text yields no chunk."""
        assert RecursiveCharacterTextSplitter().split("") == []

    def test_packs_words_with_overlap(self) -> None:
        """Words pack up to chunk_size with overlap between chunks."""
        splitter = RecursiveCharacterTextSplitter(chunk_size=7, chunk_overlap=3)
        chunks = splitter.split("aaa bbb ccc ddd")
        assert [(chunk.text, chunk.start) for chunk in chunks] == [
            ("aaa bbb", 0),
            ("bbb ccc", 4),
            ("ccc ddd", 8),
        ]

    def test_prefers_the_paragraph_boundary(self) -> None:
        """A paragraph separator is preferred over splitting mid word."""
        splitter = RecursiveCharacterTextSplitter(chunk_size=15, chunk_overlap=3)
        chunks = splitter.split("Hello world\n\nBonjour monde")
        assert [chunk.text for chunk in chunks] == ["Hello world", "Bonjour monde"]

    def test_chunk_text_matches_its_offsets(self) -> None:
        """Every chunk text equals the original slice at its offsets."""
        text = "aaa bbb ccc ddd eee fff"
        splitter = RecursiveCharacterTextSplitter(chunk_size=7, chunk_overlap=3)
        for chunk in splitter.split(text):
            assert text[chunk.start : chunk.end] == chunk.text

    def test_no_chunk_exceeds_chunk_size(self) -> None:
        """No chunk is longer than chunk_size for splittable text."""
        text = "aaa bbb ccc ddd eee fff ggg"
        splitter = RecursiveCharacterTextSplitter(chunk_size=7, chunk_overlap=3)
        for chunk in splitter.split(text):
            assert len(chunk.text) <= 7

    def test_a_value_survives_intact_in_some_chunk(self) -> None:
        """A short value in the text appears whole in at least one chunk."""
        text = "lorem ipsum Emma dolor sit amet consectetur"
        splitter = RecursiveCharacterTextSplitter(chunk_size=12, chunk_overlap=6)
        chunks = splitter.split(text)
        assert any("Emma" in chunk.text for chunk in chunks)
