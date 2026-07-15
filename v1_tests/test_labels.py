"""Tests for piighost.labels public constants."""

from piighost import labels


class TestLabelValues:
    def test_values_match_expected_strings(self) -> None:
        assert labels.PERSON == "PERSON"
        assert labels.LOCATION == "LOCATION"
        assert labels.ORGANIZATION == "ORGANIZATION"
        assert labels.EMAIL == "EMAIL"
        assert labels.PHONE == "PHONE"
        assert labels.DATE == "DATE"
        assert labels.ADDRESS == "ADDRESS"
        assert labels.IBAN == "IBAN"
        assert labels.CREDIT_CARD == "CREDIT_CARD"
        assert labels.IP_ADDRESS == "IP_ADDRESS"
        assert labels.URL == "URL"
        assert labels.API_KEY == "API_KEY"


class TestExports:
    def test_all_contains_every_constant(self) -> None:
        expected = {
            "ADDRESS",
            "API_KEY",
            "CREDIT_CARD",
            "CommonLabel",
            "DATE",
            "EMAIL",
            "IBAN",
            "IP_ADDRESS",
            "LOCATION",
            "ORGANIZATION",
            "PERSON",
            "PHONE",
            "URL",
        }
        assert set(labels.__all__) == expected

    def test_labels_module_reexported_from_package(self) -> None:
        import piighost

        assert piighost.labels is labels
