---
icon: lucide/server
---

# Déployer une API de dé-identification

Vous allez lancer `piighost-api`, le serveur compagnon de `piighost`, sur une configuration publiée sur le [hub piighost](https://hub.piighost.dev), puis dé-identifier et restaurer un message en HTTP. Tout processus qui parle HTTP partage alors un seul pipeline, chargé une fois, avec la mémoire de conversation tenue par le serveur.

La configuration `hub:piighost/support-en:286909f6` repère les noms, les adresses et les organisations avec le modèle GLiNER2 `fastino/gliner2-multi-v1`, les identifiants américains et les valeurs génériques comme les emails avec des regex, et refuse de rendre un texte dé-identifié qui contient encore une adresse email en clair.

!!! note "Prérequis"
    Python 3.12 ou plus récent, et un accès réseau au hub et à Hugging Face pour le premier démarrage. Les exemples supposent le serveur sur `http://127.0.0.1:8000`.

## 1. Installer le serveur

L'extra `gliner2` apporte le moteur du modèle dont la configuration a besoin.

=== "uv"

    ```bash
    uv add "piighost-api[gliner2]"
    ```

=== "pip"

    ```bash
    pip install "piighost-api[gliner2]"
    ```

## 2. Créer une clé d'API

Le serveur refuse de démarrer sans clé d'API. `keyshield`, installé avec le serveur, génère une clé et le pepper qui la hache en mémoire.

```bash
keyshield generate
keyshield pepper
```

Chaque commande imprime une ligne de cette forme, avec vos propres valeurs :

```text
Set in your .env : "API_KEY_DEV=ak_v1-..."
Set in your .env : "SECRET_PEPPER=..."
```

Exportez les deux dans le shell qui lancera le serveur :

```bash
export API_KEY_DEV="ak_v1-..."
export SECRET_PEPPER="..."
```

## 3. Démarrer le serveur

```bash
piighost-api serve --config hub:piighost/support-en:286909f6
```

Au premier démarrage, le serveur récupère la configuration sur le hub et la garde dans le cache disque, puis télécharge le modèle GLiNER2. Le journal affiche `API keys loaded, auth enabled`, puis `Pipeline ready: piighost/support-en:286909f6 (detector: composite)`, et uvicorn écoute sur `http://127.0.0.1:8000`.

Vérifiez-le depuis un autre shell :

```bash
curl http://127.0.0.1:8000/health
```

La sortie doit être :

```json
{"status":"ok","detector":"composite"}
```

!!! tip "Sans modèle"
    Une configuration en regex seules démarre sans rien télécharger d'autre que la configuration. `piighost-api serve --config hub:piighost/fr-default:e6990159` sert la configuration française, numéros de téléphone, IBAN, NIR, SIREN et emails entre autres.

## 4. Dé-identifier un message

Envoyez un texte et un `thread_id` à `/v1/anonymize`, avec la clé dans l'en-tête `Authorization`.

```bash
curl -X POST http://127.0.0.1:8000/v1/anonymize \
  -H "Authorization: Bearer $API_KEY_DEV" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hi, I am Jane Doe, write to jane.doe@example.com.", "thread_id": "demo"}'
```

Le serveur répond `201 Created` avec un corps de cette forme :

```json
{
  "anonymized_text": "Hi, I am <<PERSON:1>>, write to <<EMAIL:1>>.",
  "entities": [
    {
      "label": "PERSON",
      "placeholder": "<<PERSON:1>>",
      "detections": [
        {"text": "Jane Doe", "label": "PERSON", "start_pos": 9, "end_pos": 17, "confidence": 0.9999873638153076}
      ]
    },
    {
      "label": "EMAIL",
      "placeholder": "<<EMAIL:1>>",
      "detections": [
        {"text": "jane.doe@example.com", "label": "EMAIL", "start_pos": 28, "end_pos": 48, "confidence": 1.0}
      ]
    }
  ]
}
```

`Jane Doe`{ .pii } devient `<<PERSON:1>>`{ .placeholder } et `jane.doe@example.com`{ .pii } devient `<<EMAIL:1>>`{ .placeholder }. La détection `PERSON` et sa confiance viennent du modèle, donc vos valeurs peuvent différer. L'email vient d'une regex, avec une confiance de `1.0`.

## 5. Restaurer la réponse

Envoyez un texte qui porte les placeholders à `/v1/deanonymize`, sous le même `thread_id`. Ici, c'est une réponse qu'un modèle aurait pu écrire.

```bash
curl -X POST http://127.0.0.1:8000/v1/deanonymize \
  -H "Authorization: Bearer $API_KEY_DEV" \
  -H "Content-Type: application/json" \
  -d '{"text": "Thanks <<PERSON:1>>, I will write to <<EMAIL:1>>.", "thread_id": "demo"}'
```

La sortie doit être :

```json
{"text":"Thanks Jane Doe, I will write to jane.doe@example.com."}
```

Le serveur restaure chaque placeholder émis par le thread `demo`, quel que soit le texte qui le porte.

## 6. L'appeler depuis Python

`PIIGhostClient` pilote les mêmes routes depuis Python, avec la clé dans ses `headers`.

```python
import asyncio
import os

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    headers = {"Authorization": f"Bearer {os.environ['API_KEY_DEV']}"}
    async with PIIGhostClient("http://127.0.0.1:8000", headers=headers) as client:
        result = await client.anonymize("Hi, I am Jane Doe.", "demo")
        print(result.text)


asyncio.run(main())
```

La sortie doit être :

```text
Hi, I am <<PERSON:1>>.
```

`Jane Doe`{ .pii } garde `<<PERSON:1>>`{ .placeholder }, le token que le thread `demo` lui a donné à l'étape 4. Le client et ses intégrations sont décrits dans [Client distant](api-client.md).

## Comment ça marche

Le serveur charge un seul pipeline conversationnel au démarrage et exécute chaque route dessus. Une configuration qui ne déclare pas de section `[memory]`, comme les deux configurations du hub de cette page, est servie avec la mémoire in-process, donc les threads vivent dans le processus du serveur et disparaissent quand il s'arrête. Pour les garder d'un redémarrage à l'autre, ou les partager entre plusieurs instances, déclarez une mémoire Redis, comme le montre [Déployer un pipeline en production](../deployment.md).

## Et ensuite

- Pour faire passer un client OpenAI ou Anthropic par le serveur, voir [Proxy compatible OpenAI](../examples/openai-proxy.md) et [Proxy compatible Anthropic](../examples/anthropic-proxy.md).
- Pour consulter chaque route et ses champs, voir [Endpoints de l'API](../reference/api-endpoints.md).
- Pour consulter chaque option et variable d'environnement du serveur, voir [CLI du serveur](../reference/api-cli.md).
- Pour lancer le serveur dans Docker avec une mémoire partagée, voir [Déployer un pipeline en production](../deployment.md).
