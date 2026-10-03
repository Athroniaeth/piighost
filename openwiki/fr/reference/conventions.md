---
type: reference
title: Conventions et choix techniques
description: Les conventions que suit PIIGhost sans qu'un besoin les impose directement, la forme des jetons, la détection, la sécurité par défaut, la restauration, le stockage et l'architecture, avec la raison de chacune et l'endroit du code où elle vit.
tags: [conventions, decisions, placeholder, detection, security]
generated: { by: "claude-code", at: "2026-10-03T18:00:00.000Z" }
---

# Conventions et choix techniques

## En bref

Écrire PIIGhost a demandé des choix que rien n'impose de l'extérieur, comme la forme d'un jeton ou le comportement d'un réglage par défaut. Cette page les rassemble pour qu'ils ne restent pas implicites. Pour chacun, elle donne la raison du choix et l'endroit du code où il s'applique, et cite la règle de gestion qu'il soutient quand il y en a une. Ces conventions engagent le reste de la librairie, donc en changer une demande d'en discuter d'abord.

## Les jetons

- **Délimiteurs `<<` et `>>`** : un jeton est encadré par deux chevrons doublés. Cette suite est rare dans un texte ordinaire, donc un jeton se retrouve facilement par une expression régulière. Elle signale aussi au modèle qu'il lit une donnée masquée. Code, `components/placeholder/streaming.py` (`DEFAULT_PREFIX`, `DEFAULT_SUFFIX`).
- **Forme `<<LABEL:n>>`** : le label dit au modèle de quoi il s'agit, une personne ou un e-mail par exemple. Le numéro distingue les individus d'un même type. Il commence à 1 pour chaque label, dans l'ordre d'apparition. Code, `components/placeholder/label_counter.py`.
- **Grammaire d'un jeton** : un label commence par une lettre ou `_`, puis contient des lettres, des chiffres, `_`, des espaces ou des tirets. Un label de plusieurs mots, comme en émet un modèle NER, est donc accepté. L'identifiant après les deux-points est alphanumérique. Code, `components/placeholder/streaming.py` (`LABEL_INNER`).
- **Jeton haché** : la forme `<<PERSON:6b86b273>>` est l'empreinte SHA-256 de « label:rang », jamais de la valeur. Elle ne cache aucun secret, et on ne peut rien en déduire sur la valeur. Code, `components/placeholder/label_hash.py`.
- **Même jeton sur toute la conversation** : une valeur garde son jeton d'un message à l'autre, et chaque conversation a ses propres jetons. Le modèle peut ainsi suivre qui est qui. Code, `pipeline/thread.py`. Règle BR-MSG-02.
- **Identité retrouvable** : le middleware refuse, dès sa construction, une forme de jeton qui ne distingue pas les individus, comme `<<PERSON>>`. Sans identité, une valeur ne pourrait pas être restaurée. Code, `components/placeholder/tags.py` (`PreservesRecognizableIdentity`).

## La détection

- **Pas de validation par clé de contrôle** : une carte ou un IBAN est masqué sur sa seule forme. Une valeur abîmée par la reconnaissance de caractères reste ainsi détectée, au prix de quelques faux positifs. Code, `components/detector/regex.py`. Règle BR-MSG-07.
- **Expressions régulières en ASCII** : `\d` ne reconnaît que les chiffres 0 à 9, et la forme d'une valeur reste prévisible. Code, `components/detector/regex.py` (`re.ASCII`).
- **Espaces Unicode normalisées** : toute espace Unicode, insécable ou fine, compte comme une espace ordinaire. La longueur du texte ne change pas, donc les positions restent justes. Code, `text/normalization.py` (`normalize_spaces`). Règle BR-MSG-06.
- **Une valeur, quelles que soient ses espaces et sa casse** : « Jean  Dupont » et « jean dupont » reçoivent le même jeton. Code, `text/normalization.py` (`value_key`). Règle BR-MSG-02.
- **Recherche par mot entier** : « Jean » n'est pas trouvé dans « Jeanne ». Un trait d'union Unicode relie deux mots. Code, `text/boundaries.py`.
- **Chevauchements toujours arbitrés** : le résolveur ne se désactive pas, parce que le remplacement suppose des passages disjoints. La détection la plus sûre gagne, et à égalité, le premier détecteur déclaré. Code, `components/overlap_resolver/`. Règle BR-MSG-05.
- **Pas de positions venant d'un LLM** : un détecteur LLM nomme des valeurs, et PIIGhost les recherche lui-même dans le texte. Une valeur inventée par le modèle, absente du texte, est donc ignorée. Le texte envoyé est encadré de balises, et une balise présente dans le texte est neutralisée. Code, `components/detector/llm.py`.

## La sécurité par défaut

Chaque réglage par défaut choisit le côté qui protège. Un réglage explicite permet le contraire.

- **Jeton tapé par l'utilisateur neutralisé** : un caractère invisible (U+200B) est inséré dans le texte, pour qu'un utilisateur ne fasse pas apparaître la valeur d'un autre. Code, `components/anonymizer/span.py`. Règle BR-MSG-09.
- **Jeton inventé par le modèle refusé** : un jeton au bon format jamais émis bloque la réponse, plutôt que d'être affiché ou retiré en silence. Règles BR-CONV-06 et BR-TOOL-07.
- **Identifiant de conversation obligatoire** : un appel sans identifiant échoue, au lieu de partager une conversation commune. Règle BR-AGT-01.
- **Détecteur en panne qui refuse le message** : une sortie illisible d'un détecteur LLM bloque le message, et les hooks Claude Code bloquent si le serveur ne répond pas. Besoin DPO-9.
- **Mémoire bornée** : la mémoire du processus garde au plus 10 000 conversations, et oublie une conversation après un jour sans activité. Code, `conversation_memory/memory.py`. Règles BR-STO-04 et BR-CONV-11.

## La restauration

- **Du jeton le plus long au plus court** : `<<PERSON:1>>` ne remplace pas le début de `<<PERSON:10>>`. Code, `components/anonymizer/base.py`.
- **Jeton coupé pendant le flux** : un jeton coupé entre deux morceaux est retenu jusqu'à ce qu'il soit complet, dans la limite de 128 caractères. Un `<` isolé en fin de morceau est retenu aussi. Code, `components/placeholder/streaming.py`. Règles BR-STREAM-03 et BR-STREAM-04.
- **Vraie valeur aux outils** : par défaut, un outil reçoit la vraie valeur, et le modèle ne voit que le jeton. Code, `integrations/langchain/middleware.py` (`ToolCallStrategy.FULL`).
- **Valeur introduite par l'assistant** : par défaut, une valeur que le modèle écrit de lui-même est gardée telle quelle. Code, `integrations/langchain/middleware.py` (`EntityCreateByAssistantStrategy.PRESERVE`).

## Le stockage et la configuration

- **Clés hachées et valeurs chiffrées** : avec Redis, les clés passent par HMAC puis Argon2id avec un poivre, et les valeurs sont chiffrées en AES-GCM. L'identifiant de conversation reste lisible, pour qu'on puisse effacer une conversation. Code, `crypto/` et `conversation_memory/redis_backend.py`. Règle BR-STO-03.
- **Secrets dans l'environnement seulement** : le poivre et la clé de chiffrement ne s'écrivent jamais dans un fichier de configuration. Code, `config/`.
- **Références du hub** : une référence épinglée sur un commit est mise en cache. Un tag ou `latest` est relu à chaque fois, pour ne jamais servir une version périmée. Code, `hub.py`.

## L'architecture

- **Tout est asynchrone** : les détecteurs à modèle et les serveurs distants le sont, et le pipeline les attend sans bloquer.
- **Un port par étape** : chaque étape a une interface, et la plupart ont un modèle de base. Seul le détecteur est obligatoire. Voir [Ajouter ou remplacer un composant](../architecture/ports-and-extension.md).
- **Configuration couplée dans un seul sens** : la configuration connaît le cœur de la librairie, jamais l'inverse. Code, `config/`.
- **Cœur sans règle propre à une langue** : les listes de mots français ou métier vont dans les groupes du hub, pas dans la librairie.

Les termes sont définis dans le [glossaire](../glossary.md).
