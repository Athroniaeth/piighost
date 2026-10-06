---
icon: lucide/link
seo_title: Un proxy compatible OpenAI qui masque les PII
description: Pointez le base_url d'un client OpenAI vers piighost-api. La requête est dé-identifiée avant OpenAI ou un fournisseur compatible. La réponse est restaurée.
---

# Proxy compatible OpenAI

`piighost-api` sert un proxy compatible OpenAI sous `/openai/v1`. Pointez le `base_url` d'un client dessus, et le proxy dé-identifie chaque requête, la relaie au vrai fournisseur, puis restaure la réponse. Le fournisseur reçoit `<<PERSON:1>>`{ .placeholder }, jamais `Jane Doe`{ .pii }.

!!! note "Prérequis"
    Un serveur `piighost-api` lancé, voir [Serveur d'API](../getting-started/api-server.md), et une clé du fournisseur. Les exemples utilisent le SDK Python d'OpenAI.

## Pointer le client vers le proxy

Changez seulement le `base_url`. L'`api_key` reste la clé du fournisseur.

```python
--8<-- "snippets/server_proxy.py:client"
```

Le fournisseur reçoit `<<PERSON:1>>`{ .placeholder } et `<<EMAIL:1>>`{ .placeholder }, et la réponse imprimée porte de nouveau `Jane Doe`{ .pii }. Les clés `API_KEY_` du serveur ne s'appliquent pas à `/openai/v1`, parce que le proxy ne demande aucune clé de serveur. Il relaie l'en-tête `Authorization` au fournisseur tel quel.

Le même appel avec curl :

```bash
curl http://127.0.0.1:8000/openai/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5.6-terra", "messages": [{"role": "user", "content": "I am Jane Doe"}]}'
```

## Choisir le fournisseur

Sans en-tête, le proxy relaie vers `https://api.openai.com/v1`. Si vous voulez un autre fournisseur compatible OpenAI pour tous les clients, posez `PIIGHOST_OPENAI_UPSTREAM` avant de démarrer le serveur :

```bash
export PIIGHOST_OPENAI_UPSTREAM="http://vllm.internal:8000/v1"
```

Si vous le voulez pour un seul client, nommez l'URL de base du fournisseur dans l'en-tête `X-PIIGhost-Upstream` :

```python
--8<-- "snippets/server_proxy_upstream.py:example"
```

Le proxy retire chaque en-tête `X-PIIGhost-*` avant de relayer, donc le fournisseur ne le voit jamais.

## Garder une conversation d'une requête à l'autre

Chaque requête s'exécute dans une conversation neuve, oubliée dès que la réponse est restaurée. Un client de chat renvoie tout l'historique à chaque tour, donc la numérotation des placeholders reste cohérente au sein de chaque requête. Si vous voulez que la conversation survive à la requête, par exemple pour restaurer plus tard une réponse stockée via `/v1/deanonymize`, fixez-la avec `X-PIIGhost-Thread-Id` :

```python
--8<-- "snippets/server_proxy.py:thread"
```

Une conversation fixée reste dans la mémoire du serveur jusqu'à ce que `DELETE /v1/threads/user-42` l'efface.

## Streamer la réponse

`stream=True` fonctionne sans changement. Le proxy restaure chaque placeholder à l'arrivée des fragments, même quand le fournisseur coupe `<<PERSON:1>>`{ .placeholder } sur deux fragments.

```python
--8<-- "snippets/server_proxy.py:stream"
```

!!! warning "Limites"
    - Une réponse streamée ne restaure que `delta.content`. Les arguments d'appel d'outil streamés dans `delta.tool_calls` gardent leurs placeholders, alors qu'une réponse non streamée les restaure.
    - Une requête streamée reçoit un statut de succès avant que le fournisseur ne réponde, donc une erreur du fournisseur arrive au client dans le corps du stream plutôt que comme statut.
    - Les images et l'audio sont relayés intacts, sans dé-identification.
    - Seuls les en-têtes `Authorization` et `Content-Type` d'un client OpenAI atteignent le fournisseur, donc un en-tête comme `OpenAI-Organization` est abandonné.

Les routes que le proxy sert, et les champs qu'il dé-identifie sur chacune, sont listés dans [Endpoints de l'API](../reference/api-endpoints.md).

## Voir aussi

- [Proxy compatible Anthropic](anthropic-proxy.md) : le même relais pour l'API Messages et Claude Code.
- [CLI du serveur](../reference/api-cli.md) : chaque variable d'environnement du serveur.
- [Stratégies d'appel outil](../tool-call-strategies.md) : comment la librairie traite les arguments d'outil quand elle tourne dans l'agent.
