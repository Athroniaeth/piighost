---
icon: lucide/shield-check
tags:
  - Guard
---

# Référence des garde-fous

Module : `piighost.components.guard`

Un garde-fou est le dernier étage, optionnel, du pipeline. Il revérifie le texte anonymisé pour des PII résiduelles et, s'il en trouve, fait lever `PIIRemainingError` au pipeline plutôt que de renvoyer une fuite. Chaque garde-fou satisfait le port `AnyGuardRail`, un `async def check(self, text: str) -> GuardVerdict`, et renvoie un `GuardVerdict` indiquant si des PII semblent subsister et comment il le sait. Contrairement aux autres étages, les garde-fous ne partagent aucun template `Base*` : ils diffèrent par tout leur mécanisme de vérification, réexécuter un détecteur local ou appeler une API externe, il n'y a donc pas de squelette commun.

Le garde-fou classifie, il ne décide pas. Il rapporte un verdict, et le pipeline transforme un verdict signalé en exception, laissant à votre code le choix de la réaction.

```python
from piighost.components.guard import (
    DetectorGuardRail,
    LLMGuardRail,
    ModerationGuardRail,
)
```

## Brancher un garde-fou dans un pipeline

`AnonymizationPipeline` prend un argument `guard` optionnel, désactivé par défaut. Une fois défini, le garde-fou s'exécute sur la sortie rendue après anonymisation, et le pipeline lève `PIIRemainingError` si le garde-fou signale quelque chose d'inattendu.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS, US_PATTERNS
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline

# The primary detector only knows the literal name; the guard re-runs a broader
# email and phone regex over the short output to catch structured PII it missed.
guard_detector = RegexDetector({**GENERIC_PATTERNS, **US_PATTERNS})
pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Emma Doe": "PERSON"}),
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
    guard=DetectorGuardRail(guard_detector),
)

try:
    result = await pipeline.anonymize("Emma Doe, reachable at emma@acme.com.")
except PIIRemainingError as error:
    print(error)             # Anonymized text still contains PII: ['EMAIL']
    print(error.detections)  # the residual detections behind the flag
```

La version exécutable est [`examples/guard_rail.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail.py), qui utilise aussi un garde-fou en autonome en appelant `await guard.check(text)` et en lisant le verdict sans lever d'exception.

## `DetectorGuardRail`

Réexécute un détecteur sur la sortie anonymisée et signale tout ce qu'il y trouve encore, en portant les détections résiduelles sur le verdict.

```python
DetectorGuardRail(detector: AnyDetector)
```

Cela n'a de valeur qu'avec un détecteur différent de celui du pipeline : réexécuter le même ne trouve rien, puisque le pipeline a déjà anonymisé tout ce qu'il détecte. Un détecteur plus puissant ou complémentaire, exécuté en seconde passe peu coûteuse sur la courte sortie anonymisée, rattrape ce que le détecteur primaire a manqué. Les placeholders synthétiques n'ont pas la forme de PII, donc un détecteur conçu pour de vraies PII les laisse tranquilles. Il ne requiert aucun extra.

## `LLMGuardRail`

Enveloppe un `LLMDetector` configuré avec un prompt de garde qui dit au modèle d'ignorer les placeholders et de ne signaler que les PII résiduelles en clair, puis rapporte un verdict.

```python
LLMGuardRail(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
    prefix: str = "<<",
    suffix: str = ">>",
)
```

Un modèle `str` est chargé comme celui de `LLMDetector` ; une instance déjà chargée est utilisée telle quelle. Un `prompt` personnalisé doit contenir un placeholder `{labels}`. Quand aucun prompt personnalisé n'est fourni, `prefix` et `suffix` (par défaut `<<` et `>>`) façonnent les exemples de placeholder du prompt par défaut pour qu'ils correspondent aux délimiteurs que le pipeline émet. Requiert `piighost[llm]`.

## `ModerationGuardRail`

Classifie les PII résiduelles avec le modèle de modération de Mistral, en lisant le score de la catégorie PII et en signalant le verdict quand il atteint le seuil.

```python
ModerationGuardRail(
    client: Mistral,
    model: str = "mistral-moderation-latest",
    threshold: float = 0.5,
)
```

Étant d'une modalité différente d'un détecteur, il attrape des PII qu'un pipeline basé sur la détection ne peut pas localiser, au prix d'un verdict au niveau du texte, sans spans. Requiert `piighost[mistral]`.

## `GuardVerdict` et `PIIRemainingError`

`check` renvoie un `GuardVerdict(flagged: bool, score: float | None, detections: tuple[Detection, ...])` gelé. Le détail dépend du garde-fou : un score depuis un modèle de modération, ou les détections résiduelles depuis un détecteur. Les deux sont optionnels.

Quand un garde-fou signale des PII, le pipeline lève `PIIRemainingError` (une sous-classe de `GuardError`, elle-même une `PIIGhostError`). Son message nomme les labels fuités ou le score, et son attribut `detections` contient les détections résiduelles, vide pour un garde-fou basé sur un score qui ne localise rien.

## Configurer un garde-fou depuis un fichier

Une section `[guard]` ajoute l'étage, discriminée sur `type`.

```toml
[guard]
type = "detector"

[guard.detector]
type = "regex"
catalogs = ["generic", "us"]
```

| `type` | Champs | Extra |
|--------|--------|-------|
| `detector` | `[guard.detector]` (une config de détecteur) | | 
| `llm` | `model`, `labels`, `prompt` (optionnel), `provider` (optionnel) | `llm` |
| `moderation` | `model` (défaut `mistral-moderation-latest`), `threshold` (défaut `0.5`) | `mistral` |

Le garde-fou de modération lit `MISTRAL_API_KEY` dans l'environnement à la construction, levant `ConfigError` s'il est absent. Chaque clé `[guard]` est dans la [référence de configuration](../configuration/toml.md).

## Voir aussi

- [Pipeline](pipeline.md) : où l'étage garde-fou se place dans l'exécution.
- [Détecteurs](detectors.md) : les détecteurs qu'un `DetectorGuardRail` réexécute.
- [Sécurité](../security.md) : ce qu'un garde-fou protège et ne protège pas.
