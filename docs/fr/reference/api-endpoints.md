---
icon: lucide/server
---

# Référence des endpoints de l'API

Paquet : `piighost-api`

`piighost-api serve` construit un seul pipeline conversationnel à partir de sa configuration et sert chaque route ci-dessous dessus. Les corps de requête et de réponse sont en JSON. Le schéma OpenAPI est servi sur `/schema/openapi.json`, avec une interface Swagger sur `/schema/swagger`. `PIIGhostClient` appelle les routes du pipeline, voir [Client distant](../getting-started/api-client.md).

---

## Authentification

Le serveur charge ses clés au démarrage depuis chaque variable d'environnement dont le nom commence par `API_KEY_`. Une route protégée exige alors l'en-tête `Authorization: Bearer <key>`.

<div class="wide-table" markdown="1">

| Routes | Clé requise |
|---|---|
| `GET /`, `GET /health`, `GET /v1/labels` | jamais |
| `/v1/detect`, `/v1/anonymize`, `/v1/anonymize/corrected`, `/v1/deanonymize`, `/v1/threads/...`, `/schema/...` | quand des clés sont chargées |
| `/openai/v1/...`, `/anthropic/v1/...` | jamais, les identifiants de l'appelant sont relayés à l'upstream |

</div>

Un en-tête absent ou mal formé répond `401` avec `Missing or malformed Authorization header`, une clé inconnue `401` avec `Invalid API key`. Quand aucune clé ne se charge, le serveur refuse de démarrer sauf si `PIIGHOST_ALLOW_ANONYMOUS` est posée, et alors aucune route ne demande de clé. Les variables sont listées dans [CLI du serveur](api-cli.md).

---

## Codes de statut

| Statut | Quand |
|---|---|
| `200` | une route `GET` ou `DELETE` réussit |
| `201` | une route `POST` du pipeline réussit |
| `400` | le corps échoue à la validation, le corps d'un proxy n'est pas un objet JSON, ou une requête de proxy ne nomme aucun upstream et aucun n'est configuré |
| `401` | une route protégée ne reçoit pas de clé valide |
| `404` | la route n'existe pas, sous les préfixes des proxys aussi |
| `413` | le corps dépasse `PIIGHOST_MAX_BODY_BYTES` |
| `429` | le client dépasse `PIIGHOST_RATE_LIMIT`, avec des en-têtes `RateLimit-*` |
| `500` | le pipeline lève une exception, entre autres un garde-fou qui signale une valeur restée en clair ou un `role` inconnu |
| `502` | une route de proxy ne joint pas son upstream |

Sinon, une route de proxy répond avec le statut de l'upstream.

---

## Objets partagés

### `Entity`

| Champ | Type | Description |
|---|---|---|
| `label` | string | Le label de l'entité, comme `PERSON` |
| `placeholder` | string | Le token qui remplace l'entité, vide sur `/v1/detect` |
| `detections` | liste de `Detection` | Chaque occurrence de l'entité dans le texte |

### `Detection`

| Champ | Type | Description |
|---|---|---|
| `text` | string | La valeur telle qu'elle apparaît dans le texte |
| `label` | string | Le label de la détection |
| `start_pos` | integer | Décalage de début dans le texte |
| `end_pos` | integer | Décalage de fin dans le texte, exclu |
| `confidence` | float | Score du détecteur, `1.0` pour une regex ou une correspondance exacte |

---

## Routes de service

### `GET /`

```json
{"name": "piighost-api", "version": "...", "docs": "/schema/swagger"}
```

`version` est la version installée de `piighost-api`.

### `GET /health`

```json
{"status": "ok", "detector": "composite"}
```

`detector` est le `type` de la section `[detector]` de la configuration. `GET /` et `GET /health` échappent à `PIIGHOST_RATE_LIMIT`.

### `GET /v1/labels`

```json
{"name": "piighost/fr-default:e6990159", "detector": "regex", "labels": ["CREDIT_CARD", "EMAIL", "EU_VAT", "FR_IBAN", "FR_NIR", "FR_PHONE", "FR_SIREN", "FR_SIRET", "IBAN", "IPV4", "SWIFT_BIC", "URL"]}
```

| Champ | Type | Description |
|---|---|---|
| `name` | string ou null | Le `name` de la configuration |
| `detector` | string | Le `type` de `[detector]` |
| `labels` | liste de strings | Chaque label que `[detector]` peut émettre, trié |

Les labels sont collectés dans la seule section `[detector]`, le détecteur du garde-fou exclu.

| `type` du détecteur | Labels |
|---|---|
| `regex` | les clés de `patterns`, plus celles de chaque groupe du hub listé dans `catalogs`, lu sur le hub via son cache disque |
| `gliner2`, `spacy`, `transformers`, `llm` | `labels`, ou ses clés quand il associe les labels du modèle à des labels canoniques |
| `exact` | les labels de `values` |
| `composite` | l'union de ses `detectors` |
| `chunked` | ceux de son `detector` |
| tout autre | aucun |

---

## Routes du pipeline

### `POST /v1/detect`

Exécute le détecteur et le linker sur un texte et renvoie les entités, sans placeholders. La mémoire du thread n'est ni lue ni écrite, et les étapes d'override, de chevauchement, d'expansion et de garde-fou ne s'exécutent pas.

| Champ de requête | Type | Défaut |
|---|---|---|
| `text` | string | requis |
| `thread_id` | string | `"default"`, accepté et inutilisé |

Pour le texte `Write to jane.doe@example.com`, la réponse est :

```json
{"entities": [{"label": "EMAIL", "placeholder": "", "detections": [{"text": "jane.doe@example.com", "label": "EMAIL", "start_pos": 9, "end_pos": 29, "confidence": 1.0}]}]}
```

### `POST /v1/anonymize`

Dé-identifie un message dans un thread, avec des tokens cohérents sur tout le thread.

| Champ de requête | Type | Défaut |
|---|---|---|
| `text` | string | requis |
| `thread_id` | string | `"default"` |
| `role` | `"user"` ou `"assistant"` | `"user"` |

| Champ de réponse | Type | Description |
|---|---|---|
| `anonymized_text` | string | Le texte où chaque valeur est remplacée par son placeholder |
| `entities` | liste de `Entity` | Les entités de ce message qui ont reçu un token |

`role` date les valeurs qu'un message introduit. Une valeur écrite d'abord par l'assistant ne reçoit pas de token et reste en clair.

### `POST /v1/anonymize/corrected`

Dé-identifie à nouveau un message à partir d'un jeu de détections corrigé, pour une étape de relecture humaine. Le jeu remplace les détections du message dans la mémoire du thread, après l'override configuré, et la détection ne s'exécute pas de nouveau.

| Champ de requête | Type | Défaut |
|---|---|---|
| `text` | string | requis |
| `detections` | liste d'objets avec `text`, `label`, `start`, `end`, `confidence` | requis |
| `thread_id` | string | `"default"` |

Une détection corrigée nomme ses décalages `start` et `end`, pas `start_pos` et `end_pos`. La réponse est `{"anonymized_text": "..."}`.

### `POST /v1/deanonymize`

Restaure chaque placeholder émis par le thread, dans n'importe quel texte, une réponse de modèle comprise. Un token que le thread n'a jamais émis reste tel quel.

| Champ de requête | Type | Défaut |
|---|---|---|
| `text` | string | requis |
| `thread_id` | string | `"default"` |

La réponse est `{"text": "..."}`.

### `GET /v1/threads/{thread_id}/tokens`

Renvoie la table placeholder vers valeur du thread, pour un client qui restaure lui-même un stream.

```json
{"tokens": {"<<PERSON:1>>": "Jane Doe", "<<EMAIL:1>>": "jane.doe@example.com"}}
```

### `DELETE /v1/threads/{thread_id}`

Efface le thread de la mémoire et indique ce qui a été supprimé. Un thread qui n'existe pas indique zéro.

```json
{"messages": 1, "detections": 2}
```

---

## Proxy compatible OpenAI

Préfixe : `/openai/v1`

| En-tête de requête | Effet |
|---|---|
| `X-PIIGhost-Upstream` | URL de base de l'upstream, `PIIGHOST_OPENAI_UPSTREAM` en son absence |
| `X-PIIGhost-Thread-Id` | Thread fixe gardé après la requête. En son absence, chaque requête reçoit un thread neuf, oublié une fois la réponse restaurée |

Seuls `Authorization`, `Content-Type`, `x-api-key`, `anthropic-version` et `anthropic-beta` sont relayés à l'upstream.

<div class="wide-table" markdown="1">

| Route | Dé-identifié dans la requête | Restauré dans la réponse |
|---|---|---|
| `POST /chat/completions` | `messages[].content`, une string ou le `text` de chaque partie, et chaque string de `messages[].tool_calls[].function.arguments` | `choices[].message.content` et `choices[].message.tool_calls[].function.arguments`, ou `choices[].delta.content` en stream |
| `POST /completions` | `prompt`, `suffix` | `choices[].text` |
| `POST /embeddings` | `input` | rien |
| `POST /moderations` | `input` | rien |
| `GET /models`, `GET /models/{model}` | relayé tel quel | relayé tel quel |
| `POST /images/generations`, `/images/edits`, `/images/variations` | relayé tel quel | relayé tel quel |
| `POST /audio/speech`, `/audio/transcriptions`, `/audio/translations` | relayé tel quel | relayé tel quel |

</div>

- Une réponse JSON réussie est restaurée, toute autre réponse est relayée telle quelle, avec le statut de l'upstream. Les en-têtes de réponse de l'upstream ne sont pas relayés.
- Les paramètres de requête n'atteignent l'upstream que sur les routes relayées telles quelles.
- Une requête `chat/completions` streamée reçoit `201` avant que l'upstream ne réponde, donc une erreur de l'upstream arrive dans le corps du stream.
- Le délai d'attente de l'upstream est de 60 secondes.

---

## Proxy compatible Anthropic

Préfixe : `/anthropic/v1`

| En-tête de requête | Effet |
|---|---|
| `X-PIIGhost-Upstream` | URL de base de l'upstream, `PIIGHOST_ANTHROPIC_UPSTREAM` en son absence |
| `X-PIIGhost-Thread-Id` | Thread fixe gardé après la requête. En son absence, chaque requête reçoit un thread neuf, oublié une fois la réponse restaurée |

Chaque en-tête de requête est relayé sauf ceux de saut à saut (`Connection`, `Keep-Alive`, `Proxy-Authenticate`, `Proxy-Authorization`, `TE`, `Trailer`, `Transfer-Encoding`, `Upgrade`), `Host`, `Content-Length`, `Accept-Encoding` et tout en-tête `X-PIIGhost-*`. Les paramètres de requête sont relayés.

<div class="wide-table" markdown="1">

| Route | Dé-identifié dans la requête | Restauré dans la réponse |
|---|---|---|
| `POST /messages` | `messages[].content`, une string ou ses blocs `text`, `tool_use` et `tool_result`, plus `system` quand `PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM` est active | les blocs `text`, `tool_use` et `tool_result` de `content`, ou le `text_delta` et l'`input_json_delta` de chaque événement `content_block_delta` en stream |
| `POST /messages/count_tokens` | comme `/messages` | rien, le décompte est relayé |

</div>

- Chaque string d'une entrée `tool_use` est réécrite. Tout autre bloc, dont une image ou un document, et les définitions de `tools` sont relayés intacts.
- La note de guidage posée par `PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` est ajoutée après la dé-identification, en tête du prompt système ou du premier message utilisateur selon `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT`.
- La réponse garde le statut de l'upstream et ses en-têtes de réponse, `retry-after` et `anthropic-ratelimit-*` compris, sauf ceux de longueur, d'encodage, de connexion et de type de contenu.
- Une requête streamée que l'upstream refuse reçoit le statut de l'upstream dans une réponse ordinaire. Une requête acceptée est streamée avec `200`.
- Le délai d'attente de l'upstream est de 60 secondes.

---

## Voir aussi

- [CLI du serveur](api-cli.md) : les options de `serve` et chaque variable d'environnement.
- [Déployer une API de dé-identification](../getting-started/api-server.md) : un premier serveur, pas à pas.
- [Proxy compatible OpenAI](../examples/openai-proxy.md) et [Proxy compatible Anthropic](../examples/anthropic-proxy.md) : les proxys à l'usage.
