---
icon: lucide/arrow-up-circle
---

# Versions et migrations

`piighost` suit le versionnage sémantique. Une version patch change un comportement, une version mineure ajoute des composants ou des options, et une version majeure change l'API publique. Un nom marqué déprécié continue de fonctionner, et de pointer vers l'implémentation actuelle, jusqu'à la prochaine version majeure.

Vérifiez la version installée, puis mettez à jour :

```bash
python -c "import piighost; print(piighost.__version__)"

pip install -U piighost
# ou, avec uv
uv lock --upgrade-package piighost
```

Chaque version a une entrée dans [CHANGELOG.md](https://github.com/Athroniaeth/piighost/blob/master/CHANGELOG.md), avec ses fonctionnalités, ses correctifs et ses ruptures de compatibilité.

## Stabilité de l'API

Les noms publics n'offrent pas tous la même garantie. Un nom stable ne change qu'à une version majeure. Un nom expérimental peut changer à une version mineure, et l'entrée de CHANGELOG le signale alors.

### Stable

<div class="wide-table" markdown="1">

| Surface | Ce que ça couvre |
|---|---|
| Racine du package | Tous les noms de `piighost.__all__` : `AnonymizationPipeline`, `ThreadAnonymizationPipeline`, `Anonymizer`, `RegexDetector`, `ExactMatchDetector`, `CompositeDetector`, `ChunkedDetector`, `LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`, `Detection`, `Entity`, `Span`, `PIIGhostError` |
| Ports et templates | Chaque protocole `Any*` et son template `Base*`, une paire par étage du pipeline |
| Modèles de données | `Detection`, `Entity` et `Span`, dataclasses gelées dont les champs sont stables |
| Configuration | `PipelineConfig`, `load_config`, `load_pipeline`, `load_thread_pipeline`, et les clés listées dans la [référence TOML](../configuration/toml.md) |
| Ligne de commande | `piighost validate`, `piighost schema`, `piighost anonymize` |
| Intégration LangChain | `PIIAnonymizationMiddleware`, `ToolCallStrategy`, `InventedPlaceholderStrategy`, `EntityCreateByAssistantStrategy` |

</div>

Une version mineure ajoute des composants, des options et des factories de placeholder par-dessus, sans les modifier. Une option ajoutée en version mineure porte toujours le comportement précédent comme valeur par défaut.

### Expérimental

<div class="wide-table" markdown="1">

| Surface | Pourquoi ça peut encore bouger |
|---|---|
| `piighost.integrations.claude_code` | Un prototype. Aucun hook Claude Code ne peut réécrire la réponse affichée par l'assistant, ce manque n'est pas résolu, et la dé-identification fait un appel par feuille de texte au lieu de les grouper. |
| `piighost.integrations.llama_index` | Récente, deux composants, et la forme du wrapper de moteur de requête n'a pas encore été éprouvée sur de vrais corpus. |
| `LLMDetector`, `LLMGuardRail` | Le prompt et le schéma de sortie structurée dépendent de ce qu'accepte un fournisseur, donc les deux peuvent être remaniés quand un fournisseur change. |
| `ModerationGuardRail` | Lié à une API de modération Mistral tierce dont les catégories et les seuils échappent à ce projet. |
| `BridgeDetector`, `AnySpanRunner` | Récent, et la forme de span qu'il accepte d'un exécuteur n'a pas encore été éprouvée sur assez d'exécuteurs pour être figée. |

</div>

Épinglez une version exacte si vous construisez sur l'une d'elles, et lisez le CHANGELOG avant une montée de version mineure.

### Déprécié

Aucun nom n'est déprécié en 2.0. Les noms que la 1.x gardait par compatibilité sont supprimés, et listés dans la section suivante.

Les correctifs de sécurité n'atterrissent que sur la dernière version mineure, aussi bien sur la surface stable que sur l'expérimentale. Une version mineure antérieure ne reçoit rien, rester à jour fait donc partie du contrat.

## Passer à la 2.0

### Les catalogues regex sont des groupes du hub

`piighost` n'embarque plus aucun motif. Le module `piighost.components.detector.patterns` disparaît avec ses quatre catalogues, et les mêmes ensembles sont des groupes du [hub piighost](https://hub.piighost.dev).

| 1.x | 2.0 |
|---|---|
| `GENERIC_PATTERNS`, `catalogs = ["generic"]` | `hub:piighost/generic:fab51b33` |
| `US_PATTERNS`, `catalogs = ["us"]` | `hub:piighost/us:29d5c0a5` |
| `EU_PATTERNS`, `catalogs = ["eu"]` | `hub:piighost/eu:b0303ae6` |
| `FR_PATTERNS`, `catalogs = ["fr"]` | `hub:piighost/fr:6802f5ef` |

```python
# 1.x
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

detector = RegexDetector({**GENERIC_PATTERNS, **FR_PATTERNS})

# 2.0
from piighost.hub import pull

detector = RegexDetector.from_hub("hub:piighost/generic:fab51b33")
detector = RegexDetector(
    {**pull("hub:piighost/generic:fab51b33"), **pull("hub:piighost/fr:6802f5ef")}
)
```

Une config qui nomme encore `generic`, `us`, `eu` ou `fr` est refusée au chargement, avec la référence qui la remplace. Une référence épinglée sur un commit est téléchargée à la première construction, puis lue depuis le cache disque, donc un pipeline n'atteint le réseau qu'une fois. Les groupes du hub ont évolué depuis que les catalogues en avaient été copiés : `us` porte `US_ITIN`, `fr` porte `FR_SIREN`, et le motif e-mail de `generic` n'accepte que les lettres latines. `piighost anonymize` sans config lance `hub:piighost/generic:fab51b33`.

### Les alias de la 1.x sont supprimés

| Supprimé | À utiliser |
|---|---|
| `piighost.integrations.middleware` | `piighost.integrations.langchain` |
| `AssistantEntityStrategy` | `EntityCreateByAssistantStrategy` |
| l'extra `piighost[middleware]` | `piighost[langchain]` |

```python
# 1.x
from piighost.integrations.middleware import AssistantEntityStrategy, PIIAnonymizationMiddleware

# 2.0
from piighost.integrations.langchain import EntityCreateByAssistantStrategy, PIIAnonymizationMiddleware
```

### `BridgeDetector` prend une unité de décalage

`offset_unit` est un mot-clé obligatoire, `OffsetUnit.CODE_POINT` pour un exécuteur écrit en Python, `OffsetUnit.UTF16` pour un exécuteur écrit en JavaScript. Un exécuteur JavaScript compte un emoji pour deux, si bien que ses décalages tombaient un caractère trop loin après chacun. Un décalage qui n'est pas un entier, `8.0` compris, lève maintenant `BridgePayloadError` au lieu d'être tronqué, et un span noté sous `threshold` est écarté même quand l'exécuteur l'a ignoré. Voir la [référence des détecteurs](../reference/detectors.md).

### Comportements qui changent

- **Espaces Unicode.** `RegexDetector` lit toute espace Unicode comme une espace ordinaire, donc un motif qui cherchait exprès une espace insécable n'en trouve plus. Deux valeurs qui ne diffèrent que par leurs espaces sont une seule valeur, et reçoivent un seul jeton.
- **Traits d'union.** Tout trait d'union Unicode relie deux mots dans une recherche par mot entier, y compris le trait d'union insécable que tape Word, donc `Jean`{ .pii } n'est plus trouvé dans `Jean‑Paul`{ .pii } écrit avec lui.
- **Détecteurs NER.** Chaque adaptateur relit dans la source le texte d'une détection et applique lui-même son seuil, quoi que rende son modèle. Une détection de `Gliner2Detector` peut donc porter un texte un peu différent d'avant, celui du document plutôt que celui du modèle.
- **Surcharges.** Deux détections sur un même span gardent l'ordre de leurs détecteurs après une liste blanche, comme sans elle.

Une mémoire de conversation écrite par la 1.x indexe la provenance d'une valeur par son texte casefoldé, alors que la 2.0 l'indexe par la valeur aux espaces réduites. Une valeur tapée avec une espace inhabituelle peut perdre sa provenance au passage. Purgez le stockage, comme pour le changement Argon2 plus bas, si cela compte pour un fil en cours.

## Les digests Argon2 ont changé

`Argon2Hasher` passe désormais la valeur dans un HMAC-SHA256 clé par le pepper avant qu'Argon2id ne la hache, donc un digest n'est plus celui qu'une version antérieure produisait. Rien ne change dans l'API, mais toute clé déjà stockée sous l'ancien digest devient introuvable.

Cela concerne une mémoire de conversation Redis ou SQLAlchemy construite avec `type = "argon2"`. Un déploiement sur `sha256`, ou sans hasher du tout, n'est pas concerné.

Les entrées stockées sont orphelines, pas corrompues. Le pipeline ne trouve rien sous la nouvelle clé, considère le message comme jamais vu, et le redétecte. Un thread en cours repart donc avec une numérotation de tokens remise à zéro, et une même valeur peut atterrir sur un numéro différent de celui que le modèle lisait jusque-là.

Purgez le store pendant la montée de version, avant de redémarrer l'application :

```bash
# Redis, la base entière qui porte la mémoire de conversation
redis-cli -n 0 FLUSHDB
```

```sql
-- SQLAlchemy, la table de mémoire de conversation (son nom par défaut)
TRUNCATE TABLE piighost_conversation_messages;
```

Une entrée laissée en place expire d'elle-même si un `ttl` est configuré. Sans TTL elle reste indéfiniment, purger est alors le seul moyen de récupérer la place.

## Venir de la 0.x

Chaque version avant la 1.0.0 exposait une API différente, donc un code en 0.x se porte en réécrivant son montage plutôt qu'en renommant ses imports. Ce qui a changé :

- les imports vivent sous `piighost.components`, `piighost.pipeline`, `piighost.config` et `piighost.integrations`
- un pipeline prend un détecteur et rien d'autre, puisque le linker et l'anonymiseur ont des valeurs par défaut
- les extras `faker`, `cache`, `langfuse` et `opik` ont disparu, et aucun étage ne met les détections en cache
- l'extra `sqlalchemy` est revenu en 1.2.0, comme backend de mémoire de conversation

Repartez du [Quickstart](../getting-started/quickstart.md), puis lisez [Premier pipeline](../getting-started/first-pipeline.md) pour les étages et la [référence TOML](../configuration/toml.md) pour déplacer le montage dans un fichier de configuration.
