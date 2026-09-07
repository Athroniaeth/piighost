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

</div>

Épinglez une version exacte si vous construisez sur l'une d'elles, et lisez le CHANGELOG avant une montée de version mineure.

### Déprécié

Les noms en voie de retrait sont listés dans la section suivante, avec la version qui les a dépréciés.

Les correctifs de sécurité n'atterrissent que sur la dernière version mineure 1.x, aussi bien sur la surface stable que sur l'expérimentale. Une version mineure antérieure ne reçoit rien, rester à jour fait donc partie du contrat.

## Noms dépréciés

Trois noms issus de versions précédentes restent importables. Ils pointent vers l'implémentation actuelle, donc rien ne casse aujourd'hui, et ils seront supprimés dans une future version majeure.

| Déprécié | À utiliser | Depuis | À l'usage |
|---|---|---|---|
| `piighost.integrations.middleware` | `piighost.integrations.langchain` | 1.4.0 | `DeprecationWarning` à l'import |
| `AssistantEntityStrategy` | `EntityCreateByAssistantStrategy` | 1.5.0 | `DeprecationWarning` à l'accès |
| l'extra `piighost[middleware]` | `piighost[langchain]` | 1.4.0 | aucun avertissement, les deux installent `langchain` |

L'ancien module et l'ancien nom de stratégie atteignent les mêmes objets que les noms actuels, donc la mise à jour est une ligne d'import réécrite :

```python
# déprécié, fonctionne encore
from piighost.integrations.middleware import AssistantEntityStrategy, PIIAnonymizationMiddleware

# actuel
from piighost.integrations.langchain import EntityCreateByAssistantStrategy, PIIAnonymizationMiddleware
```

Lancez votre suite de tests avec `python -W error::DeprecationWarning` pour échouer sur tout nom déprécié resté dans un code. La surface actuelle est listée dans la [référence LangChain](../reference/langchain.md).

## Venir de la 0.x

Chaque version avant la 1.0.0 exposait une API différente, donc un code en 0.x se porte en réécrivant son montage plutôt qu'en renommant ses imports. Ce qui a changé :

- les imports vivent sous `piighost.components`, `piighost.pipeline`, `piighost.config` et `piighost.integrations`
- un pipeline prend un détecteur et rien d'autre, puisque le linker et l'anonymiseur ont des valeurs par défaut
- les extras `faker`, `cache`, `langfuse` et `opik` ont disparu, et aucun étage ne met les détections en cache
- l'extra `sqlalchemy` est revenu en 1.2.0, comme backend de mémoire de conversation

Repartez du [Quickstart](../getting-started/quickstart.md), puis lisez [Premier pipeline](../getting-started/first-pipeline.md) pour les étages et la [référence TOML](../configuration/toml.md) pour déplacer le montage dans un fichier de configuration.
