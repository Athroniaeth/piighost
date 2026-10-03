---
icon: lucide/list
tags:
  - Détecteur
  - Regex
---

# Référence Détecteurs

Module : `piighost.components.detector`

Un détecteur est l'étage de détection d'un pipeline. Il lit un texte et renvoie les données confidentielles qu'il y trouve. Tout détecteur satisfait le port `AnyDetector` et renvoie une liste de `Detection`, quel que soit le backend qu'il enveloppe.

```python
from piighost.components.detector import (
    ChunkedDetector,
    CompositeDetector,
    ExactMatchDetector,
    LLMDetector,
    RegexDetector,
)
from piighost.components.detector.ner import (
    BridgeDetector,
    Gliner2Detector,
    Gliner2PiiDetector,
    PresidioDetector,
    SpacyDetector,
    TransformersDetector,
)
```

Chaque détecteur NER a besoin de son propre extra (`gliner2`, `spacy`, `transformers`, `presidio`). `LLMDetector` a besoin de l'extra `llm` et d'un paquet fournisseur.

---

## `AnyDetector` (protocole)

C'est le port que tout détecteur implémente. Sa seule méthode est asynchrone, donc une implémentation peut attendre une I/O comme un serveur de modèle ou une API LLM sans bloquer le pipeline.

```python
@runtime_checkable
class AnyDetector(Protocol):
    async def detect(self, text: str) -> list[Detection]: ...
```

`detect` renvoie les détections dans un ordre quelconque. Les chevauchements et les doublons sont résolus par les étages suivants du pipeline, pas par le détecteur.

### `Detection`

Chaque détecteur renvoie une liste de `Detection`, un dataclass gelé qui porte l'emplacement de la correspondance, le texte trouvé, son label et sa confiance.

| Attribut | Type | Description |
|----------|------|-------------|
| `span` | `Span` | L'emplacement de la détection, en intervalle semi-ouvert |
| `text` | `str` | La sous-chaîne trouvée |
| `label` | `str` | La catégorie de la valeur détectée, par exemple `PERSON` ou `EMAIL` |
| `confidence` | `float` | La confiance du détecteur, dans l'intervalle fermé 0 à 1 |

---

## `RegexDetector`

Trouve les données confidentielles en appliquant un pattern regex par label. Chaque pattern est compilé une fois à la construction, sous `re.ASCII`, donc `\d` et les autres classes de forme ne correspondent qu'à l'ASCII. Un caractère Unicode ressemblant à un chiffre, comme un chiffre arabo-indien, ne correspond pas, car les formats que le détecteur cible utilisent des chiffres ASCII. `detect` émet une détection par correspondance sans chevauchement, à une confiance fixe de 1.0. Chaque espace Unicode du texte est lue comme une espace ordinaire, voir [Espaces Unicode](#espaces-unicode).

Il ne porte aucun validateur de somme de contrôle. Il reconnaît donc une valeur sur sa forme seule. Une valeur structurée abîmée par un OCR est conservée plutôt que rejetée, car rejeter une vraie valeur reviendrait à la laisser fuiter.

### Constructeur

```python
RegexDetector(patterns: dict[str, str])
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `patterns` | `dict[str, str]` | Correspondance d'un label vers le pattern regex à appliquer (requis) |

```python
--8<-- "snippets/reference_detectors.py:regex"
```

### `from_hub`

```python
RegexDetector.from_hub(ref: str, *, hub: str | None = None) -> RegexDetector
```

Construit un détecteur à partir des regex que porte une référence du [hub piighost](https://hub.piighost.dev). Le hub est un registre de regex de dé-identification testées, adressées par `namespace/name` et un sélecteur optionnel, soit un tag, soit les huit caractères hexadécimaux d'un commit.

| Paramètre | Type | Description |
|-----------|------|-------------|
| `ref` | `str` | Une référence, `namespace/name` avec un `:selector` optionnel et un préfixe `hub:` optionnel. Sans sélecteur, elle résout vers `latest` (requis) |
| `hub` | `str \| None` | Origine du hub à interroger. Par défaut `PIIGHOST_HUB_URL`, puis le hub public |

```python
--8<-- "snippets/reference_regex_hub.py:from_hub"
```

Une référence épinglée sur un commit est immuable. Sa réponse est donc mise en cache sous `~/.cache/piighost/hub` et relue depuis le disque aux appels suivants. Une référence qui pointe vers un tag ou vers `latest` peut changer. Elle est donc récupérée à chaque fois, parce qu'une version périmée détecterait sans le dire moins que ce que l'appelant a demandé.

L'appel lève une sous-classe de `HubError` (`piighost.hub`) si la référence ne se parse pas, si le hub est injoignable, ou si la référence résout vers autre chose qu'un détecteur regex simple. Ce dernier cas couvre une référence qui porte un détecteur modèle. Ses regex seules détecteraient moins que ce que la référence promet, donc l'appel échoue plutôt que d'en rendre la moitié.

`from_hub` n'utilise que la bibliothèque standard, donc l'installation de base n'a besoin d'aucun extra.


---

## `CompositeDetector`

Fait tourner plusieurs détecteurs sur le même texte et fusionne leurs détections. Il est lui-même un `AnyDetector`, donc il se compose avec le pipeline sans changement. Il exécute chaque enfant en parallèle et concatène leurs résultats dans l'ordre des enfants. Il ne déduplique pas. Chevauchements et doublons passent à l'étage de résolution de spans.

### Constructeur

```python
CompositeDetector(detectors: list[AnyDetector])
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `detectors` | `list[AnyDetector]` | Les détecteurs enfants à exécuter, dans l'ordre (requis) |

```python
--8<-- "snippets/reference_composite.py"
```

---

## `ExactMatchDetector`

Trouve les occurrences en mot entier de valeurs littérales configurées. Il parcourt le texte pour chaque valeur et émet une détection par occurrence à une confiance de 1.0. La correspondance se fait sur des frontières de mot, donc une valeur ne se déclenche pas à l'intérieur d'un mot plus long (`Ann`{ .pii } ne correspond pas dans `Anne`{ .pii }). La correspondance est insensible à la casse par défaut. Une valeur correspond donc quelle que soit sa casse, et la détection garde le texte tel qu'il apparaît. Une espace dans une valeur correspond à n'importe quelle suite d'espaces, voir [Espaces Unicode](#espaces-unicode). Une valeur faite uniquement d'espaces est refusée. Il ne porte aucun modèle et aucune dépendance optionnelle. C'est donc le détecteur de choix pour exercer le pipeline dans les tests.

### Constructeur

```python
ExactMatchDetector(values: dict[str, str], case_sensitive: bool = False)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `values` | `dict[str, str]` | Correspondance d'une valeur littérale vers le label à émettre pour elle (requis) |
| `case_sensitive` | `bool` | Si la correspondance respecte la casse. `False` par défaut |

```python
--8<-- "snippets/reference_detectors.py:exact"
```

---

## `ChunkedDetector`

Fait tourner un détecteur enveloppé sur chaque morceau d'un texte long. C'est un décorateur, lui-même un `AnyDetector`. Il découpe le texte en morceaux qui se chevauchent, exécute le détecteur enveloppé sur chacun, et reprojette chaque détection sur le texte original. Les détections strictement identiques produites par le chevauchement sont supprimées. Conflits de label et confiances différentes passent à l'étage de résolution de spans.

### Constructeur

```python
ChunkedDetector(detector: AnyDetector, splitter: AnySplitter | None = None)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `detector` | `AnyDetector` | Le détecteur exécuté sur chaque morceau (requis) |
| `splitter` | `AnySplitter \| None` | Le splitter, ou `None` pour un `RecursiveCharacterTextSplitter` par défaut |

```python
--8<-- "snippets/reference_chunked.py"
```

---

## `LLMDetector`

Détecte les PII avec un modèle de chat LangChain via une sortie structurée. A besoin de l'extra `llm` et d'un paquet fournisseur. On demande au modèle d'extraire des paires `(text, label)` selon un schéma. Le champ label de ce schéma n'accepte que les labels configurés. Chaque valeur extraite est ensuite localisée dans le texte source par recherche sur frontière de mot, donc une valeur inventée par le modèle mais absente du texte ne donne rien. `labels` est requis, puisque le schéma est construit à partir de ces labels. Le texte source est enveloppé dans des balises `<text_to_analyze>`. Le prompt système ordonne au modèle de traiter le contenu balisé comme des données, jamais comme des instructions. Une tentative d'injection de prompt dans le texte ne peut donc pas orienter l'extraction.

### Constructeur

```python
LLMDetector(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
    confidence: float = 1.0,
    fail_open: bool = False,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `BaseChatModel \| str` | Un modèle de chat chargé, ou un nom chargé avec `init_chat_model` (requis) |
| `labels` | `list[str] \| dict[str, str]` | Les labels à extraire, liste ou map `{emitted: internal}` (requis) |
| `prompt` | `str \| None` | Un prompt système personnalisé, ou `None` pour celui par défaut |
| `provider` | `str \| None` | Le fournisseur passé à `init_chat_model` quand `model` est un nom |
| `confidence` | `float` | Confiance portée sur chaque détection, 1.0 par défaut, pour qu'un détecteur LLM puisse être départagé face à un détecteur NER à la résolution des chevauchements |
| `fail_open` | `bool` | Si une sortie que le détecteur ne sait pas lire passe comme zéro détection, `False` par défaut |

Un `prompt` personnalisé doit contenir un placeholder `{labels}`. Il doit aussi doubler toute autre accolade littérale en `{{` ou `}}`, selon le format f-string de LangChain.

Une sortie que le détecteur ne sait pas lire, un JSON cassé ou un résultat sans son champ `entities`, lève `UnreadableOutputError`. Un modèle en panne refuse donc le message au lieu de l'envoyer sans détection. L'erreur nomme le type de la sortie, jamais son texte. Avec `fail_open=True`, le message part sans détection et un avertissement est journalisé, pour un déploiement qui fait passer la disponibilité avant la protection.

```python
--8<-- "snippets/reference_llm_detector.py:example"
```

---

## Détecteurs NER

Les détecteurs adossés à un modèle étendent `BaseNERDetector`, qui gère la correspondance et le filtrage des labels (voir plus bas). Chacun a besoin de son propre extra et prend un modèle chargé ou un nom de modèle à charger, sauf `PresidioDetector`, qui prend un `AnalyzerEngine` construit.

### `Gliner2Detector`

Un modèle GLiNER2 zero-shot. A besoin de l'extra `gliner2`. `labels` est requis, car GLiNER2 est interrogé avec les labels internes. Un `model` en `str` est chargé avec `GLiNER2.from_pretrained`.

```python
Gliner2Detector(
    model: GLiNER2 | str,
    labels: list[str] | dict[str, str],
    threshold: float = 0.5,
    max_concurrency: int | None = None,
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `GLiNER2 \| str` | Un modèle chargé, ou un nom chargé avec `from_pretrained` (requis) |
| `labels` | `list[str] \| dict[str, str]` | Les labels à interroger, liste ou map `{emitted: internal}` (requis) |
| `threshold` | `float` | La confiance à partir de laquelle une entité est conservée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |
| `max_chars` | `int \| None` | Limite en caractères vue par une seule inférence, ou `None` pour aucune limite |
| `auto_chunk` | `bool` | Si un texte plus long que `max_chars` est découpé et reprojeté, sinon lève `TextTooLongError` |

### `Gliner2PiiDetector`

Un `Gliner2Detector` prêt à l'emploi sur le modèle GLiNER2 de fastino affiné pour les PII. Le modèle et la map de labels sont préréglés, donc ni identifiant de modèle ni argument `labels` n'est requis. Le préréglage couvre la taxonomie du modèle, des noms et coordonnées aux identifiants, données de paiement, identité numérique, secrets et dates sensibles. Passez `labels` pour restreindre ou étendre l'ensemble, ou `model` pour injecter une instance chargée, par exemple dans un test, afin qu'aucun poids ne soit téléchargé.

```python
Gliner2PiiDetector(
    model: GLiNER2 | str | None = None,
    labels: list[str] | dict[str, str] | None = None,
    threshold: float = 0.5,
    max_concurrency: int | None = None,
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `GLiNER2 \| str \| None` | Un modèle chargé ou un nom, ou `None` pour le modèle PII préréglé |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à interroger, ou `None` pour la map de labels PII préréglée |
| `threshold` | `float` | La confiance à partir de laquelle une entité est conservée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |
| `max_chars` | `int \| None` | Limite en caractères vue par une seule inférence, ou `None` pour aucune limite |
| `auto_chunk` | `bool` | Si un texte plus long que `max_chars` est découpé et reprojeté, sinon lève `TextTooLongError` |

### `SpacyDetector`

Un modèle NER spaCy. A besoin de l'extra `spacy`. `labels` est optionnel. Omis, chaque entité produite par spaCy est conservée avec son label spaCy. Un `model` en `str` est chargé avec `spacy.load`.

```python
SpacyDetector(
    model: Language | str,
    labels: list[str] | dict[str, str] | None = None,
    max_concurrency: int | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `Language \| str` | Un modèle chargé, ou un nom chargé avec `spacy.load` (requis) |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à mapper et filtrer, ou `None` pour garder chaque label natif |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |

### `TransformersDetector`

Un pipeline de classification de tokens Hugging Face. A besoin de l'extra `transformers`. `labels` est optionnel. Omis, chaque label natif est gardé. Un `pipeline` en `str` est chargé comme un pipeline `ner`. Une entité qui score sous `threshold` est rejetée.

```python
TransformersDetector(
    pipeline: TokenClassificationPipeline | str,
    labels: list[str] | dict[str, str] | None = None,
    threshold: float = 0.0,
    max_concurrency: int | None = None,
    aggregation_strategy: str = "simple",
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `pipeline` | `TokenClassificationPipeline \| str` | Un pipeline construit, ou un nom de modèle chargé comme pipeline `ner` (requis) |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à mapper et filtrer, ou `None` pour garder chaque label natif |
| `threshold` | `float` | Le score sous lequel une entité détectée est rejetée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |
| `aggregation_strategy` | `str` | Comment les sous-tokens sont regroupés en entités entières, appliqué seulement à la construction depuis un nom de modèle. Un pipeline injecté garde la sienne. `"simple"` par défaut |
| `max_chars` | `int \| None` | Limite en caractères vue par une seule inférence, ou `None` pour aucune limite |
| `auto_chunk` | `bool` | Si un texte plus long que `max_chars` est découpé et reprojeté, sinon lève `TextTooLongError` |

### `PresidioDetector`

Enveloppe un `AnalyzerEngine` de Presidio pour réutiliser ses recognizers. A besoin de l'extra `presidio`. L'analyzer est injecté, car un moteur est assemblé d'un moteur NLP et d'un registre de recognizers, pas chargé depuis un nom. `labels` est optionnel. Omis, chaque type natif est gardé. Une entité scorant sous `threshold` est écartée.

```python
PresidioDetector(
    analyzer: AnalyzerEngine,
    labels: list[str] | dict[str, str] | None = None,
    language: str = "en",
    threshold: float = 0.0,
    max_concurrency: int | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `analyzer` | `AnalyzerEngine` | Un analyzer Presidio construit (requis) |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à mapper et filtrer, ou `None` pour garder chaque type natif |
| `language` | `str` | Le code de langue passé à `analyze` |
| `threshold` | `float` | Le score sous lequel une entité est écartée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |

Depuis une config, le type de détecteur `presidio` construit l'`AnalyzerEngine` anglais par défaut de Presidio. Pour une autre langue ou des recognizers custom, construisez le moteur vous-même et utilisez `PresidioDetector` directement.

### `BridgeDetector`

Délègue l'inférence à un exécuteur injecté et convertit sa réponse en détections. Il ne porte aucun modèle et ne demande aucun extra. Il existe pour un environnement où aucune pile NER n'est installable. Le cas courant est le navigateur. Le modèle y tourne dans le runtime JavaScript de l'hôte, et Python l'attend via le FFI de Pyodide. La même forme sert n'importe quel exécuteur hors du processus, un sous-processus ou un side-car.

`labels` est obligatoire, puisque l'exécuteur est interrogé avec les labels internes et qu'un span dont le label n'est pas mappé est écarté, comme pour tout adaptateur NER. `offset_unit` est obligatoire aussi, puisque rien dans une réponse ne dit si ses décalages comptent des points de code ou des unités UTF-16.

```python
BridgeDetector(
    runner: AnySpanRunner,
    labels: list[str] | dict[str, str],
    *,
    offset_unit: OffsetUnit,
    threshold: float = 0.5,
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `runner` | `AnySpanRunner` | L'appelable attendu pour chaque texte, qui porte le modèle (obligatoire) |
| `labels` | `list[str] \| dict[str, str]` | Les labels à mapper et filtrer (obligatoire) |
| `offset_unit` | `OffsetUnit` | Ce que l'exécuteur compte dans ses décalages, `CODE_POINT` ou `UTF16` (obligatoire) |
| `threshold` | `float` | La confiance à partir de laquelle un span est retenu, transmise à l'exécuteur puis appliquée à nouveau sur sa réponse |
| `max_chars` | `int \| None` | Borne au-delà de laquelle le texte est découpé, ou `None` pour aucune borne |
| `auto_chunk` | `bool` | Si un texte au-delà de `max_chars` est découpé plutôt que refusé |

L'exécuteur est un appelable asynchrone qui prend le texte, les labels internes et le seuil, et rend une séquence de mappings portant `start`, `end`, `label` et `score`. Les décalages sont des positions dans le texte transmis, en intervalle semi-ouvert, comptées dans l'unité que nomme `offset_unit`.

| `OffsetUnit` | Compte | Exécuteur |
|---|---|---|
| `CODE_POINT` | des caractères, comme une `str` Python et `Span` | écrit en Python |
| `UTF16` | des unités UTF-16, où un emoji ou un idéogramme rare en prend deux | écrit en JavaScript, dans un navigateur ou dans Node |

Sur un texte sans emoji ni idéogramme rare, les deux unités concordent. Après chacun de ces caractères, elles s'écartent d'une unité. Un décalage JavaScript lu comme un point de code tombe un caractère trop loin, et la première lettre de la valeur reste en clair. Un exécuteur JavaScript déclare donc `UTF16`, et le détecteur convertit.

```python
--8<-- "snippets/reference_detectors.py:bridge"
```

Un exécuteur est du code étranger, souvent atteint au travers d'une frontière de langage, donc sa réponse est vérifiée plutôt que crue.

- Le `text` que l'exécuteur rend est ignoré et relu depuis la source, donc un exécuteur qui abîme la sous-chaîne trouvée ne peut pas désynchroniser le remplacement.
- Un span auquel il manque un champ, ou qui porte un décalage qui n'est pas un entier, un flottant comme `8.9` ou `8.0` compris, lève `BridgePayloadError`. Tronquer un tel décalage déplacerait le span.
- Un span qui déborde du texte, ou un décalage UTF-16 qui tombe entre les deux moitiés d'un caractère, lève `BridgeSpanRangeError`. Rogner le span découperait une sous-chaîne plus courte que ce que l'exécuteur visait, et laisserait une partie de la valeur en clair.
- Un span noté sous `threshold` est écarté, même quand l'exécuteur a ignoré le seuil qu'il a reçu.
- Un résultat portant une méthode `to_py`, comme le fait un `JsProxy` de Pyodide, est converti d'abord.

Ce détecteur n'a pas de modèle de configuration. Son exécuteur est un appelable. Un fichier TOML ou JSON ne peut pas nommer un appelable sans un registre d'appelables, et ce registre ferait dépendre le cœur de ce qui le configure. Un appelant qui construit ce détecteur le construit dans le code.

### Gestion des textes longs

`Gliner2Detector`, `TransformersDetector` et `BridgeDetector` prennent `max_chars` avec `auto_chunk` (défaut `True`). Un texte plus long que `max_chars` est découpé en morceaux qui se chevauchent, scannés séparément, puis reprojetés sur le texte original. Avec `auto_chunk` désactivé, un texte au-delà de la limite lève `TextTooLongError` à la place. `max_chars` vaut `None` par défaut, donc il n'y a pas de limite et le texte entier est scanné en une passe. `SpacyDetector` et `PresidioDetector` n'exposent pas ces deux paramètres.

### Garanties communes à tous les détecteurs NER

`BaseNERDetector` applique une même passe à ce que rend n'importe quel modèle, si bien que tous les adaptateurs se comportent pareil, quel que soit leur backend.

- Le texte d'une détection est la tranche de la source que couvre son span, jamais la chaîne que le modèle a rendue. La fusion des chevauchements, le regroupement et la restauration supposent tous que le texte correspond aux caractères qu'il remplace.
- Une détection notée sous `threshold` est écartée, même quand le modèle a reçu le seuil et laissé passer une détection plus faible.
- Les labels sont mappés et filtrés, comme le décrit la section suivante.

### Correspondance des labels

`BaseNERDetector` normalise l'argument `labels` en une map externe vers interne, puis mappe et filtre les détections produites par le modèle. Il distingue le label qu'un modèle utilise nativement du label émis dans `Detection.label`.

- Une liste, `["PERSON", "LOCATION"]`, mappe chaque label vers lui-même.
- Une map, `{"PERSON": "PER"}`, prend le label émis comme clé et le label natif du modèle comme valeur. Une détection que le modèle étiquette `PER` est donc émise en `PERSON`. Un label natif absent des valeurs de la map est rejeté.
- `None` ou une map vide n'applique aucune correspondance, donc chaque détection est gardée avec le label donné par le modèle.

Deux labels externes mappant vers un même label interne lèvent `LabelMappingError`, car la recherche inverse serait ambiguë.

```python
--8<-- "snippets/reference_transformers.py"
```

---

## Catalogues de patterns

Ensembles de patterns regex réutilisables pour `RegexDetector`, publiés sous forme de groupes sur le [hub piighost](https://hub.piighost.dev). Chaque groupe associe un label de PII à un pattern regex. Les patterns correspondent sur la forme seule, sans validation de somme de contrôle.

<div class="wide-table" markdown="1">

| Groupe | Référence | Labels |
|--------|-----------|--------|
| Générique | `hub:piighost/generic:fab51b33` | `EMAIL`, `URL`, `IPV4`, `CREDIT_CARD` |
| US | `hub:piighost/us:29d5c0a5` | `US_PHONE`, `US_ZIP`, `US_ITIN`, `US_SSN` |
| EU | `hub:piighost/eu:b0303ae6` | `IBAN` |
| France | `hub:piighost/fr:6802f5ef` | `FR_PHONE`, `FR_IBAN`, `FR_NIR`, `FR_SIRET`, `FR_SIREN` |
| Secrets | `hub:piighost/secrets:d822d04c` | `OPENAI_API_KEY`, `AWS_ACCESS_KEY`, `GITHUB_TOKEN`, `STRIPE_KEY` |

</div>

Construisez un détecteur à partir d'un groupe avec [`from_hub`](#from_hub). `pull` (`piighost.hub`) renvoie un groupe sous forme de `dict[str, str]` dans l'ordre du registre. Plusieurs groupes se fusionnent donc comme des dict, et pour un même label, l'entrée de droite l'emporte.

```python
--8<-- "snippets/reference_regex_hub.py:merge"
```

Une référence épinglée sur un commit se termine par les huit caractères hexadécimaux du commit, après le dernier deux-points. Elle est récupérée à la première construction d'un détecteur, puis relue depuis le cache sur disque, même hors ligne. Une référence non épinglée, `hub:piighost/generic` ou `hub:piighost/generic:latest`, est récupérée à chaque construction.

Le hub teste chaque pattern qu'il publie contre le backtracking catastrophique, de sorte qu'une entrée adverse ne peut pas transformer un scan en déni de service.

Les labels du groupe générique ne dépendent d'aucun pays. Les autres sont préfixés (`US_`, `FR_`) pour ne pas se confondre quand les groupes sont fusionnés. Le groupe EU porte l'IBAN ISO 13616 partagé entre les États membres. Pour des numéros propres à un pays, utilisez un groupe par pays.

### Tirer les catalogues depuis une config

Une config de détecteur regex tire les catalogues via `catalogs`. Une entrée est une référence de hub écrite `hub:namespace/name` avec un `:selector` optionnel. Les catalogues fusionnent dans l'ordre, puis les `patterns` en ligne s'y ajoutent. Un pattern en ligne l'emporte donc sur un pattern de catalogue pour le même label. Une config de détecteur regex a besoin d'au moins un pattern en ligne ou un catalogue.

```toml
[detector]
type = "regex"
catalogs = ["hub:piighost/generic:fab51b33", "hub:piighost/fr:6802f5ef"]

[detector.patterns]
INTERNAL_ID = "EMP-\\d{6}"
```

Une référence de hub nomme un catalogue relu au lieu d'en porter une copie. La config reste donc courte, et les patterns restent auditables à leur source. Un catalogue est récupéré à la construction de la config, pas à sa lecture. Définissez `PIIGHOST_HUB_URL` pour interroger un registre privé.

Une entrée qui n'est pas une référence de hub échoue au chargement plutôt que sous forme d'URL invalide plus tard. Les noms `generic`, `us`, `eu` et `fr`, qui désignaient avant la 2.0 des catalogues livrés dans la librairie, sont refusés, et le message d'erreur donne la référence qui les remplace.

```text
the built-in catalog 'generic' was removed in piighost 2.0: name the hub group instead, hub:piighost/generic
```

## Espaces Unicode

Une valeur est souvent tapée avec une espace qui n'est pas l'espace ASCII. Word place une espace insécable (U+00A0) ou une espace fine insécable (U+202F) dans un numéro de téléphone ou un IBAN, l'extraction d'un PDF produit des espaces fines et des espaces de chiffre, et un texte d'Asie de l'Est utilise l'espace idéographique (U+3000). `piighost` lit chaque séparateur d'espace Unicode (catégorie Zs) comme une espace ordinaire, et chaque séparateur de ligne (U+0085, U+2028, U+2029) comme un retour à la ligne. Cette règle s'applique à trois étapes.

| Étape | Composants | Ce qui est garanti |
|---|---|---|
| Détection | `RegexDetector` | Un pattern écrit avec une espace ou avec `\s` reconnaît une valeur tapée avec n'importe quelle espace Unicode. Les patterns s'appliquent à une copie du texte de même longueur, donc les positions restent justes et le texte détecté garde ses espaces telles qu'elles sont écrites. |
| Recherche | `ExactMatchDetector`, `LLMDetector`, `WordBoundaryExpander` | Une espace dans une valeur cherchée correspond à n'importe quelle suite d'espaces, retour à la ligne compris, donc `Paul Martin`{ .pii } est retrouvé à travers une espace insécable, deux espaces ou un retour à la ligne. |
| Identité | `ExactEntityLinker`, overrides, mémoire de conversation, `FuzzyEntityResolver` | Deux valeurs sont la même quand elles ont les mêmes mots, quelles que soient les espaces qui les séparent et leur casse, donc elles partagent un jeton. |

La règle vaut pour tous les patterns, ceux du hub compris, donc un pattern n'a pas à prévoir ces caractères. Un pattern qui cherche exprès une espace insécable n'en trouve plus, car la copie sur laquelle il s'applique porte des espaces ordinaires à la place. Les caractères de largeur nulle (U+200B, U+2060, U+FEFF) ne sont pas des espaces et restent tels quels.

Les deux fonctions de cette règle, `normalize_spaces` et `value_key`, sont publiques dans `piighost.text`, pour un détecteur ou un linker personnalisé qui doit suivre la même règle.

```python
--8<-- "snippets/reference_text.fr.py:example"
```

## Recherche par mot entier

`ExactMatchDetector`, `LLMDetector` et `WordBoundaryExpander` ne trouvent une valeur que là où elle forme un mot entier. Le caractère qui la précède et celui qui la suit ne doivent donc pas appartenir à un mot.

| Caractère | Rôle | Exemple |
|---|---|---|
| lettre, chiffre, tiret bas | dans un mot | `Jean`{ .pii } n'est pas trouvé dans `Jeanne`{ .pii } |
| trait d'union, n'importe lequel | dans un mot | `Jean`{ .pii } n'est pas trouvé dans `Jean-Paul`{ .pii }, quel que soit le trait d'union qui les relie |
| tiret, demi-cadratin ou cadratin | borne un mot | `Paris`{ .pii } est trouvé dans `Paris–Lyon`{ .pii } |
| apostrophe, droite ou courbe | borne un mot | `Anne`{ .pii } est trouvé dans `d'Anne`{ .pii }, `Jean`{ .pii } dans `Jean's`{ .pii } |
| espace, n'importe laquelle | borne un mot | voir [Espaces Unicode](#espaces-unicode) |

Les traits d'union sont celui de l'ASCII, le trait d'union et le trait d'union insécable que Word écrit à sa place, le trait d'union conditionnel, le maqaf hébreu, et toute autre ponctuation de tiret que Unicode nomme trait d'union. Ils forment `WORD_JOIN_CHARS`, dans `piighost.text.boundaries`.

L'apostrophe borne un mot dans toutes les langues, puisqu'elle termine un mot aussi souvent qu'elle se trouve à l'intérieur. En contrepartie, `Brien`{ .pii } est aussi trouvé dans `O'Brien`{ .pii }. Le masque couvre alors plus que demandé, mais ne laisse rien en clair.

La règle suppose des espaces entre les mots, elle ne trouve donc rien en chinois, en japonais ou en thaï, voir [Limites](../limitations.md#la-recherche-par-mot-entier-suppose-des-espaces-entre-les-mots).

---

## Voir aussi

- [Référence Pipeline](pipeline.md) pour le pipeline qui pilote le détecteur.
- [Détecteurs prêts à l'emploi](../examples/detectors.md) pour composer les catalogues en pratique.
- [Configuration TOML](../configuration/toml.md) pour la construction déclarative.
- [Étendre PIIGhost](../extending.md) pour écrire son propre détecteur.
- [Référence des modèles de données](models.md) pour la forme complète d'une `Detection`.
