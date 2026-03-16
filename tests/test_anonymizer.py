"""Unit tests for maskara.anonymizer — GLiNER2 is fully mocked."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from maskara.anonymizer import Anonymizer


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _gliner_response(**by_type: list[dict]) -> dict:
    """Build a fake GLiNER2 extract_entities return value.

    Usage::

        _gliner_response(
            person=[{"text": "Pierre", "confidence": 0.95, "start": 0, "end": 6}],
            location=[{"text": "Lyon", "confidence": 0.88, "start": 18, "end": 22}],
        )
    """
    return {"entities": by_type}


def _make_anonymizer(side_effect: list | None = None, **kwargs) -> Anonymizer:
    """Create an Anonymizer with a mocked GLiNER2 extractor."""
    extractor = MagicMock()
    if side_effect is not None:
        extractor.extract_entities.side_effect = side_effect
    return Anonymizer(extractor, **kwargs)


EMPTY = _gliner_response()


# ------------------------------------------------------------------
# _detect
# ------------------------------------------------------------------


class TestDetect:
    def test_basic_detection(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.95, "start": 0, "end": 6},
                    ]
                ),
            ]
        )
        hits = anon._detect("Pierre habite ici")
        assert hits == [("Pierre", "person")]

    def test_filters_below_min_confidence(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.3, "start": 0, "end": 6},
                        {"text": "Marie", "confidence": 0.9, "start": 10, "end": 15},
                    ]
                ),
            ],
            min_confidence=0.5,
        )
        hits = anon._detect("Pierre et Marie")
        assert hits == [("Marie", "person")]

    def test_strips_whitespace(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    location=[
                        {"text": " Lyon ", "confidence": 0.9, "start": 5, "end": 11},
                    ]
                ),
            ]
        )
        hits = anon._detect("a Lyon b")
        assert hits == [("Lyon", "location")]

    def test_ignores_empty_after_strip(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "  ", "confidence": 0.9, "start": 0, "end": 2},
                    ]
                ),
            ]
        )
        hits = anon._detect("  ")
        assert hits == []

    def test_multiple_types(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6}
                    ],
                    location=[
                        {"text": "Lyon", "confidence": 0.8, "start": 18, "end": 22}
                    ],
                ),
            ]
        )
        hits = anon._detect("Pierre habite a Lyon")
        assert ("Pierre", "person") in hits
        assert ("Lyon", "location") in hits


# ------------------------------------------------------------------
# _assign
# ------------------------------------------------------------------


class TestAssign:
    def test_first_entity_gets_index_1(self):
        anon = _make_anonymizer()
        vocab: dict[str, str] = {}
        anon._assign([("Pierre", "person")], vocab)
        assert vocab == {"Pierre": "<PERSON_1>"}

    def test_same_text_reuses_placeholder(self):
        anon = _make_anonymizer()
        vocab: dict[str, str] = {}
        anon._assign([("Pierre", "person"), ("Pierre", "person")], vocab)
        assert vocab == {"Pierre": "<PERSON_1>"}

    def test_different_text_same_type_increments(self):
        anon = _make_anonymizer()
        vocab: dict[str, str] = {}
        anon._assign([("Pierre", "person"), ("Marie", "person")], vocab)
        assert vocab == {"Pierre": "<PERSON_1>", "Marie": "<PERSON_2>"}

    def test_reuses_existing_vocab(self):
        anon = _make_anonymizer()
        vocab = {"Pierre": "<PERSON_1>"}
        anon._assign([("Pierre", "person"), ("Marie", "person")], vocab)
        assert vocab["Pierre"] == "<PERSON_1>"
        assert vocab["Marie"] == "<PERSON_2>"

    def test_multiple_types(self):
        anon = _make_anonymizer()
        vocab: dict[str, str] = {}
        anon._assign([("Pierre", "person"), ("Lyon", "location")], vocab)
        assert vocab == {"Pierre": "<PERSON_1>", "Lyon": "<LOCATION_1>"}

    def test_fills_gap_in_indices(self):
        """If index 1 is taken by another text, the new text gets index 2."""
        anon = _make_anonymizer()
        vocab = {"Pierre": "<PERSON_1>"}
        anon._assign([("Marie", "person")], vocab)
        assert vocab["Marie"] == "<PERSON_2>"


# ------------------------------------------------------------------
# _replace
# ------------------------------------------------------------------


class TestReplace:
    def test_simple_replacement(self):
        result = Anonymizer._replace("Pierre a Lyon", {"Pierre": "<P>", "Lyon": "<L>"})
        assert result == "<P> a <L>"

    def test_longest_first(self):
        """'Apple Inc.' must be replaced before 'Apple'."""
        result = Anonymizer._replace(
            "Apple Inc. and Apple",
            {"Apple Inc.": "<COMPANY_1>", "Apple": "<COMPANY_2>"},
        )
        assert result == "<COMPANY_1> and <COMPANY_2>"

    def test_replaces_all_occurrences(self):
        result = Anonymizer._replace(
            "Lyon et Lyon encore Lyon",
            {"Lyon": "<LOCATION_1>"},
        )
        assert result == "<LOCATION_1> et <LOCATION_1> encore <LOCATION_1>"

    def test_empty_mapping(self):
        assert Anonymizer._replace("hello", {}) == "hello"


# ------------------------------------------------------------------
# anonymize — full pipeline
# ------------------------------------------------------------------


class TestAnonymize:
    def test_simple(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
            ]
        )
        text, vocab = anon.anonymize("Pierre est la", thread_id="t1")
        assert text == "<PERSON_1> est la"
        assert vocab == {"Pierre": "<PERSON_1>"}

    def test_duplicate_term_in_same_message(self):
        """GLiNER detects only the first 'Lyon', but str.replace covers both."""
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    location=[
                        {"text": "Lyon", "confidence": 0.9, "start": 0, "end": 4},
                    ]
                ),
            ]
        )
        text, vocab = anon.anonymize("Lyon est a Lyon", thread_id="t1")
        assert text == "<LOCATION_1> est a <LOCATION_1>"

    def test_thread_memory_reuses_placeholder(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
            ]
        )
        anon.anonymize("Pierre", thread_id="t1")
        text2, vocab2 = anon.anonymize("Pierre revient", thread_id="t1")
        assert text2 == "<PERSON_1> revient"
        assert vocab2["Pierre"] == "<PERSON_1>"

    def test_thread_memory_new_entity_next_turn(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
                _gliner_response(
                    person=[
                        {"text": "Marie", "confidence": 0.9, "start": 0, "end": 5},
                    ]
                ),
            ]
        )
        anon.anonymize("Pierre", thread_id="t1")
        text2, vocab2 = anon.anonymize("Marie arrive", thread_id="t1")
        assert "<PERSON_2>" in text2
        assert vocab2["Pierre"] == "<PERSON_1>"
        assert vocab2["Marie"] == "<PERSON_2>"

    def test_thread_memory_old_entity_replaced_in_new_turn(self):
        """Even if GLiNER doesn't detect 'Pierre' in turn 2, the vocab still replaces it."""
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
                EMPTY,  # GLiNER detects nothing in turn 2
            ]
        )
        anon.anonymize("Pierre", thread_id="t1")
        text2, _ = anon.anonymize("Pierre est parti", thread_id="t1")
        assert text2 == "<PERSON_1> est parti"

    def test_no_thread_id_generates_uuid(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
            ]
        )
        text, vocab = anon.anonymize("Pierre")
        assert text == "<PERSON_1>"
        assert len(anon._thread_store) == 1

    def test_different_threads_are_isolated(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
                _gliner_response(
                    person=[
                        {"text": "Marie", "confidence": 0.9, "start": 0, "end": 5},
                    ]
                ),
            ]
        )
        anon.anonymize("Pierre", thread_id="t1")
        _, vocab_t2 = anon.anonymize("Marie", thread_id="t2")
        # Marie gets index 1 in t2 (no collision with Pierre from t1)
        assert vocab_t2 == {"Marie": "<PERSON_1>"}

    def test_no_entities_detected(self):
        anon = _make_anonymizer(side_effect=[EMPTY])
        text, vocab = anon.anonymize("Bonjour le monde", thread_id="t1")
        assert text == "Bonjour le monde"
        assert vocab == {}

    def test_nested_entity_longest_first(self):
        """'Apple Inc.' should not be broken by 'Apple'."""
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    company=[
                        {
                            "text": "Apple Inc.",
                            "confidence": 0.95,
                            "start": 0,
                            "end": 10,
                        },
                        {"text": "Apple", "confidence": 0.8, "start": 25, "end": 30},
                    ]
                ),
            ]
        )
        text, vocab = anon.anonymize(
            "Apple Inc. est grande. Apple aussi.", thread_id="t1"
        )
        assert vocab["Apple Inc."] == "<COMPANY_1>"
        assert vocab["Apple"] == "<COMPANY_2>"
        assert text == "<COMPANY_1> est grande. <COMPANY_2> aussi."


# ------------------------------------------------------------------
# deanonymize
# ------------------------------------------------------------------


class TestDeanonymize:
    def test_simple(self):
        anon = _make_anonymizer()
        vocab = {"Pierre": "<PERSON_1>", "Lyon": "<LOCATION_1>"}
        result = anon.deanonymize("<PERSON_1> habite a <LOCATION_1>", vocab)
        assert result == "Pierre habite a Lyon"

    def test_multiple_occurrences(self):
        anon = _make_anonymizer()
        vocab = {"Lyon": "<LOCATION_1>"}
        result = anon.deanonymize("<LOCATION_1> et <LOCATION_1>", vocab)
        assert result == "Lyon et Lyon"

    def test_llm_echoes_placeholder(self):
        """The LLM response contains placeholders — deanonymize restores them."""
        anon = _make_anonymizer()
        vocab = {"Pierre": "<PERSON_1>", "Lyon": "<LOCATION_1>"}
        llm_response = (
            "<PERSON_1> est bien installe a <LOCATION_1>. <PERSON_1> aime <LOCATION_1>."
        )
        result = anon.deanonymize(llm_response, vocab)
        assert result == "Pierre est bien installe a Lyon. Pierre aime Lyon."

    def test_roundtrip(self):
        """anonymize → deanonymize should restore original text."""
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6}
                    ],
                    location=[
                        {"text": "Lyon", "confidence": 0.9, "start": 18, "end": 22}
                    ],
                ),
            ]
        )
        original = "Pierre habite a Lyon"
        anon_text, vocab = anon.anonymize(original, thread_id="t1")
        assert anon.deanonymize(anon_text, vocab) == original

    def test_empty_vocab(self):
        anon = _make_anonymizer()
        assert anon.deanonymize("hello", {}) == "hello"


# ------------------------------------------------------------------
# anonymize_messages / deanonymize_messages
# ------------------------------------------------------------------


class TestMessages:
    def test_anonymize_messages(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
                _gliner_response(
                    location=[
                        {"text": "Lyon", "confidence": 0.9, "start": 10, "end": 14},
                    ]
                ),
            ]
        )
        msgs = [
            HumanMessage(content="Pierre est la"),
            HumanMessage(content="Il est a Lyon"),
        ]
        anon_msgs, vocab = anon.anonymize_messages(msgs, thread_id="t1")
        assert anon_msgs[0].content == "<PERSON_1> est la"
        assert anon_msgs[1].content == "Il est a <LOCATION_1>"
        assert "Pierre" in vocab
        assert "Lyon" in vocab

    def test_deanonymize_messages_via_thread_id(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6},
                    ]
                ),
            ]
        )
        anon.anonymize("Pierre", thread_id="t1")

        msgs = [AIMessage(content="<PERSON_1> est la")]
        restored = anon.deanonymize_messages(msgs, thread_id="t1")
        assert restored[0].content == "Pierre est la"

    def test_deanonymize_messages_via_explicit_placeholders(self):
        anon = _make_anonymizer()
        vocab = {"Pierre": "<PERSON_1>"}
        msgs = [AIMessage(content="<PERSON_1> est la")]
        restored = anon.deanonymize_messages(msgs, placeholders=vocab)
        assert restored[0].content == "Pierre est la"

    def test_deanonymize_messages_no_vocab_no_change(self):
        anon = _make_anonymizer()
        msgs = [AIMessage(content="<PERSON_1> est la")]
        restored = anon.deanonymize_messages(msgs)
        assert restored[0].content == "<PERSON_1> est la"

    def test_messages_roundtrip(self):
        anon = _make_anonymizer(
            side_effect=[
                _gliner_response(
                    person=[
                        {"text": "Pierre", "confidence": 0.9, "start": 0, "end": 6}
                    ],
                    location=[
                        {"text": "Lyon", "confidence": 0.9, "start": 18, "end": 22}
                    ],
                ),
            ]
        )
        original_content = "Pierre habite a Lyon"
        msgs = [HumanMessage(content=original_content)]
        anon_msgs, vocab = anon.anonymize_messages(msgs, thread_id="t1")
        restored = anon.deanonymize_messages(anon_msgs, placeholders=vocab)
        assert restored[0].content == original_content
