from piighost.config import export_schema


def test_export_schema_returns_a_dict():
    schema = export_schema()
    assert isinstance(schema, dict)


def test_export_schema_has_top_level_properties():
    schema = export_schema()
    assert "properties" in schema
    assert "detectors" in schema["properties"]
    assert "anonymizer" in schema["properties"]


def test_export_schema_contains_all_detector_discriminator_tags():
    schema = export_schema()
    # The schema serialization is non-trivial. We assert that every concrete
    # detector type appears somewhere in the rendered JSON Schema.
    import json
    blob = json.dumps(schema)
    for type_name in (
        "regex", "gliner2", "spacy", "transformers", "llm", "chunked",
    ):
        assert f'"const": "{type_name}"' in blob or f'"{type_name}"' in blob


def test_export_schema_contains_all_placeholder_discriminator_tags():
    import json
    blob = json.dumps(export_schema())
    for type_name in (
        "label_counter", "label_hash", "label", "mask",
        "redact_counter", "redact_hash", "redact",
        "faker_counter", "faker_hash", "faker",
    ):
        assert f'"const": "{type_name}"' in blob or f'"{type_name}"' in blob
