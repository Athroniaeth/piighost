---
icon: lucide/terminal
seo_title: Masquer les PII dans Claude Code avec des hooks
description: Branchez piighost sur les hooks de Claude Code. Les sorties d'outils arrivent au modèle en placeholders, et les outils reçoivent les vraies valeurs. Ce que les hooks manquent, et le proxy qui le couvre.
---

# Hooks Claude Code

Vous ne pouvez pas pointer Claude Code vers le proxy compatible OpenAI, parce qu'il parle l'API Messages d'Anthropic, pas la forme OpenAI. À la place, `piighost` se branche sur le système de hooks propre à Claude Code. Un hook est une petite commande que Claude Code exécute à un moment fixe d'un tour. Les hooks dé-identifient ce que les outils renvoient au modèle et restaurent les vraies valeurs là où les outils en ont besoin, sans toucher au code de votre agent. L'autre voie est le [proxy compatible Anthropic](anthropic-proxy.md), branché par l'URL de base de Claude Code.

Trois hooks couvrent un tour :

- **`PostToolUse`** dé-identifie la sortie d'un outil avant que le modèle ne la lise.
- **`PreToolUse`** restaure les vraies valeurs dans l'entrée d'un outil avant que l'outil ne s'exécute.
- **`UserPromptSubmit`** vérifie que `piighost-api` répond, et bloque votre prompt sinon. Il ne peut pas dé-identifier le prompt, car Claude Code ne laisse aucun hook le remplacer.

Quand l'outil Read renvoie une ligne client, le modèle reçoit `<<PERSON:1>>`{ .placeholder } au lieu de `Margaret Holloway`{ .pii }. Quand le modèle écrit ensuite `<<PERSON:1>>`{ .placeholder } dans un fichier, l'outil Write reçoit `Margaret Holloway`{ .pii }. Le `session_id` de Claude Code nomme la conversation de dé-identification, donc une valeur garde le même placeholder sur toute la session.

!!! warning "Ce que les hooks laissent en clair"

    Le modèle reçoit ces éléments en clair, car aucun hook ne peut les réécrire :

    - Votre prompt. S'il nomme `Margaret Holloway`{ .pii }, le modèle lit `Margaret Holloway`{ .pii }.
    - Un fichier que vous mentionnez avec `@`, comme `@.env`. Claude Code ajoute son contenu sans appel d'outil, donc aucun hook ne le voit.
    - La sortie d'un outil absent de la liste des champs plus bas, comme un outil MCP.

    Pour dé-identifier tout ce que Claude Code envoie à Anthropic, utilisez plutôt le [proxy compatible Anthropic](anthropic-proxy.md). Il dé-identifie les messages de chaque requête, donc votre prompt, les fichiers `@` et chaque sortie d'outil arrivent chez Anthropic en placeholders.

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

## Tenir `.env` hors de portée du modèle

Le modèle a rarement besoin de la valeur d'une clé pour écrire du code. Refusez-la dans le même `.claude/settings.json` :

```json
{
  "permissions": {
    "deny": ["Read(./.env)", "Read(./.env.*)"]
  }
}
```

Ces règles bloquent l'outil Read et les commandes Bash qui nomment le fichier, comme `cat .env`. Claude Code les applique aussi à Grep, Glob et aux mentions `@`, au mieux, voir sa [page sur les permissions](https://code.claude.com/docs/fr/permissions). Elles n'arrêtent pas `grep -r` ni un script qui ouvre le fichier lui-même. Pour ces cas, Claude Code propose un [bac à sable](https://code.claude.com/docs/fr/sandboxing).

## Le pointer vers votre serveur

Le hook parle à `piighost-api` sur `http://localhost:8000` par défaut. Surchargez avec une variable d'environnement :

```bash
export PIIGHOST_API_URL="https://piighost.internal:8000"
```

Quand le hook ne peut pas dé-identifier, parce que le serveur est arrêté ou que l'événement n'a pas d'identifiant de session, il bloque par défaut, et Claude Code affiche la raison :

- Un prompt est bloqué.
- Un appel d'outil est bloqué avant que l'outil ne s'exécute.
- Une sortie d'outil existe déjà. Le hook remplace chacun de ses champs texte de la liste plus bas par un avis, et garde le reste de la sortie. Claude Code ignore un remplacement qui ne respecte pas la forme de sortie de l'outil, donc la forme doit rester.

Serveur arrêté, le modèle lit alors `[piighost could not de-identify this PostToolUse event (ConnectError: All connection attempts failed), so the tool output is withheld.]` à la place du contenu du fichier. Un outil absent de la liste ne reçoit pas d'avis, voir l'avertissement plus bas.

Pour laisser passer le texte en clair plutôt que bloquer, dans une session où la disponibilité compte plus que la protection, réglez :

```bash
export PIIGHOST_HOOK_FAIL_OPEN=1
```

Pour observer ce que fait le hook, réglez `PIIGHOST_HOOK_LOG` sur un chemin de fichier. Le point d'entrée du hook ajoute un enregistrement JSON par événement (l'événement, l'outil, l'identifiant de session, et la mutation renvoyée) :

```bash
export PIIGHOST_HOOK_LOG="$HOME/piighost-hooks.jsonl"
```

## Quels champs sont dé-identifiés

Un prompt et une entrée d'outil sont assez simples pour être dé-identifiés en entier. La sortie d'un outil, elle, est un objet structuré où seuls certains champs contiennent du texte destiné au modèle. Le hook `PostToolUse` ne dé-identifie donc pas tout l'objet, pour ne jamais abîmer un chemin, un code de sortie, ou un numéro de ligne. Il dé-identifie seulement les champs texte listés pour chaque outil :

| Outil | Champs dé-identifiés |
|-------|-------------------|
| `Bash` | `stdout`, `stderr` |
| `Read` | `file.content` |
| `Write` | `content`, `originalFile`, lignes du patch |
| `Edit` | `oldString`, `newString`, `originalFile`, lignes du patch |
| `Agent` | texte du message |
| `Grep` | `content`, les lignes trouvées |
| `WebFetch` | `result` |
| `WebSearch` | titres des résultats |
| `ToolSearch` | `query` |

!!! warning "La liste des champs laisse passer par défaut"

    Un outil absent de la liste, ou une sortie dont la forme est inattendue, passe sans modification, que le serveur réponde ou non. Son texte atteint donc le modèle en clair. Les outils MCP sont dans ce cas. Étendez la liste comme décrit plus bas, refusez l'outil dans vos permissions, ou utilisez le [proxy compatible Anthropic](anthropic-proxy.md).

## Découvrir la forme d'un nouvel outil

Pour étendre la liste des champs à un outil qu'elle ne couvre pas encore, définissez `PIIGHOST_HOOK_LOG` comme plus haut avant de lancer Claude Code. Le journal contient chaque appel de hook. Une sortie d'outil que le hook a laissée passer y figure en entier, et vous y voyez donc les vrais noms de champs.

Sollicitez l'outil, lisez le log pour trouver quels champs portent le texte, et ajoutez l'outil à la liste des champs dans l'intégration. Le log contient du texte en clair. Supprimez-le ensuite.

## L'utiliser par programmation

L'API publique tient en deux fonctions. `handle_hook(event, pipeline)` est un dispatch pur. Il prend un événement parsé et n'importe quel pipeline de conversation (un `ThreadAnonymizationPipeline` local ou un `PIIGhostClient` distant). Il renvoie l'enveloppe de mutation, ou `None` pour laisser passer. `run()` est le point d'entrée stdin/stdout que le module invoque. Pilotez `handle_hook` directement pour tester le comportement ou l'intégrer dans votre propre point d'entrée.
