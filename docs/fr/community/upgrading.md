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
-- SQLAlchemy, la table de mémoire de conversation (its default name)
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
