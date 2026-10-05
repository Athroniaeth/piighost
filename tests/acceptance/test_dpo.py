"""Acceptance tests of the compliance officer's stories, through public entry points.

Each test carries the id of the acceptance test it implements, AT-<story>-<n>,
the same in every language of the documentation. The catalog is faked: each
reference answers with patterns copied from the group it names.
"""

from pathlib import Path

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.config import load_pipeline
from piighost.pipeline import ThreadAnonymizationPipeline

SECRETS = "catalog:piighost/logs:b635d867"
"""The catalog group of secrets and machine identifiers."""

PAYMENT = "catalog:piighost/payment:b1b1cd64"
"""A catalog group carrying the IBAN."""

GENERIC = "catalog:piighost/generic:fab51b33"
"""A catalog group carrying the email address."""

CATALOG = {
    SECRETS: {
        "OPENAI_API_KEY": r"(?<![A-Za-z0-9])sk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{20,}",
        "AWS_ACCESS_KEY": r"\bAKIA[0-9A-Z]{16}\b",
    },
    PAYMENT: {"IBAN": r"\bFR\d{2}(?: ?\d{4}){5} ?\d{3}\b"},
    GENERIC: {"EMAIL": r"[\w.+-]+@[\w-]+\.[\w.]+"},
}
"""What the fake catalog answers, the secret patterns copied from the real group."""

OPENAI_KEY = "sk-proj-Ab3dEf6hIj9kLm2nOp5qRs8t"
"""A key shaped like an OpenAI project key, issued by nobody."""

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
"""The access key AWS documents as an example."""

IBAN = "FR76 3000 6000 0112 3456 7890 189"
"""A French IBAN, spaced as people write it."""


@pytest.fixture(autouse=True)
def fake_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every catalog pull from CATALOG, so no test reaches the network."""
    monkeypatch.setattr("piighost.config.models.detector.pull", CATALOG.__getitem__)


def _config(tmp_path: Path, *catalogs: str) -> str:
    """Write a regex config pulling the catalogs and return its path."""
    path = tmp_path / "pipeline.toml"
    listed = ", ".join(f'"{catalog}"' for catalog in catalogs)
    path.write_text(f'[detector]\ntype = "regex"\ncatalogs = [{listed}]\n')
    return str(path)


class TestSecretsLeaveAsTokens:
    @pytest.mark.parametrize(
        ("secret", "token"),
        [(OPENAI_KEY, "<<OPENAI_API_KEY:1>>"), (AWS_KEY, "<<AWS_ACCESS_KEY:1>>")],
    )
    async def test_an_api_key_leaves_as_a_token(
        self, tmp_path: Path, secret: str, token: str
    ) -> None:
        """A key in a message reaches the LLM as a token of its label (AT-DPO-1-2)."""
        pipeline = load_pipeline(_config(tmp_path, SECRETS))
        result = await pipeline.anonymize(f"Mon déploiement plante avec {secret}.")
        assert result.text == f"Mon déploiement plante avec {token}."


class TestChosenGroups:
    async def test_a_removed_group_leaves_its_values_clear(
        self, tmp_path: Path
    ) -> None:
        """Without the group carrying the IBAN, the IBAN stays clear (AT-DPO-2-2)."""
        text = f"Virement sur {IBAN}, confirmation à jean@exemple.fr"
        both = load_pipeline(_config(tmp_path, GENERIC, PAYMENT))
        generic_only = load_pipeline(_config(tmp_path, GENERIC))

        assert (await both.anonymize(text)).text == (
            "Virement sur <<IBAN:1>>, confirmation à <<EMAIL:1>>"
        )
        assert (await generic_only.anonymize(text)).text == (
            f"Virement sur {IBAN}, confirmation à <<EMAIL:1>>"
        )


class TestErasure:
    async def test_a_forgotten_thread_restores_nothing(self) -> None:
        """After forget_thread, a token of that thread comes back as it is (AT-DPO-6-1)."""
        pipeline = ThreadAnonymizationPipeline(ExactMatchDetector({"Emma": "PERSON"}))
        await pipeline.anonymize("Hi Emma", "t1")
        assert await pipeline.deanonymize("Bye <<PERSON:1>>", "t1") == "Bye Emma"

        await pipeline.forget_thread("t1")

        assert (
            await pipeline.deanonymize("Bye <<PERSON:1>>", "t1") == "Bye <<PERSON:1>>"
        )
