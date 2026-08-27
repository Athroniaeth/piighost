# PIIGhost

[![CI](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml/badge.svg)](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/piighost.svg)](https://pypi.org/project/piighost/)
[![Python versions](https://img.shields.io/pypi/pyversions/piighost.svg)](https://pypi.org/project/piighost/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Discord](https://img.shields.io/badge/Discord-rejoindre-5865F2?logo=discord&logoColor=white)](https://discord.gg/vFg9GHQR2s)

`piighost` est une librairie Python qui empêche les PII (données personnelles identifiables) d'atteindre un modèle de langage, tout en gardant l'application pleinement fonctionnelle.

Cette librairie repère les PII grâce à des détecteurs (regex, NER, ou un autre LLM) et remplace chaque valeur par un placeholder stable, par exemple `john.doe@example.com` devient `<<EMAIL:1>>`. Le modèle ne travaille donc que sur du texte dé-identifié. Quand le LLM retourne des placeholders, `piighost` réinjecte les vraies valeurs à leur place, l'utilisateur final voit `john.doe@example.com` et n'a jamais conscience de la dé-identification. La même mécanique protège les agents outillés. Un outil qui a besoin de la vraie adresse la reçoit en clair, alors que le LLM qui décide de l'appeler ne voit toujours que `<<EMAIL:1>>`.

Enfin, cette librairie garde la correspondance entre la valeur et son placeholder tout au long de la conversation. Si `john.doe@example.com` réapparaît trois messages plus tard, le placeholder reste `<<EMAIL:1>>`, ce qui permet au modèle de suivre le fil de discussion.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/deid-chat-fr-dark.gif">
    <img alt="Un utilisateur discute avec un agent : les valeurs PII sont remplacées par des placeholders avant d'atteindre le modèle puis restaurées pour l'utilisateur et pour les appels d'outils." src="docs/assets/deid-chat-fr-light.gif" width="760">
  </picture>
</p>

*Le LLM ne voit que des placeholders. L'outil reçoit la vraie adresse, l'utilisateur reçoit une réponse en clair, et le code de l'agent ne change pas.*

> [!NOTE]
> `piighost` fait de la **dé-identification réversible**. Comme la correspondance entre une valeur et son placeholder est conservée pour pouvoir restaurer les données, il s'agit d'une pseudonymisation au sens du RGPD, pas d'une anonymisation définitive. Les valeurs réelles restent stockées le temps de la conversation et doivent être protégées en conséquence.

## Fonctionnalités

- **Détecteurs enfichables** — catalogues regex (generic, US, EU, FR), NER (GLiNER2, spaCy, Transformers), un détecteur LLM, plus exact-match, composite et chunked.
- **Placeholders réversibles et sans collision** — jetons opaques (`<<PERSON:1>>`), plus des factories label-only, masque, et hash à clé, stables sur toute une conversation.
- **Intégrations agents** — middleware LangChain, hooks Pydantic AI, et LlamaIndex, avec dé-identification à la frontière des outils et restauration en streaming token par token.
- **Mémoire de conversation** — backends in-process, Redis, ou SQLAlchemy ; le backend Redis peut chiffrer les valeurs au repos (AES-GCM) et hacher les clés (Argon2id).
- **Guard rail** — revérifie la sortie du modèle pour des PII résiduelles et la refuse (un détecteur, un LLM, ou une modération via Mistral).
- **Configuration TOML/JSON** — construit un pipeline complet depuis un fichier, avec un CLI pour le valider et émettre son schéma.
- **Client HTTP et tracing OpenTelemetry** — un client async pour `piighost-api`, et des spans par étape avec rédaction optionnelle des payloads.
- **Typé et léger en dépendances** — fournit `py.typed`, un cœur minimal, tout le lourd derrière des extras optionnels.

## Pourquoi PIIGhost

- **vs. regex ou scrubbing simple** — la regex seule rate les noms et décale les frontières, et supprimer ou masquer les PII brise le raisonnement du modèle. PIIGhost garde le texte cohérent avec des placeholders stables et réversibles, et restaure les vraies valeurs pour l'utilisateur et les outils.
- **vs. faux à la Faker** — un vivier fini de faux collisionne et peut coïncider avec une vraie valeur, donc il n'est pas restaurable de façon fiable. PIIGhost utilise plutôt des jetons synthétiques sans collision. Si vous dépendez déjà de Presidio, il est disponible comme détecteur via l'extra `presidio`.
- **vs. anonymisation analytique (k-anonymity, differential privacy)** — celles-ci protègent un jeu de données entier en le transformant. PIIGhost protège une conversation en direct, message par message, et la restaure, donc votre agent continue de travailler sur les vraies données en coulisses.

Pensé pour les agents LLM : le modèle ne voit que des placeholders, tandis que les outils et l'utilisateur final voient les vraies valeurs.

## Démarrage rapide

```bash
pip install piighost   # or: uv add piighost
```

### Dé-identifier un texte

`ExactMatchDetector` dé-identifie un dictionnaire de valeurs connues sans télécharger de modèle.

```python
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "john.doe@example.com": "EMAIL"})
pipeline = AnonymizationPipeline(detector)

result = asyncio.run(pipeline.anonymize("Écris à John Doe à john.doe@example.com."))
print(result.text)  # Écris à <<PERSON:1>> à <<EMAIL:1>>.
```

### Conversations et agents (LangChain)

Le middleware enrobe un pipeline conversationnel et gère chaque tour d'agent. Le LLM ne voit que des placeholders, les outils reçoivent les vraies valeurs, l'utilisateur reçoit une réponse en clair.

```bash
pip install 'piighost[langchain]'   # or: uv add 'piighost[langchain]'
```

```python
import asyncio

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline

SYSTEM_PROMPT = (
    "Some inputs contain placeholders like <<PERSON:1>> that stand in for real "
    "values withheld for privacy. Treat each placeholder as the real value, never "
    "comment on its format, and pass it to tools unchanged."
)


@tool
def send_mail(to: str, body: str) -> str:
    """Send an email to `to` with the given body."""
    print(f"[tool] send_mail received to={to!r}")
    return "Email successfully sent."


async def main() -> None:
    load_dotenv()

    labels = {"Patrick Dupont": "PERSON", "patrick@acme.com": "EMAIL"}
    detector = ExactMatchDetector(labels)
    pipeline = ThreadAnonymizationPipeline(detector)
    middleware = PIIAnonymizationMiddleware(pipeline)
    # gpt-5.6-terra is a reasoning model; reasoning_effort="none" lets it call
    # function tools over chat/completions.
    model = init_chat_model("openai:gpt-5.6-terra", reasoning_effort="none")
    # The system prompt tells the model to treat placeholders as real values and
    # pass them to tools unchanged, so it does not balk at the tokens.
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[send_mail],
        middleware=[middleware],
    )
    config = {"configurable": {"thread_id": "demo-thread"}}

    message = HumanMessage(
        "Use the send_mail tool to send a welcome note to Patrick Dupont at patrick@acme.com."
    )
    result = await agent.ainvoke({"messages": [message]}, config=config)
    print(f"user sees: {result['messages'][-1].content!r}")


if __name__ == "__main__":
    asyncio.run(main())
```

C'est l'intégration **LangChain**, mais ce n'est qu'une option parmi d'autres. `piighost` propose aussi des connecteurs pour [Pydantic AI](https://athroniaeth.github.io/piighost/fr/examples/pydantic-ai/) et [LlamaIndex](https://athroniaeth.github.io/piighost/fr/examples/llama-index/), et le serveur compagnon [piighost-api](https://github.com/Athroniaeth/piighost-api) expose un proxy compatible OpenAI pour déplacer la dé-identification à la frontière HTTP en changeant seulement le `base_url`.

Pour un vrai détecteur et le pipeline conversationnel, voir le [Quickstart](https://athroniaeth.github.io/piighost/fr/getting-started/quickstart/) et l'[intégration LangChain](https://athroniaeth.github.io/piighost/fr/examples/langchain/).

## Documentation

**[Documentation complète](https://athroniaeth.github.io/piighost/fr/)**

- **Démarrer**
    - [installation](https://athroniaeth.github.io/piighost/fr/getting-started/installation/)
    - [quickstart](https://athroniaeth.github.io/piighost/fr/getting-started/quickstart/)
    - [premier pipeline](https://athroniaeth.github.io/piighost/fr/getting-started/first-pipeline/)
- **Recettes**
    - [usage basique](https://athroniaeth.github.io/piighost/fr/examples/basic/)
    - [intégration LangChain](https://athroniaeth.github.io/piighost/fr/examples/langchain/)
    - [intégration Pydantic AI](https://athroniaeth.github.io/piighost/fr/examples/pydantic-ai/)
    - [détecteurs prêts à l'emploi](https://athroniaeth.github.io/piighost/fr/examples/detectors/)
- **Référence**
    - [pipeline](https://athroniaeth.github.io/piighost/fr/reference/pipeline/)
    - [middleware](https://athroniaeth.github.io/piighost/fr/reference/middleware/)
    - [détecteurs](https://athroniaeth.github.io/piighost/fr/reference/detectors/)
    - [CLI](https://athroniaeth.github.io/piighost/fr/reference/cli/)
- **Concepts**
    - [pourquoi dé-identifier](https://athroniaeth.github.io/piighost/fr/why-anonymize/)
    - [architecture](https://athroniaeth.github.io/piighost/fr/architecture/)
    - [placeholder factories](https://athroniaeth.github.io/piighost/fr/placeholder-factories/)
    - [sécurité](https://athroniaeth.github.io/piighost/fr/security/)

## Projet

- **Communauté** : [Discord](https://discord.gg/vFg9GHQR2s) pour obtenir de l'aide, signaler des bugs, proposer des fonctionnalités et échanger sur la dé-identification
- **Contribuer** : [guide de contribution](https://athroniaeth.github.io/piighost/fr/community/contributing/) et [signaler un bug](https://athroniaeth.github.io/piighost/fr/community/bug-reports/)
- **Écosystème** :
    - **[Site de présentation](https://piighost.athroniaeth.cloud)** : une vue d'ensemble du projet
    - **[piighost-api](https://github.com/Athroniaeth/piighost-api)** : le serveur d'API d'inférence
    - **[piighost-chat](https://github.com/Athroniaeth/piighost-chat)** : un exemple d'interface de chat avec HITL
- **Licence** : [MIT](LICENSE)
