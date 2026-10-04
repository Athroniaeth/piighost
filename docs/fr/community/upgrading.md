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
| Racine du package | Tous les noms de `piighost.__all__`, c'est-à-dire `AnonymizationPipeline`, `ThreadAnonymizationPipeline`, `Anonymizer`, `RegexDetector`, `ExactMatchDetector`, `CompositeDetector`, `ChunkedDetector`, `LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`, `Detection`, `Entity`, `Span`, `PIIGhostError` |
| Ports et templates | Chaque protocole `Any*` et son template `Base*`, une paire par étage du pipeline |
| Modèles de données | `Detection`, `Entity` et `Span`, dataclasses gelées dont les champs sont stables |
| Configuration | `PipelineConfig`, `load_config`, `load_pipeline`, `load_thread_pipeline`, et les clés listées dans la [référence TOML](../configuration/toml.md) |
| Ligne de commande | `piighost validate`, `piighost schema`, `piighost anonymize` |
| Intégration LangChain | `PIIAnonymizationMiddleware`, `ToolCallStrategy`, `InventedPlaceholderStrategy`, `EntityCreateByAssistantStrategy` |
| Détecteurs à modèle | `Gliner2Detector`, `SpacyDetector`, `TransformersDetector`, tous trois sur la passe commune de `BaseNERDetector` |
| Garde-fous | `DetectorGuardRail`, qui relance n'importe quel détecteur sur la sortie |

</div>

Une version mineure ajoute des composants, des options et des factories de placeholder par-dessus, sans les modifier. Une option ajoutée en version mineure porte toujours le comportement précédent comme valeur par défaut.

### Expérimental

<div class="wide-table" markdown="1">

| Surface | Pourquoi ça peut encore bouger |
|---|---|
| `piighost.integrations.claude_code` | Un prototype. Aucun hook Claude Code ne peut réécrire la réponse affichée par l'assistant, et ce manque n'est pas résolu. La dé-identification fait aussi un appel par feuille de texte au lieu de les grouper. |
| `piighost.integrations.llama_index` | Récente, deux composants, et la forme du wrapper de moteur de requête n'a pas encore été éprouvée sur de vrais corpus. |
| `LLMDetector`, `LLMGuardRail` | Le prompt et le schéma de sortie structurée peuvent être remaniés quand un fournisseur change, parce qu'ils dépendent de ce que ce fournisseur accepte. |
| `ModerationGuardRail` | Lié à une API de modération Mistral tierce dont les catégories et les seuils échappent à ce projet. |
| `BridgeDetector`, `AnySpanRunner` | Récent, et la forme de span qu'il accepte d'un exécuteur n'a pas encore été éprouvée sur assez d'exécuteurs pour être figée. |
| `Gliner2PiiDetector` | Un préréglage. Ses labels par défaut suivent un checkpoint PII, et bougent quand ce checkpoint bouge. |
| `PresidioDetector` | Un adaptateur sur l'analyseur de Presidio. Les reconnaisseurs et les noms d'entités appartiennent au projet Presidio. |
| `Gliner2GuardRail` | Récent, et sa tâche et ses labels par défaut suivent un checkpoint de garde-fou. |

</div>

Épinglez une version exacte si vous construisez sur une surface expérimentale, et lisez le CHANGELOG avant une montée de version mineure.

### Déprécié

Aucun nom n'est déprécié en 2.0. Les noms que la 1.x gardait par compatibilité sont supprimés, et listés dans la section suivante.

Les correctifs de sécurité n'atterrissent que sur la dernière version mineure, aussi bien sur la surface stable que sur l'expérimentale. Une version mineure antérieure ne reçoit aucun correctif. Rester à jour fait donc partie du contrat.

## Passer à la 2.0

### Les catalogues regex sont des groupes du hub

`piighost` n'embarque plus aucun motif. Le module `piighost.components.detector.patterns` disparaît avec ses quatre catalogues, et les mêmes ensembles sont des groupes du [hub piighost](https://hub.piighost.dev).

| 1.x | 2.0 |
|---|---|
| `GENERIC_PATTERNS`, `catalogs = ["generic"]` | `hub:piighost/generic` |
| `US_PATTERNS`, `catalogs = ["us"]` | `hub:piighost/us` |
| `EU_PATTERNS`, `catalogs = ["eu"]` | `hub:piighost/eu` |
| `FR_PATTERNS`, `catalogs = ["fr"]` | `hub:piighost/fr` |

```python
# 1.x
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

detector = RegexDetector({**GENERIC_PATTERNS, **FR_PATTERNS})

# 2.0
--8<-- "snippets/upgrading_catalogs.py:example"
```

Une config qui nomme encore `generic`, `us`, `eu` ou `fr` est refusée au chargement, avec la référence qui la remplace. Une référence épinglée sur un commit est téléchargée à la première construction, puis lue depuis le cache disque. Un pipeline n'atteint donc le réseau qu'une fois. Les groupes du hub ont évolué depuis que les catalogues en avaient été copiés. Le groupe `us` porte `US_ITIN`, `fr` porte `FR_SIREN`, et le motif e-mail de `generic` n'accepte que les lettres latines. `piighost anonymize` sans config lance `hub:piighost/generic`.

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
--8<-- "snippets/upgrading.py:aliases"
```

### `BridgeDetector` prend une unité de décalage

`offset_unit` est un mot-clé obligatoire, `OffsetUnit.CODE_POINT` pour un exécuteur écrit en Python, `OffsetUnit.UTF16` pour un exécuteur écrit en JavaScript. Un exécuteur JavaScript compte un emoji pour deux unités. Ses décalages tombaient donc un caractère trop loin après chaque emoji. Un décalage qui n'est pas un entier, `8.0` compris, lève maintenant `BridgePayloadError` au lieu d'être tronqué. Un span noté sous `threshold` est écarté, même quand l'exécuteur a ignoré ce seuil. Voir la [référence des détecteurs](../reference/detectors.md).

### Une conversation est toujours nommée

`require_thread_id` est supprimé du middleware LangChain. Un appel dont la config LangGraph ne porte pas de `thread_id` lève toujours `MissingThreadIdError`, et un événement Claude Code sans `session_id` aussi. `PIIGhostClient.detect` prend un `thread_id` obligatoire. Si vos conversations n'ont pas besoin d'être séparées, nommez la conversation `"default"`.

```python
# 1.x
middleware = PIIAnonymizationMiddleware(pipeline, require_thread_id=False)
await agent.ainvoke({"messages": messages})

# 2.0
--8<-- "snippets/upgrading.py:middleware"
--8<-- "snippets/upgrading.py:invoke"
```

### Comportements qui changent

- **Espaces Unicode.** `RegexDetector` lit toute espace Unicode comme une espace ordinaire, donc un motif qui cherchait exprès une espace insécable n'en trouve plus. Deux valeurs qui ne diffèrent que par leurs espaces sont une seule valeur, et reçoivent un seul jeton.
- **Traits d'union.** Dans une recherche par mot entier, tout trait d'union Unicode relie deux mots, y compris le trait d'union insécable que tape Word. `Jean`{ .pii } n'est donc plus trouvé dans `Jean‑Paul`{ .pii } écrit avec ce trait d'union.
- **Détecteurs NER.** Chaque adaptateur relit dans la source le texte d'une détection et applique lui-même son seuil, quoi que rende son modèle. Une détection de `Gliner2Detector` peut donc porter un texte un peu différent d'avant, celui du document plutôt que celui du modèle.
- **Surcharges.** Après une liste blanche, deux détections sur un même span gardent l'ordre de leurs détecteurs, comme quand aucune liste blanche n'est posée.
- **Mémoire en processus.** `InMemoryConversationMemory` est bornée par défaut à 10 000 conversations et un jour d'inactivité. Une conversation évincée ou expirée ne restaure plus ses jetons. Passez `max_threads=None` et `ttl=None` pour retrouver le store sans borne de la 1.x.
- **Détecteur et garde-fou LLM.** Une sortie que `LLMDetector` ou `LLMGuardRail` ne sait pas lire lève `UnreadableOutputError` au lieu de compter comme zéro détection, donc le message est refusé. Passez `fail_open=True`, ou `fail_open = true` dans une configuration, pour l'envoyer sans détection comme le faisait la 1.x.
- **Hooks Claude Code.** Un hook qui ne peut pas dé-identifier, quand le serveur est arrêté par exemple, bloque le prompt ou l'appel d'outil et remplace une sortie d'outil par un avis. Réglez `PIIGHOST_HOOK_FAIL_OPEN=1` pour laisser passer le texte en clair comme le faisait la 1.x.

Une mémoire de conversation écrite par la 1.x indexe la provenance d'une valeur par son texte casefoldé (mis en minuscules au sens Unicode), alors que la 2.0 l'indexe par la valeur aux espaces réduites. Une valeur tapée avec une espace inhabituelle peut perdre sa provenance au passage. Si cette provenance compte pour une conversation en cours, purgez le stockage, comme pour le changement Argon2 plus bas.

### Le serveur d'API

`piighost-api` demande `piighost>=2.0,<3`, et sa configuration suit les règles de la 2.0 ci-dessus, références du hub de `catalogs` comprises.

- `--config` et `PIIGHOST_CONFIG` acceptent une référence du hub aussi bien qu'un chemin de fichier.
- Une configuration sans section `[memory]` est servie avec la mémoire in-process au lieu d'être refusée. Déclarez une mémoire `redis` pour partager les conversations entre instances.
- `/v1/anonymize`, `/v1/anonymize/corrected` et `/v1/deanonymize` exigent un `thread_id`, et répondent `400` sans lui au lieu d'utiliser la conversation partagée `"default"`.
- `/v1/labels` lit les labels d'un groupe du hub sur le hub.
- L'observation passe par les variables standard `OTEL_*`. `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY` ne servent qu'à `dataset extract`, et aucune variable `OPIK_*` n'est lue.
- Le serveur ne lit aucun `REDIS_URL`. L'adresse Redis est l'`url` de la section `[memory]`.
- Un déploiement qui pose encore `PIPELINE_PATH`, ou passe un chemin `module:variable`, date d'avant le chargeur TOML. Posez plutôt `PIIGHOST_CONFIG` à un fichier de config ou à une référence du hub.

Les routes et les variables sont listées dans [Endpoints de l'API](../reference/api-endpoints.md) et [CLI du serveur](../reference/api-cli.md).

## Les digests Argon2 ont changé

`Argon2Hasher` passe désormais la valeur dans un HMAC-SHA256, avec pour clé le pepper (le secret lu dans `PIIGHOST_HASH_PEPPER`), avant qu'Argon2id ne la hache. Un digest n'est donc plus celui qu'une version antérieure produisait. Rien ne change dans l'API, mais toute clé déjà stockée sous l'ancien digest devient introuvable.

Cela concerne une mémoire de conversation Redis ou SQLAlchemy construite avec `type = "argon2"`. Un déploiement sur `sha256`, ou sans hasher du tout, n'est pas concerné.

Les entrées stockées sont orphelines, pas corrompues. Le pipeline ne trouve rien sous la nouvelle clé, considère le message comme jamais vu, et le redétecte. Une conversation en cours repart donc avec une numérotation de jetons remise à zéro, et une même valeur peut atterrir sur un numéro différent de celui que le modèle lisait jusque-là.

Purgez le store pendant la montée de version, avant de redémarrer l'application :

```bash
# Redis, la base entière qui porte la mémoire de conversation
redis-cli -n 0 FLUSHDB
```

```sql
-- SQLAlchemy, la table de mémoire de conversation (son nom par défaut)
TRUNCATE TABLE piighost_conversation_messages;
```

Une entrée laissée en place expire d'elle-même si un `ttl` est configuré. Sans TTL, elle reste indéfiniment. Purger est alors le seul moyen de récupérer la place.

## Venir de la 0.x

Un code en 0.x se porte en réécrivant son montage, pas en renommant ses imports, parce que chaque version avant la 1.0.0 exposait une API différente. Ce qui a changé :

- les imports vivent sous `piighost.components`, `piighost.pipeline`, `piighost.config` et `piighost.integrations`
- un pipeline prend un détecteur et rien d'autre, puisque le linker et l'anonymiseur ont des valeurs par défaut
- les extras `faker`, `cache`, `langfuse` et `opik` ont disparu, et aucun étage ne met les détections en cache
- l'extra `sqlalchemy` est revenu en 1.2.0, comme backend de mémoire de conversation

Repartez du [Quickstart](../getting-started/quickstart.md), puis lisez [Premier pipeline](../getting-started/first-pipeline.md) pour les étages et la [référence TOML](../configuration/toml.md) pour déplacer le montage dans un fichier de configuration.
