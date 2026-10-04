---
icon: lucide/terminal
---

# Hooks Claude Code

Vous ne pouvez pas pointer Claude Code vers le proxy compatible OpenAI, parce qu'il parle l'API Messages d'Anthropic, pas la forme OpenAI. À la place, `piighost` se branche sur le système de hooks propre à Claude Code. Un hook est une petite commande que Claude Code exécute à un moment fixe d'un tour. Les hooks dé-identifient ce que le modèle voit et restaurent les vraies valeurs là où elles sont réellement nécessaires, sans toucher au code de votre agent. L'autre voie est le [proxy compatible Anthropic](anthropic-proxy.md), branché par l'URL de base de Claude Code.

Trois hooks couvrent un tour :

- **`UserPromptSubmit`** dé-identifie votre prompt avant que le modèle ne le lise.
- **`PostToolUse`** dé-identifie la sortie d'un outil avant que le modèle ne la lise.
- **`PreToolUse`** restaure les vraies valeurs dans l'entrée d'un outil avant que l'outil ne s'exécute.

Ainsi le modèle ne voit que des placeholders comme `<<PERSON:1>>`, tandis que les outils qui s'exécutent vraiment (Bash, Read, Edit, ...) reçoivent les vraies valeurs. Le `session_id` de Claude Code nomme la conversation de dé-identification, donc une valeur garde le même jeton sur toute la session.

!!! note "Prérequis"
    `piighost` installé avec l'extra client, `pip install "piighost[client]"`, et un serveur `piighost-api` en cours d'exécution, voir [Serveur d'API](../getting-started/api-server.md). Le hook est un client léger. Il transmet chaque événement à l'API, qui possède le pipeline et la mémoire de conversation. Le hook n'envoie aucune clé d'API. Démarrez donc le serveur avec `PIIGHOST_ALLOW_ANONYMOUS=true`, et gardez-le sur un hôte que vous seul pouvez joindre.

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

Le même bloc est fourni comme `settings.template.json` dans le paquet de l'intégration. Lancez `claude` comme d'habitude. Les hooks se déclenchent automatiquement.

## Le pointer vers votre serveur

Le hook parle à `piighost-api` sur `http://localhost:8000` par défaut. Surchargez avec une variable d'environnement :

```bash
export PIIGHOST_API_URL="https://piighost.internal:8000"
```

Quand le hook ne peut pas dé-identifier, parce que le serveur est arrêté ou que l'événement n'a pas d'identifiant de session, il bloque par défaut. Un prompt ou un appel d'outil est bloqué, et Claude Code affiche la raison. Une sortie d'outil est déjà produite, donc le hook la remplace par un avis. Pour laisser passer le texte en clair plutôt que bloquer, dans une session où la disponibilité compte plus que la protection, réglez :

```bash
export PIIGHOST_HOOK_FAIL_OPEN=1
```

Pour observer ce que fait le hook, réglez `PIIGHOST_HOOK_LOG` sur un chemin de fichier. Le point d'entrée du hook ajoute un enregistrement JSON par événement (l'événement, l'outil, l'identifiant de session, et la mutation renvoyée) :

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

## Quels champs sont dé-identifiés

Un prompt et une entrée d'outil sont assez simples pour être dé-identifiés en entier. La sortie d'un outil, elle, est un objet structuré où seuls certains champs contiennent du texte destiné au modèle. Le hook `PostToolUse` ne dé-identifie donc pas tout l'objet, pour ne jamais abîmer un chemin, un code de sortie, ou un numéro de ligne. Il dé-identifie une liste blanche de champs texte par outil :

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

    Un outil absent de la liste, ou une sortie dont la forme est inattendue, passe sans modification. Son texte atteint donc le modèle en clair. Le manque notable est `Grep`, que la liste ne couvre pas encore. Ses correspondances sont des lignes des fichiers parcourus. En attendant, gardez `Grep` hors de la session ou étendez la liste comme décrit plus bas.

## Découvrir la forme d'un nouvel outil

Pour étendre la liste blanche à un outil qu'elle ne couvre pas encore, définissez `PIIGHOST_HOOK_LOG` comme plus haut avant de lancer Claude Code. Le journal contient chaque appel de hook. Une sortie d'outil que le hook a laissée passer y figure en entier, et vous y voyez donc les vrais noms de champs.

Sollicitez l'outil, lisez le log pour trouver quels champs portent le texte, et ajoutez l'outil à la liste blanche dans l'intégration. Le log contient du texte en clair. Supprimez-le ensuite.

## L'utiliser par programmation

L'API publique tient en deux fonctions. `handle_hook(event, pipeline)` est un dispatch pur. Il prend un événement parsé et n'importe quel pipeline de conversation (un `ThreadAnonymizationPipeline` local ou un `PIIGhostClient` distant). Il renvoie l'enveloppe de mutation, ou `None` pour laisser passer. `run()` est le point d'entrée stdin/stdout que le module invoque. Pilotez `handle_hook` directement pour tester le comportement ou l'intégrer dans votre propre point d'entrée.
