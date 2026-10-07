---
icon: lucide/shield-check
tags:
  - Garde-fou
---

# Référence des garde-fous

Module : `piighost.components.guard`

Un garde-fou est le dernier étage, optionnel, du pipeline. Il revérifie le texte dé-identifié pour y chercher des valeurs confidentielles résiduelles. S'il en trouve, le pipeline lève `PIIRemainingError` plutôt que de renvoyer une fuite. Chaque garde-fou satisfait le port `AnyGuardRail`, un `async def check(self, text: str) -> GuardVerdict`. Il renvoie un `GuardVerdict` indiquant si des valeurs confidentielles semblent subsister et comment il le sait. Contrairement aux autres étages, les garde-fous ne partagent aucun template `Base*`, parce que leurs mécanismes de vérification n'ont pas de squelette commun. L'un réexécute un détecteur local, un autre appelle une API externe.

Le garde-fou classifie, il ne décide pas. Il rapporte un verdict. Le pipeline transforme un verdict signalé en exception, et votre code choisit comment réagir.

```python
from piighost.components.guard import (
    DetectorGuardRail,
    LLMGuardRail,
    ModerationGuardRail,
)
```

## Brancher un garde-fou dans un pipeline

`AnonymizationPipeline` prend un argument `guard` optionnel, désactivé par défaut. Une fois défini, le garde-fou s'exécute sur la sortie rendue après dé-identification, et le pipeline lève `PIIRemainingError` si le garde-fou signale quelque chose d'inattendu.

```python
--8<-- "snippets/reference_guard.py"
```

La version exécutable est [`examples/guard_rail.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail.py). Ce script utilise aussi un garde-fou seul. Il appelle `await guard.check(text)` et lit le verdict sans lever d'exception. La version à modèle local est [`examples/guard_rail_local_model.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail_local_model.py).

## `DetectorGuardRail`

Réexécute un détecteur sur la sortie dé-identifiée et signale tout ce qu'il y trouve encore, en portant les détections résiduelles sur le verdict.

```python
DetectorGuardRail(
    detector: AnyDetector,
    recognizer: BaseDelimitedPlaceholderFactory | None = None,
    ignore_placeholders: bool = True,
)
```

Ce garde-fou n'a de valeur qu'avec un détecteur différent de celui du pipeline. Réexécuter le même ne trouve rien, puisque le pipeline a déjà dé-identifié tout ce qu'il détecte. Un détecteur plus puissant ou complémentaire, exécuté en seconde passe peu coûteuse sur la courte sortie dé-identifiée, rattrape ce que le détecteur primaire a manqué. `DetectorGuardRail` ne requiert aucun extra.

### Les placeholders sont ignorés

Un détecteur à base de modèle étiquette souvent les placeholders eux-mêmes. GLiNER2 lit `<<PERSON:1>>`{ .placeholder } comme une personne dans 169 textes dé-identifiés sur 200, donc un garde-fou qui signale chaque détection refuse tous les textes. `DetectorGuardRail` écarte donc chaque détection qui ne contient que des placeholders, c'est-à-dire qui garde moins de deux lettres ou chiffres une fois ses placeholders mis de côté.

- `<<PERSON:1>>, <<PERSON:2>>` est écartée, il ne reste qu'une virgule
- `<<PERSON:1>> Dubois` signale, il reste `Dubois`{ .pii }
- `Mme Dubois`{ .pii } à côté de `<<PERSON:2>>`{ .placeholder } signale, la détection ne contient aucun placeholder

Le verdict ne porte que les détections qui signalent. Le garde-fou retrouve les placeholders avec la grammaire du pipeline où il tourne, délimiteurs personnalisés compris. Seul, il lit les formes par défaut `<<PERSON>>`, `<<PERSON:1>>` et `<<PERSON:a1b2c3d4>>`, ou la grammaire de la factory passée en `recognizer`. Passez `ignore_placeholders=False` pour signaler chaque détection.

### Un modèle local comme garde

Le détecteur complémentaire est souvent un modèle, parce que les formes qu'un regex attrape bien sont justement celles que la passe primaire a déjà prises. Ce qui passe au travers, c'est un nom, une adresse, une raison sociale :

```python
--8<-- "snippets/reference_guard_gliner2.py:example"
```

Ce garde localise ce qui a fuité. C'est ce qu'un garde adossé à un détecteur apporte de plus qu'un classifieur. Pour un verdict au niveau du texte issu du même checkpoint, sans spans et en une seule passe, voir [`Gliner2GuardRail`](#gliner2guardrail).

### Ce qu'il rattrape

Le [benchmark des garde-fous de décision](https://github.com/Athroniaeth/piighost/tree/master/benchmarks/decision_guard) fait tourner ce garde-fou, avec le détecteur ci-dessus, sur 200 textes dé-identifiés. La moitié est en français, l'autre en anglais, et la moitié laisse fuir une valeur.

| Seuil | Fuites rattrapées | Fausses alertes |
|---|---|---|
| 0,5 | 97/100 | 49/100 |
| 0,9 | 83/100 | 3/100 |
| Choisi sur les autres gabarits | 83/100 | 7/100 |

Le seuil de 0,9 a été choisi sur les données du benchmark, donc ses 3 fausses alertes sont optimistes. La dernière ligne est le chiffre honnête. Pour chacun des 28 gabarits de texte, le seuil qui rattrape le plus de fuites avec au plus 5 % de fausses alertes sur les 27 autres est testé sur celui mis de côté. Sans le filtre des placeholders, le même détecteur signale les 200 textes au seuil de 0,5.

Deux sortes de fausses alertes restent :

- un mot de rôle lu comme une personne, comme "Customer", "[User]" ou "Tenant"
- une civilité à côté d'un placeholder, comme `Mr <<PERSON:3>>`

Choisissez le seuil sur vos propres documents. Un seuil choisi sur les textes français ne se transpose pas tel quel aux textes anglais.

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
    fail_open: bool = False,
)
```

Un modèle `str` est chargé comme celui de `LLMDetector`. Une instance déjà chargée est utilisée telle quelle. Un `prompt` personnalisé doit contenir un placeholder `{labels}`. Quand aucun prompt personnalisé n'est fourni, `prefix` et `suffix` (par défaut `<<` et `>>`) façonnent les exemples de placeholder du prompt par défaut pour qu'ils correspondent aux délimiteurs que le pipeline émet. Une sortie que le garde ne sait pas lire lève `UnreadableOutputError` au lieu de déclarer le texte propre, sauf avec `fail_open=True`. Ce comportement est le même que pour `LLMDetector`. Requiert `piighost[llm]`.

## `Gliner2GuardRail`

Classe la sortie dé-identifiée avec un modèle de garde GLiNER2 qui tourne dans le processus, et signale le verdict quand la réponse revient `unsafe` avec assez de confiance.

```python
Gliner2GuardRail(
    model: GLiNER2 | str = "fastino/GLiNER2-Guardrails-PII-Multi",
    task: str = "response_safety",
    labels: tuple[str, ...] = ("safe", "unsafe"),
    threshold: float = 0.5,
)
```

C'est `ModerationGuardRail` sans l'appel d'API, et cette différence est tout l'intérêt. Le texte qu'un garde examine est celui qui contient encore ce qui a fuité. L'envoyer à un tiers est donc une drôle de forme pour la dernière étape d'un pipeline de dé-identification. Le modèle par défaut fait 300M de paramètres, couvre sept langues, et fait modération de sûreté et extraction de PII en une seule passe.

Un modèle `str` est chargé avec `GLiNER2.from_pretrained`, et une instance déjà chargée est utilisée telle quelle. Un même checkpoint peut ainsi servir à ce garde et à un `Gliner2Detector`. La paire `labels` est lue par position, et la réponse refusée vient en dernier. Une autre tâche du même modèle se lit donc de la même façon. Par exemple, `task="response_refusal"` avec `labels=("compliance", "refusal")` signale un refus. Requiert `piighost[gliner2]`.

```python
--8<-- "snippets/reference_gliner2_guard.py"
```

`Gliner2GuardRail` rend un verdict au niveau du texte, donc il ne localise rien. `detections` reste vide et seul `score` est renseigné. Associez-le à un `DetectorGuardRail` s'il vous faut savoir quelle valeur a fuité. Les placeholders qu'émet le pipeline ne le déclenchent pas. Par exemple, `<<EMAIL:1>>` est classé `safe` à 0,989. La version exécutable est [`examples/guard_rail_local_model.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail_local_model.py).

## `ModerationGuardRail`

Classifie les PII résiduelles avec le modèle de modération de Mistral, en lisant le score de la catégorie PII et en signalant le verdict quand il atteint le seuil.

```python
ModerationGuardRail(
    client: Mistral,
    model: str = "mistral-moderation-latest",
    threshold: float = 0.5,
)
```

Ce garde-fou classe le texte, il ne détecte pas de valeurs. Il attrape donc des PII qu'un pipeline basé sur la détection ne peut pas localiser. En contrepartie, il rend un verdict au niveau du texte, sans spans. Requiert `piighost[mistral]`.

## `GuardVerdict` et `PIIRemainingError`

`check` renvoie un `GuardVerdict(flagged: bool, score: float | None, detections: tuple[Detection, ...])` gelé. Le détail dépend du garde-fou. C'est un score depuis un modèle de modération, ou les détections résiduelles depuis un détecteur. Les deux sont optionnels.

Quand un garde-fou signale des valeurs confidentielles, le pipeline lève `PIIRemainingError` (une sous-classe de `GuardError`, elle-même une `PIIGhostError`). Son message nomme les labels fuités ou le score. Son attribut `detections` contient les détections résiduelles. Il reste vide pour un garde-fou basé sur un score, qui ne localise rien.

## Configurer un garde-fou depuis un fichier

Une section `[guard]` ajoute l'étage, et son champ `type` choisit le garde-fou.

```toml
[guard]
type = "detector"

[guard.detector]
type = "regex"
catalogs = ["catalog:piighost/generic", "catalog:piighost/us"]
```

| `type` | Champs | Extra |
|--------|--------|-------|
| `detector` | `[guard.detector]` (une config de détecteur), `ignore_placeholders` (défaut `true`) | | 
| `gliner2` | `model` (défaut `fastino/GLiNER2-Guardrails-PII-Multi`), `task`, `labels`, `threshold` | `gliner2` |
| `llm` | `model`, `labels`, `prompt` (optionnel), `provider` (optionnel) | `llm` |
| `moderation` | `model` (défaut `mistral-moderation-latest`), `threshold` (défaut `0.5`) | `mistral` |

Le garde-fou de modération lit `MISTRAL_API_KEY` dans l'environnement à la construction. Il lève `ConfigError` si la variable est absente. Chaque clé `[guard]` est dans la [référence de configuration](../configuration/toml.md).

## Voir aussi

- [Pipeline](pipeline.md) : où l'étage garde-fou se place dans l'exécution.
- [Détecteurs](detectors.md) : les détecteurs qu'un `DetectorGuardRail` réexécute.
- [Sécurité](../security.md) : ce qu'un garde-fou protège et ne protège pas.
