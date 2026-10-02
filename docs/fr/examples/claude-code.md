---
icon: lucide/terminal
---

# Dé-identifier Claude Code avec les hooks

Claude Code parle l'API Messages d'Anthropic, pas la forme OpenAI, donc vous ne pouvez pas le pointer vers le proxy compatible OpenAI. À la place, `piighost` se branche sur le système de hooks propre à Claude Code, de petites commandes que le harness exécute à des moments fixes d'un tour. Les hooks dé-identifient ce que le modèle voit et restaurent les vraies valeurs là où elles sont réellement nécessaires, sans toucher au code de votre agent. Le [proxy compatible Anthropic](anthropic-proxy.md) est l'autre voie, par l'URL de base de Claude Code.

Trois hooks couvrent un tour :

- **`UserPromptSubmit`** dé-identifie votre prompt avant que le modèle ne le lise.
- **`PostToolUse`** dé-identifie la sortie d'un outil avant que le modèle ne la lise.
- **`PreToolUse`** restaure les vraies valeurs dans l'entrée d'un outil avant que l'outil ne s'exécute.

Ainsi le modèle ne voit que des placeholders comme `<<PERSON:1>>`, tandis que les outils qui s'exécutent vraiment (Bash, Read, Edit, ...) reçoivent les vraies valeurs. Le `session_id` de Claude Code nomme la conversation de dé-identification, donc une valeur garde le même jeton sur toute la session.

!!! note "Prérequis"
    `piighost` installé avec l'extra client, `pip install piighost[client]`, et un serveur `piighost-api` en cours d'exécution, voir [Déployer une API de dé-identification](../getting-started/api-server.md). Le hook est un client léger, il transmet chaque événement à l'API, qui possède le pipeline et la mémoire de conversation. Il n'envoie aucune clé d'API, donc démarrez le serveur avec `PIIGHOST_ALLOW_ANONYMOUS=true` et gardez-le sur un hôte que vous seul pouvez joindre.

## Brancher les hooks

Chaque invocation de hook exécute `python -m piighost.integrations.claude_code`. Elle lit un événement de hook en JSON sur stdin et réécrit la mutation en JSON sur stdout. Fusionnez ceci dans votre `.claude/settings.json` :

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python -m piighost.integrations.claude_code"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m piighost.integrations.claude_code"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m piighost.integrations.claude_code"
          }
        ]
      }
    ]
  }
}
```

Le même snippet est fourni comme `settings.template.json` dans le paquet de l'intégration. Lancez `claude` comme d'habitude. Les hooks se déclenchent automatiquement.

## Le pointer vers votre serveur

Le hook parle à `piighost-api` sur `http://localhost:8000` par défaut. Surchargez avec une variable d'environnement :

```bash
export PIIGHOST_API_URL="https://piighost.internal:8000"
```

Pour observer ce que fait le hook, réglez `PIIGHOST_HOOK_LOG` sur un chemin de fichier. Le runner ajoute un enregistrement JSON par événement (l'événement, l'outil, l'identifiant de session, et la mutation renvoyée) :

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

## Quels champs sont dé-identifiés

Un prompt et une entrée d'outil sont assez simples pour être dé-identifiés en entier, mais la sortie d'un outil est un objet structuré où seuls certains champs contiennent du texte destiné au modèle. Le hook `PostToolUse` dé-identifie donc une liste blanche de champs texte par outil plutôt que tout le payload, pour ne jamais abîmer un chemin, un code de sortie, ou un numéro de ligne :

| Outil | Champs dé-identifiés |
|-------|-------------------|
| `Bash` | `stdout`, `stderr` |
| `Read` | `file.content` |
| `Write` | `content`, `originalFile`, lignes du patch |
| `Edit` | `oldString`, `newString`, `originalFile`, lignes du patch |
| `Agent` | texte du message |
| `WebFetch` | `result` |
| `WebSearch` | titres des résultats |
| `ToolSearch` | `query` |

!!! warning "La liste blanche laisse passer par défaut"

    Un outil absent de la liste, ou une sortie dont la forme est inattendue, passe sans modification, donc son texte atteint le modèle en clair. `Grep` est le manque notable, ses correspondances étant des lignes des fichiers parcourus, et la liste ne le couvre pas encore. En attendant, gardez `Grep` hors de la session ou étendez la liste comme décrit plus bas.

## Découvrir la forme d'un nouvel outil

Pour étendre la liste blanche à un outil qu'elle ne couvre pas encore, définissez `PIIGHOST_HOOK_LOG` avant de lancer Claude Code. Le runner journalise alors chaque appel de hook dans un fichier JSONL, et une sortie d'outil qu'il a laissée passer y figure en entier, ce qui vous laisse voir les vrais noms de champs :

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

Sollicitez l'outil, lisez le log pour trouver quels champs portent le texte, et ajoutez l'outil à la liste blanche dans l'intégration. Le log contient du texte en clair, supprimez-le ensuite.

## L'utiliser par programmation

L'API publique tient en deux fonctions. `handle_hook(event, pipeline)` est un dispatch pur qui prend un événement parsé et n'importe quel pipeline de conversation (un `ThreadAnonymizationPipeline` local ou un `PIIGhostClient` distant) et renvoie l'enveloppe de mutation, ou `None` pour laisser passer. `run()` est le point d'entrée stdin/stdout que le module invoque. Pilotez `handle_hook` directement pour tester le comportement ou l'intégrer dans votre propre runner.
