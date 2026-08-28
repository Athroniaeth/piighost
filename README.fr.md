# PIIGhost

[![CI](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml/badge.svg)](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Athroniaeth/piighost/branch/master/graph/badge.svg)](https://codecov.io/gh/Athroniaeth/piighost)
[![PyPI version](https://img.shields.io/pypi/v/piighost.svg)](https://pypi.org/project/piighost/)
[![Python versions](https://img.shields.io/pypi/pyversions/piighost.svg)](https://pypi.org/project/piighost/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Discord](https://img.shields.io/badge/Discord-rejoindre-5865F2?logo=discord&logoColor=white)](https://discord.gg/vFg9GHQR2s)

`piighost` est une librairie Python qui empêche les PII (données personnelles identifiables) d'atteindre un modèle de langage, sans jamais gêner ce que votre application doit en faire.

Elle repère les PII grâce à des détecteurs (regex, NER, ou un autre LLM) et remplace chaque valeur par un placeholder stable, si bien que `john.doe@example.com` devient `<<EMAIL:1>>` et que le modèle ne travaille que sur du texte dé-identifié. Quand le LLM répond avec ces placeholders, `piighost` réinjecte les vraies valeurs, et l'utilisateur final lit `john.doe@example.com` sans se rendre compte de rien. Les agents outillés ont droit au même traitement. Un outil qui a réellement besoin de la vraie adresse la reçoit en clair, alors que le LLM qui a décidé de l'appeler ne voit toujours que `<<EMAIL:1>>`.

La correspondance entre une valeur et son placeholder tient aussi sur toute la conversation. Si `john.doe@example.com` revient trois messages plus tard, il reste `<<EMAIL:1>>`, ce qui permet au modèle de suivre le fil.

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

- **Détecteurs enfichables :** catalogues regex (generic, US, EU, FR), NER avec GLiNER2, spaCy ou Transformers, et un détecteur LLM, plus les détecteurs exact-match, composite et chunked (le chunking découpe les longs textes qui dépassent la fenêtre de contexte d'un modèle).
- **Placeholders réversibles et sans collision :** des jetons opaques comme `<<PERSON:1>>`, plus des factories label-only, masque, et hash à clé, tous stables sur toute une conversation.
- **Intégrations agents :** middleware LangChain, hooks Pydantic AI, et LlamaIndex, avec la dé-identification juste à la frontière des outils et une restauration en streaming token par token.
- **Mémoire de conversation :** backends in-process, Redis, ou SQLAlchemy. Le backend Redis peut chiffrer les valeurs au repos (AES-GCM) et hacher les clés (Argon2id).
- **Guard rail :** revérifie la sortie du modèle pour toute PII passée entre les mailles et la refuse, avec un détecteur, un LLM, ou la modération Mistral.
- **Configuration TOML/JSON :** construit tout un pipeline depuis un seul fichier, avec un CLI pour le valider et afficher son schéma.
- **Client HTTP et tracing OpenTelemetry :** un client async pour le compagnon `piighost-api`, et des spans par étape visibles dans n'importe quel backend OpenTelemetry comme Langfuse ou Jaeger, avec rédaction optionnelle des payloads.
- **Typé et léger en dépendances :** fournit `py.typed` et un cœur minimal, avec tout le lourd rangé derrière des extras optionnels.

## Pourquoi PIIGhost

La plupart des outils PII s'arrêtent à la détection. Presidio, GLiNER, spaCy et les catalogues regex repèrent très bien les entités dans un texte. Le difficile, pour un agent LLM, c'est tout ce qui vient après. Remplacer les valeurs sans casser le raisonnement du modèle, garder une valeur associée à un seul token sur toute une conversation, donner la vraie valeur aux outils pendant que le modèle ne voit que le token, et réinjecter les originaux dans la réponse. Cette orchestration, c'est PIIGhost.

**Ce que PIIGhost ajoute par-dessus :**

- **Détecteurs enfichables :** composez des catalogues regex, du NER (GLiNER2, spaCy, Transformers), et un détecteur LLM, et gardez celui que vous connaissez déjà (Presidio se branche via un extra).
- **Jetons réversibles :** chaque valeur devient un id stable comme `<<PERSON:1>>`, adossé à un cache plutôt qu'à du chiffrement embarqué dans le jeton.
- **Restauration transparente :** la vraie valeur est réinjectée automatiquement, donc l'utilisateur final lit `john.doe@example.com` et ne voit jamais de jeton.
- **Cohérent sur toute une conversation :** la même valeur garde le même token sur tout le thread, donc le modèle sait qui est qui.
- **Frontière d'outils :** l'outil reçoit la vraie valeur pendant que le modèle ne voit que le jeton.
- **Restauration en streaming :** les réponses sont restaurées token par token au fil du flux.
- **Un pipeline en étapes personnalisable :** détection, liaison, résolution des chevauchements, expansion, anonymisation, et un guard rail optionnel, pour brancher un appariement fuzzy tolérant aux fautes ou ajouter votre propre étape.
- **Périmètre, texte et conversations en direct :** PIIGhost protège une conversation en cours, message par message, pas un dataset figé.
- **Auto-hébergé :** tourne dans votre process, ou comme service via le compagnon [piighost-api](https://github.com/Athroniaeth/piighost-api), qui construit tout son pipeline depuis un fichier de config.

Pour voir comment il se situe face à Presidio, LangChain, les API cloud et d'autres, voir [Comment PIIGhost se compare](https://athroniaeth.github.io/piighost/fr/comparison/).

### Limites et partis pris

- **Le jeton n'embarque pas la valeur chiffrée, par choix.** Contrairement à un jeton à chiffrement à format préservé (où le chiffré *est* le jeton, ex. Google DLP), PIIGhost utilise un id (`<<PERSON:1>>`) adossé à un cache. La raison : un jeton qui contient le chiffré peut être capté aujourd'hui et cassé dans 20 ans (« harvest now, decrypt later », la menace de l'informatique quantique sur le chiffrement classique), alors qu'un id ne révèle rien en soi. En retour, il faut un cache pour garder la correspondance jeton-valeur, donc une mémoire à déployer, partager entre workers et persister en production.
- **Ce cache stocke les vraies valeurs, donc la réversibilité est de la pseudonymisation, pas de l'anonymisation (RGPD).** Les données réelles restent stockées le temps de la conversation. La lib fournit de quoi les protéger (chiffrement AES-GCM des valeurs, hachage Argon2id des clés), mais l'architecture de base de données elle-même doit être sécurisée en production dès qu'on utilise Redis ou PostgreSQL.
- **Pas d'anonymisation de dataset.** Ni k-anonymity, ni l-diversité, ni differential privacy, ni données tabulaires. PIIGhost protège du texte et des conversations en direct, pas un jeu de données entier. Pour ça, voir ARX, Amnesia, ou Google DLP.
- **Pas de validation par checksum (Luhn / IBAN / NIR), par choix.** Le `RegexDetector` matche sur la forme seule pour ne jamais laisser fuiter une valeur réelle abîmée par l'OCR (un checksum la rejetterait et elle passerait en clair). En échange, il repère parfois une chaîne qui a la forme d'une PII sans en être une, ce qui ne coûte qu'un jeton de trop.

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

Le middleware enrobe un pipeline conversationnel et gère chaque tour d'agent pour vous, si bien que la même dé-identification s'applique sans rien changer à la logique de votre agent.

```bash
pip install 'piighost[langchain]'   # or: uv add 'piighost[langchain]'
```

```python
import asyncio

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
    # This example calls OpenAI, so set OPENAI_API_KEY in your environment first.
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

C'est l'intégration **LangChain**, mais ce n'est qu'une option parmi d'autres. `piighost` propose aussi des connecteurs pour [Pydantic AI](https://athroniaeth.github.io/piighost/fr/examples/pydantic-ai/) et [LlamaIndex](https://athroniaeth.github.io/piighost/fr/examples/llama-index/), et le serveur compagnon [piighost-api](https://github.com/Athroniaeth/piighost-api) expose des proxys compatibles OpenAI et Anthropic pour déplacer la dé-identification à la frontière HTTP en changeant seulement l'URL de base.

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
