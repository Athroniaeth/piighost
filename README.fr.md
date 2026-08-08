# PIIGhost

[![CI](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml/badge.svg)](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/piighost.svg)](https://pypi.org/project/piighost/)
[![Python versions](https://img.shields.io/pypi/pyversions/piighost.svg)](https://pypi.org/project/piighost/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

[README EN](README.md) - [README FR](README.fr.md) / [Documentation EN](https://athroniaeth.github.io/piighost/) - [Documentation FR](https://athroniaeth.github.io/piighost/fr/)

`piighost` est une librairie Python qui empêche les PII (données personnelles identifiables) d'atteindre un modèle de langage, tout en gardant l'application pleinement fonctionnelle.

Cette librairie repère les PII grâce à des détecteurs (regex, NER, ou un autre LLM) et remplace chaque valeur par un placeholder stable, par exemple `john.doe@example.com` devient `<<EMAIL:1>>`. Le modèle ne travaille donc que sur du texte dé-identifié. Quand le LLM retourne des placeholders, `piighost` réinjecte les vraies valeurs à leur place, l'utilisateur final voit `john.doe@example.com` et n'a jamais conscience de la dé-identification. La même mécanique protège les agents outillés. Un outil qui a besoin de la vraie adresse la reçoit en clair, alors que le LLM qui décide de l'appeler ne voit toujours que `<<EMAIL:1>>`.

Enfin, cette librairie garde la correspondance entre la valeur et son placeholder tout au long de la conversation. Si `john.doe@example.com` réapparaît trois messages plus tard, le placeholder reste `<<EMAIL:1>>`, ce qui permet au modèle de suivre le fil de discussion.

> [!NOTE]
> `piighost` fait de la **dé-identification réversible**. Comme la correspondance entre une valeur et son placeholder est conservée pour pouvoir restaurer les données, il s'agit d'une pseudonymisation au sens du RGPD, pas d'une anonymisation définitive. Les valeurs réelles restent stockées le temps de la conversation et doivent être protégées en conséquence.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/deid-chat-fr-dark.gif">
    <img alt="Un utilisateur discute avec un agent : les valeurs PII sont remplacées par des placeholders avant d'atteindre le modèle puis restaurées pour l'utilisateur et pour les appels d'outils." src="docs/assets/deid-chat-fr-light.gif" width="760">
  </picture>
</p>

*Le LLM ne voit que des placeholders. L'outil reçoit la vraie adresse, l'utilisateur reçoit une réponse en clair, et le code de l'agent ne change pas.*

## Démarrage rapide

```bash
uv add piighost
```

### Dé-identifier un texte

`ExactMatchDetector` dé-identifie un dictionnaire de valeurs connues sans télécharger de modèle.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "john.doe@example.com": "EMAIL"})
pipeline = AnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)

result = asyncio.run(pipeline.anonymize("Écris à John Doe à john.doe@example.com."))
print(result.text)  # Écris à <<PERSON:1>> à <<EMAIL:1>>.
```

### Conversations et agents (LangChain)

Le middleware enrobe un pipeline conversationnel et gère chaque tour d'agent. Le LLM ne voit que des placeholders, les outils reçoivent les vraies valeurs, l'utilisateur reçoit une réponse en clair.

```bash
uv add 'piighost[middleware]'
```

```python
from langchain.agents import create_agent
from piighost.integrations.middleware import PIIAnonymizationMiddleware

# pipeline : un ThreadAnonymizationPipeline, voir le guide conversationnel
agent = create_agent(
    model="openai:gpt-5.4",
    tools=[send_email],
    middleware=[PIIAnonymizationMiddleware(pipeline=pipeline)],
)
```

Pour un vrai détecteur, le pipeline conversationnel et un exemple LangChain complet, voir le [Quickstart](https://athroniaeth.github.io/piighost/fr/getting-started/quickstart/) et l'[intégration LangChain](https://athroniaeth.github.io/piighost/fr/examples/langchain/).

## Documentation

- **Démarrer** : [installation](https://athroniaeth.github.io/piighost/fr/getting-started/installation/), [quickstart](https://athroniaeth.github.io/piighost/fr/getting-started/quickstart/), [premier pipeline](https://athroniaeth.github.io/piighost/fr/getting-started/first-pipeline/)
- **Recettes** : [usage basique](https://athroniaeth.github.io/piighost/fr/examples/basic/), [intégration LangChain](https://athroniaeth.github.io/piighost/fr/examples/langchain/), [détecteurs prêts à l'emploi](https://athroniaeth.github.io/piighost/fr/examples/detectors/)
- **Référence** : [pipeline](https://athroniaeth.github.io/piighost/fr/reference/pipeline/), [middleware](https://athroniaeth.github.io/piighost/fr/reference/middleware/), [détecteurs](https://athroniaeth.github.io/piighost/fr/reference/detectors/), [CLI](https://athroniaeth.github.io/piighost/fr/reference/cli/)
- **Concepts** : [pourquoi dé-identifier](https://athroniaeth.github.io/piighost/fr/why-anonymize/), [architecture](https://athroniaeth.github.io/piighost/fr/architecture/), [placeholder factories](https://athroniaeth.github.io/piighost/fr/placeholder-factories/), [sécurité](https://athroniaeth.github.io/piighost/fr/security/)

## Projet

- **Contribuer** : [guide de contribution](https://athroniaeth.github.io/piighost/fr/community/contributing/) et [signaler un bug](https://athroniaeth.github.io/piighost/fr/community/bug-reports/)
- **Écosystème** :
    - [piighost.athroniaeth.cloud](https://piighost.athroniaeth.cloud) : site de présentation
    - [piighost-api](https://github.com/Athroniaeth/piighost-api) : API d'inférence piighost
    - [piighost-chat](https://github.com/Athroniaeth/piighost-chat) : exemple d'interface avec HITL
- **Licence** : [MIT](LICENSE)
