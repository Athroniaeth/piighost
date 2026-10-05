---
icon: lucide/terminal
---

# Référence de la CLI du serveur

Paquet : `piighost-api`

`piighost-api` est la ligne de commande du serveur compagnon. `serve` démarre le serveur HTTP. Les commandes `dataset` construisent et notent un jeu de détections à partir des traces d'observation.

```text
piighost-api serve [--config SOURCE] [--host HOST] [--port PORT] [--log-level LEVEL]
piighost-api dataset extract --output FILE [--since DATE] [--until DATE] [--mode MODE] [--limit N]
piighost-api dataset metrics --input FILE [--output FILE] [--output-format FORMAT] [--match-mode MODE] [--iou-threshold FLOAT] [--source SOURCE]
```

Le serveur demande Python 3.12 ou plus récent et `piighost>=2.0,<3`. Ses extras ajoutent des fonctions optionnelles :

| Extra | Ajoute |
|---|---|
| `gliner2` | `piighost[gliner2]`, pour une configuration qui exécute un détecteur GLiNER2 |
| `observation` | le SDK OpenTelemetry et l'exporteur OTLP, pour exporter les traces |
| `dataset` | le SDK Langfuse et `python-dotenv`, pour `dataset extract` |

Le serveur n'est pas publié sur PyPI. Dans l'image Docker `ghcr.io/athroniaeth/piighost-api`, la variable `EXTRA_PACKAGES` installe des paquets au démarrage du conteneur, par exemple l'extra `gliner2` :

```bash
docker run -p 8000:8000 -e EXTRA_PACKAGES="piighost[gliner2]" ghcr.io/athroniaeth/piighost-api:latest
```

Depuis un clone du dépôt, `uv sync` installe les extras choisis :

```bash
uv sync --extra gliner2 --extra observation
```

---

## `piighost-api serve`

Construit le pipeline une fois et sert les [endpoints de l'API](api-endpoints.md) avec uvicorn, dans un seul processus.

```bash
piighost-api serve --config catalog:piighost/support-en --host 0.0.0.0 --port 8000
```

| Option | Défaut | Description |
|---|---|---|
| `--config`, `-c` | `PIIGHOST_CONFIG` | Un fichier de config de pipeline TOML ou JSON, ou une référence du catalogue comme `catalog:piighost/support-en` |
| `--host` | `127.0.0.1` | Hôte d'écoute |
| `--port` | `8000` | Port d'écoute |
| `--log-level` | `info` | `debug`, `info`, `warning` ou `error` |

- Sans `--config` ni `PIIGHOST_CONFIG`, la commande imprime `Missing --config or PIIGHOST_CONFIG.` avec une indication d'usage et sort en `1`. Un chemin de fichier qui n'existe pas sort en `1` avec `Configuration file not found:`.
- Une référence du catalogue charge la configuration complète que le [catalogue piighost](https://catalog.piighost.dev) publie sous ce nom. Une référence épinglée à un commit est récupérée au premier démarrage, puis lue dans le cache disque.
- Une configuration qui ne déclare pas de section `[memory]` est servie avec la mémoire in-process, `in_memory`. Ses conversations vivent dans le processus du serveur, donc chaque instance tient les siennes. Plusieurs instances derrière un load balancer demandent une mémoire `redis` ou `sqlalchemy` partagée, voir [Déploiement multi-instance](../multi-instance.md).
- Toute section de premier niveau se surcharge avec une variable `PIIGHOST_` qui porte un objet JSON, comme pour un fichier, voir [Surcharges d'environnement](../configuration/toml.md). `PIIGHOST_MEMORY` ajoute ainsi une mémoire partagée à une configuration du catalogue. Celle de l'exemple ci-dessous demande `piighost[crypto]` pour son cipher.
- Sans clé dans une variable `API_KEY_`, le serveur refuse de démarrer sauf si `PIIGHOST_ALLOW_ANONYMOUS` est posée.

```bash
export PIIGHOST_MEMORY='{"type": "redis", "url": "redis://redis:6379/0", "hasher": {"type": "argon2"}, "cipher": {"type": "aesgcm"}}'
piighost-api serve --config catalog:piighost/support-en
```

---

## Variables d'environnement

<div class="wide-table" markdown="1">

| Variable | Défaut | Effet |
|---|---|---|
| `PIIGHOST_CONFIG` | aucun | Fichier de config ou référence du catalogue, lu quand `--config` est absent |
| `API_KEY_<NAME>` | aucun | Une clé d'API acceptée par variable. La valeur est celle qu'imprime `keyshield generate` |
| `SECRET_PEPPER` | le poivre intégré de `keyshield`, avec un avertissement | Poivre du hash Argon2 que le serveur garde de chaque clé, imprimé par `keyshield pepper` |
| `PIIGHOST_ALLOW_ANONYMOUS` | désactivé | `1`, `true`, `yes` ou `on` laisse le serveur démarrer sans clé, chaque route est alors ouverte. S'applique aussi quand les clés échouent à se charger |
| `PIIGHOST_MAX_BODY_BYTES` | `1000000` | Plus grand corps de requête accepté, au-delà `413` |
| `PIIGHOST_RATE_LIMIT` | désactivé | `<unit>:<count>` par client, `unit` parmi `second`, `minute`, `hour`, `day`, comme `minute:300`. Une valeur mal formée arrête le serveur au démarrage |
| `PIIGHOST_OPENAI_UPSTREAM` | `https://api.openai.com/v1` | Upstream de `/openai/v1` quand une requête n'en nomme aucun |
| `PIIGHOST_ANTHROPIC_UPSTREAM` | `https://api.anthropic.com/v1` | Upstream de `/anthropic/v1` quand une requête n'en nomme aucun |
| `PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM` | `false` | `1`, `true`, `yes` ou `on` dé-identifie aussi le prompt système |
| `PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` | vide, pas de note | `default` ajoute la note intégrée sur les placeholders. Tout autre texte sert lui-même de note |
| `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT` | `system` | `user` place la note dans le premier message utilisateur, toute autre valeur dans le prompt système |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_ENDPOINT` | aucun | Un endpoint OTLP active l'export des traces. Si les deux sont posées, la première de la liste l'emporte. Demande l'extra `observation` |
| `OTEL_SERVICE_NAME` | `piighost-api` | Nom de service des traces exportées |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | aucun | Identifiants de `dataset extract` |

</div>

Le pipeline lit ses propres secrets (`PIIGHOST_HASH_PEPPER`, `PIIGHOST_CIPHER_KEY`, `PIIGHOST_DATABASE_URL` et `MISTRAL_API_KEY`). `PIIGHOST_CATALOG_URL` nomme un catalogue privé. Ces variables sont listées dans la [Référence TOML](../configuration/toml.md). Les autres variables `OTEL_*`, en-têtes compris, sont lues par l'exporteur OpenTelemetry lui-même, voir [Observation](../observation.md).

L'image Docker en lit quatre de plus, listées dans [Déployer un pipeline en production](../deployment.md).

---

## `piighost-api dataset extract`

Lit des traces sur Langfuse et écrit un enregistrement JSONL par trace. Il demande l'extra `dataset` ainsi que `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY`, lues dans l'environnement ou dans un fichier `.env` du répertoire courant. Sans elles, il sort en `1`.

```bash
piighost-api dataset extract --output dataset.jsonl --since 2026-09-01 --limit 1000
```

| Option | Défaut | Description |
|---|---|---|
| `--output`, `-o` | requis | Fichier JSONL à écrire |
| `--since` | aucun | Ignore les traces antérieures à cette date, `%Y-%m-%d`, `%Y-%m-%dT%H:%M:%S` ou `%Y-%m-%d %H:%M:%S` |
| `--until` | aucun | Ignore les traces postérieures à cette date, mêmes formats |
| `--mode` | `all` | `hitl`, `model-only` ou `all` |
| `--limit` | aucun | S'arrête après ce nombre d'enregistrements |

| `--mode` | Nom de trace lu | `entities` tiré de |
|---|---|---|
| `hitl` | `piighost.hitl_correction` | les `detections` de la sortie de la trace, la correction humaine |
| `model-only` | `piighost.anonymize` | les `detections` de sortie de son enfant `piighost.detect` |
| `all` | les deux | selon la trace |

!!! warning
    Aucune route du serveur n'émet `piighost.hitl_correction`, donc `hitl` ne trouve aucune trace. Un message corrigé est tracé comme `piighost.anonymize`, comme tout autre, et `model-only` le lit comme une trace du modèle.

Une trace sans texte d'entrée, ou une trace de modèle sans son enfant `piighost.detect`, est ignorée. La commande se termine par `Wrote N records to FILE (M skipped).`

```json
{
  "text": "Hi Jane Doe, from Acme in Boston",
  "entities": [[3, 11, "PERSON"], [18, 22, "ORGANIZATION"], [26, 32, "LOCATION"]],
  "model_entities": [[3, 11, "PERSON"], [18, 22, "LOCATION"]],
  "labels_universe": [],
  "source": "hitl",
  "trace_id": "...",
  "session_id": "...",
  "created_at": "..."
}
```

| Champ | Contenu |
|---|---|
| `entities` | Les spans de référence en `[start, end, label]`. C'est la correction humaine pour un enregistrement `hitl`, et la sortie du modèle pour un enregistrement `model` |
| `model_entities` | Les spans du modèle, égaux à `entities` sur un enregistrement `model` |
| `labels_universe` | Les `labels` de l'entrée d'une trace de correction, vide sur un enregistrement `model` |
| `source` | `hitl` ou `model` |

---

## `piighost-api dataset metrics`

Note le modèle contre la référence d'un fichier JSONL écrit par `dataset extract`, label par label. Il ne demande aucun extra.

```bash
piighost-api dataset metrics --input dataset.jsonl
```

| Option | Défaut | Description |
|---|---|---|
| `--input`, `-i` | requis | Fichier JSONL à lire |
| `--output`, `-o` | stdout | Fichier où écrire le rapport |
| `--output-format` | `table` | `table`, `csv` ou `json` |
| `--match-mode` | `strict` | `strict` exige le même span et le même label, `lenient` accepte un span de même label dont le taux de recouvrement atteint `--iou-threshold` |
| `--iou-threshold` | `0.5` | Seuil de recouvrement en mode `lenient` |
| `--source` | `all` | `hitl`, `model` ou `all`, les enregistrements à noter |

Sur l'enregistrement ci-dessus, le tableau est :

```text
label                    tp     fp     fn      P      R     F1
--------------------------------------------------------------
LOCATION                  0      1      1   0.00   0.00   0.00
ORGANIZATION              0      0      1   0.00   0.00   0.00
PERSON                    1      0      0   1.00   1.00   1.00
--------------------------------------------------------------
macro avg                 -      -      -   0.33   0.33   0.33
micro avg                 -      -      -   0.50   0.33   0.40

Label confusion (model -> human, same span):
  LOCATION -> ORGANIZATION: 1
```

`tp` compte un span du modèle que la référence contient, `fp` un span du modèle qu'elle ne contient pas, `fn` un span de référence que le modèle a manqué. `P`, `R` et `F1` sont la précision, le rappel et leur moyenne harmonique. La section de confusion liste les spans où le modèle et la référence s'accordent sur les décalages et diffèrent sur le label.

---

## Voir aussi

- [Endpoints de l'API](api-endpoints.md) : chaque route que le serveur sert.
- [Déployer une API de dé-identification](../getting-started/api-server.md) : un premier serveur, pas à pas.
- [CLI](cli.md) : la commande `piighost` de la librairie.
