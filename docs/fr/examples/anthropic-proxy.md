---
icon: lucide/link
---

# Dé-identifier Claude Code avec le proxy Anthropic

`piighost-api` sert un proxy compatible avec l'API Messages d'Anthropic sous `/anthropic/v1`. Claude Code, ou tout client de l'API Messages, pointe son URL de base dessus, et le proxy dé-identifie les messages et le contenu des outils, les relaie à Anthropic, puis restaure la réponse, streamée ou non. Le modèle reçoit `<<PERSON:1>>`{ .placeholder }, jamais `Patrick`{ .pii }.

!!! note "Prérequis"
    Un serveur `piighost-api` lancé, voir [Déployer une API de dé-identification](../getting-started/api-server.md), et une clé d'API Anthropic ou la clé d'une passerelle compatible.

## Pointer Claude Code vers le proxy

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8000/anthropic
export ANTHROPIC_API_KEY=sk-ant-...
claude
```

Claude Code appelle alors `/anthropic/v1/messages` sur le proxy. Le proxy relaie à Anthropic chaque en-tête du client sauf ceux de saut à saut, `Host`, `Content-Length`, `Accept-Encoding` et les en-têtes `X-PIIGhost-*`, donc la clé d'API, le user agent et les drapeaux bêta arrivent tels que Claude Code les a envoyés. Le proxy ne demande aucune clé de serveur, donc les clés `API_KEY_` du serveur ne s'appliquent pas à `/anthropic/v1`.

## Vérifier que le modèle ne voit jamais la valeur

Servez une configuration qui connaît votre prénom, ici `Patrick`{ .pii } :

```toml title="patrick.toml"
[detector]
type = "exact"

[detector.values]
Patrick = "PERSON"
```

```bash
piighost-api serve --config patrick.toml
```

Lancez-le dans le shell où votre `API_KEY_DEV` est exportée, puisque le serveur refuse de démarrer sans clé. Pointez Claude Code dessus comme plus haut, puis demandez "What is the first letter of my name, Patrick?". Le modèle ne peut pas répondre, puisque la requête qu'il a reçue porte `<<PERSON:1>>`{ .placeholder }. La réponse que vous lisez est restaurée, donc elle affiche toujours `Patrick`{ .pii } là où le modèle a écrit le jeton.

## Choisir l'upstream

Sans en-tête, le proxy relaie vers `https://api.anthropic.com/v1`. Si vous voulez une passerelle pour tous les clients, posez `PIIGHOST_ANTHROPIC_UPSTREAM` avant de démarrer le serveur :

```bash
export PIIGHOST_ANTHROPIC_UPSTREAM="https://gateway.internal/v1"
```

Si vous la voulez pour une seule requête, nommez l'URL de base de la passerelle dans l'en-tête `X-PIIGhost-Upstream`. Chaque requête s'exécute dans une conversation neuve, oubliée une fois la réponse restaurée, ce qui correspond à Claude Code qui renvoie tout l'historique à chaque tour. Fixez une conversation avec `X-PIIGhost-Thread-Id` seulement si vous gérez vous-même sa durée de vie.

## Guider le modèle avec une note

Une courte note explique les placeholders au modèle et lui demande de réutiliser `<<PERSON:1>>`{ .placeholder } tel quel, sans jamais deviner l'orthographe d'une valeur cachée. Elle est désactivée par défaut. Pour placer la note intégrée en tête du premier message utilisateur, posez :

```bash
export PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE=default
export PIIGHOST_ANTHROPIC_NOTE_PLACEMENT=user
```

`PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` accepte aussi votre propre texte à la place de `default`. Sans `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT=user`, la note est placée en tête du prompt système.

## Dé-identifier aussi le prompt système

Le prompt système est relayé intact par défaut, et seuls les messages et le contenu des outils sont dé-identifiés. Certains comptes, dont des comptes par abonnement ou entreprise, valident le client à partir de son prompt système et rejettent une requête dont le prompt système a été modifié. Le même contrôle rejette une note placée dans le prompt système, d'où le placement de la note dans le premier message utilisateur.

Si votre compte tolère un prompt système modifié, dé-identifiez-le aussi :

```bash
export PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM=true
```

!!! warning "Limites"
    - Avec le prompt système intact, le comportement par défaut, une valeur écrite dedans atteint le modèle en clair.
    - Les images, les documents et les définitions d'outils de `tools` sont relayés intacts.
    - Une requête streamée que l'upstream refuse reçoit le statut de l'upstream et ses en-têtes `retry-after` et `anthropic-ratelimit-*`. Un échec au milieu d'un stream arrive au client comme un stream tronqué.

Les champs que le proxy dé-identifie et restaure sont listés dans [Endpoints de l'API](../reference/api-endpoints.md).

## Voir aussi

- [Dé-identifier Claude Code avec les hooks](claude-code.md) : l'autre voie pour Claude Code, par son système de hooks.
- [Proxy compatible OpenAI](openai-proxy.md) : le même relais pour l'API OpenAI.
- [CLI du serveur](../reference/api-cli.md) : chaque variable d'environnement du serveur.
