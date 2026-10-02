---
type: reference
title: Registre des écarts doc / code
description: Chaque écart constaté entre la documentation existante de PIIGhost (docs/, AGENTS.md, docstrings) et le comportement du code, avec la source de chaque côté et la page du wiki concernée.
tags: [reference, documentation, discrepancies, review]
sources:
  - id: openwiki-source-ca6cb4b1a14fd7969dfae3ec
    resource: repo://CHANGELOG.md
  - id: openwiki-source-0b69b3c329609131d2e52b9b
    resource: repo://docs/en/architecture.md
  - id: openwiki-source-fa5bbad74af0c6433d558198
    resource: repo://docs/en/community/faq.md
  - id: openwiki-source-0338c20fdc4eb0eacd90211e
    resource: repo://docs/en/roadmap.md
  - id: openwiki-source-85d8e9a0caddafe5d9e86ff1
    resource: repo://docs/en/security.md
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-cf4da74160eab5c3e37887a7
    resource: repo://src/piighost/components/detector/base.py
  - id: openwiki-source-aa685735384e8973ddee846d
    resource: repo://src/piighost/components/linker/exact.py
  - id: openwiki-source-6f090348d19a69e9634505fd
    resource: repo://src/piighost/components/override/base.py
  - id: openwiki-source-6b7f5f02702990f6448a1a5f
    resource: repo://src/piighost/components/override/detector.py
  - id: openwiki-source-bbc55964bae79b175f6d8646
    resource: repo://src/piighost/components/placeholder/__init__.py
  - id: openwiki-source-bf20a98e70f3bb3b8be6a584
    resource: repo://src/piighost/components/placeholder/label_hash.py
  - id: openwiki-source-2e9ef08220178b673a83c4b1
    resource: repo://src/piighost/components/placeholder/label.py
  - id: openwiki-source-9f3ba9afe8d0b86331fc300d
    resource: repo://src/piighost/components/placeholder/redact.py
  - id: openwiki-source-41e1e26a4994aaf47da714b8
    resource: repo://src/piighost/config/models/detector.py
  - id: openwiki-source-7ef27c7836ed8bc6a9f4f484
    resource: repo://src/piighost/config/models/hasher.py
  - id: openwiki-source-beb42dcd927067e197327036
    resource: repo://src/piighost/conversation_memory/base.py
  - id: openwiki-source-e7c9258b08b04c2f058cde4e
    resource: repo://src/piighost/crypto/cipher/base.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Registre des écarts doc / code

## En bref

- Cette page liste les endroits où la documentation existante dit autre chose que le code.
- Le code fait foi : le wiki décrit toujours ce que fait le code.
- Aucun écart n'est corrigé ici. Chacun attend une décision du mainteneur : corriger la doc, ou corriger le code. Un écart réglé garde son entrée, avec son statut.
- Les écarts relevés portent sur la documentation pour développeurs et sur un exemple de la FAQ. Aucun ne change ce que voit l'utilisateur final.

Les termes sont définis dans le [glossaire](../glossaire.md). Retour au [quickstart](../quickstart.md).

## Lire une entrée

Chaque entrée donne ce que dit la doc, ce que fait le code, la page du wiki qui en parle et l'effet de l'écart. Quand la version française de la doc (`docs/fr/`) répète l'écart, elle est citée aussi. `AGENTS.md` et `CLAUDE.md` sont ignorés par git dans ce dépôt (`.gitignore:186`). Leurs écarts ne touchent donc que les agents qui travaillent en local.

## Écarts

### ECART-01 : ports sans gabarit `Base*`

| | |
|---|---|
| Doc | `AGENTS.md:7`, `:26` et `:82` : chaque étape a un port `Any*` et un gabarit `Base*`. `docs/en/architecture.md:109-111` et `docs/fr/architecture.md:112` : seuls deux ports n'ont pas de gabarit, les garde-fous et la mémoire. |
| Code | Cinq ports n'ont pas de gabarit : `components/detector/base.py:9`, `components/override/base.py:9-17`, `components/guard/base.py:42`, `conversation_memory/base.py:10-14`, `crypto/cipher/base.py:7-10`. |
| Page du wiki | [Ajouter ou remplacer un composant](../architecture/ports-et-extension.md) |
| Effet | Un contributeur peut chercher un `BaseDetector` qui n'existe pas. |

### ECART-02 : version citée dans un message d'erreur

| | |
|---|---|
| Doc | Message de `config/models/detector.py:62-66` : les catalogues intégrés ont été retirés « in piighost 2.0 ». |
| Code | Le paquet est en `1.10.0` (`pyproject.toml:3`). `CHANGELOG.md` place le passage des catalogues au hub en 1.8.0. |
| Page du wiki | [Ajouter ou remplacer un composant](../architecture/ports-et-extension.md) |
| Effet | Un utilisateur en 1.x lit une version qui n'existe pas. [à vérifier] : « 2.0 » désigne peut-être la réécriture interne (« v2 »), pas un numéro de version publié. |

### ECART-03 : exemple de jeton haché

| | |
|---|---|
| Doc | Docstring de `components/placeholder/label_hash.py:14` et `AGENTS.md:45` : le premier jeton est `<<PERSON:6b86b273>>`. |
| Code | `label_hash.py:35-40` hache la chaîne `PERSON:1`. Le premier jeton est `<<PERSON:09ef3b74>>`. `6b86b273` est l'empreinte de la chaîne `1` seule. |
| Page du wiki | [Glossaire](../glossaire.md) |
| Effet | Un lecteur qui compare un jeton réel à l'exemple croit à un bug. Les pages de `docs/` utilisent un exemple neutre (`<<PERSON:a1b2c3d4>>`) et ne sont pas concernées. |

### ECART-04 : forme des jetons de type et de caviardage

| | |
|---|---|
| Doc | `AGENTS.md:45` illustre l'axe « étiquette » par `<PERSON>` et `[REDACT]`. |
| Code | Les fabriques émettent `<<PERSON>>` (`components/placeholder/label.py:26-28`) et `<<REDACT>>` (`redact.py:25-28`), avec les délimiteurs `<<` et `>>` par défaut. |
| Page du wiki | [Glossaire](../glossaire.md) |
| Effet | Faible : la forme des délimiteurs est mal illustrée. |

### ECART-05 : hacheur de la mémoire Redis

| | |
|---|---|
| Doc | `AGENTS.md:49` : le backend Redis hache les clés « with Argon2id ». |
| Code | Le hacheur est au choix, HMAC-SHA256 ou Argon2id (`config/models/hasher.py:76-79`). Sans hacheur, la clé est un SHA-256 non secret (`conversation_memory/base.py:73-77`). |
| Page du wiki | [Stocker les conversations et protéger les traces](../exploitation/stockage-et-chiffrement.md) |
| Effet | Un lecteur peut croire qu'Argon2id est toujours actif. |

### ECART-06 : liste blanche, liste noire et lecture du cache

| | |
|---|---|
| Doc | Docstring de `DetectionOverride` (`components/override/detector.py:51-53`) : les pipelines appliquent les listes « after every detection read ». |
| Code | Une lecture depuis le cache de la conversation ne repasse pas par les listes (`pipeline/thread.py:271-274`). |
| Page du wiki | [Imposer une liste blanche et une liste noire](../processus/imposer-une-liste-blanche-et-noire.md) |
| Effet | Une liste modifiée ne s'applique pas aux messages déjà analysés. [à vérifier] : si « detection read » désigne seulement l'appel au détecteur, la phrase est juste mais trompeuse. |

### ECART-07 : classe `ConversationMemory`

| | |
|---|---|
| Doc | `docs/en/security.md:23` et `:57`, `docs/fr/security.md:23` et `:58` : « la `ConversationMemory` lie les variantes » et porte le lien entre valeur et jeton. |
| Code | Aucune classe `ConversationMemory`. Le port est `AnyConversationMemory` (`conversation_memory/base.py:106`). Le regroupement des variantes est fait par `ExactEntityLinker` (`components/linker/exact.py:8-21`), pas par la mémoire, qui ne stocke que des détections (`conversation_memory/base.py:1-8`). |
| Page du wiki | [Suivre une conversation et restaurer la réponse](../processus/suivre-une-conversation.md) |
| Effet | Un lecteur cherche une classe absente et attribue le regroupement au mauvais composant. |

### ECART-08 : Faker, prévu ou écarté

| | |
|---|---|
| Doc | `docs/en/community/faq.md:32` et `docs/fr/community/faq.md:32` : une fabrique Faker « est sur la roadmap ». `docs/en/roadmap.md:40` et `docs/fr/roadmap.md:40` la classent dans les « Non-goals », écartée à dessein. |
| Code | Aucune fabrique Faker dans `src/` (`components/placeholder/` ne contient que `redact`, `label`, `label_counter`, `label_hash`, `mask`). |
| Page du wiki | [Glossaire](../glossaire.md) |
| Effet | Deux pages de la doc se contredisent sur une fonction annoncée aux utilisateurs. C'est le seul écart visible par un public non développeur. |

### ECART-09 : résultat d'un outil

| | |
|---|---|
| Doc | `docs/en/tool-call-strategies.md` et `docs/fr/tool-call-strategies.md`, ainsi que `placeholder-factories.md` dans les deux langues : la réponse d'un outil est parcourue « à la recherche des valeurs connues ». |
| Code | Le résultat passe par le pipeline complet de la conversation, détection comprise (`integrations/langchain/middleware.py:253-272`). Une valeur jamais citée est détectée aussi. |
| Page du wiki | [Laisser un outil agir sur les vraies valeurs](../processus/laisser-un-outil-agir.md) |
| Effet | La doc sous-estimait la protection. Statut : doc corrigée le 2026-10-02 (`3473217`). |

### ECART-10 : flux coupé au milieu d'un jeton

| | |
|---|---|
| Doc | `docs/en/reference/langchain.md` et `docs/fr/reference/langchain.md` : l'affichage en flux « ne montre jamais de token cassé ». |
| Code | En fin de flux, `flush` rend tel quel le reste retenu (`components/placeholder/streaming.py:186`), donc un flux coupé dans un jeton affiche son début. |
| Page du wiki | [Afficher une réponse streamée](../processus/afficher-une-reponse-streamee.md) |
| Effet | Cas rare, sans fuite de valeur. Statut : doc corrigée le 2026-10-02 (`3473217`). |

## Points à vérifier, sans écart établi

Ces points ne contredisent aucune doc. Ils sont signalés dans les pages du wiki avec le moyen de trancher.

| Point | Page |
|---|---|
| La demande part-elle en clair dans Claude Code quand `piighost-api` est injoignable ? | [Brancher la protection sur un agent](../integrations/agents-et-outils.md) |
| L'expiration d'un message Redis renumérote-t-elle les jetons de la conversation ? | [Suivre une conversation](../processus/suivre-une-conversation.md) |
| La surcharge d'une section entière par un objet JSON (`PIIGHOST_DETECTOR`) n'a pas de test. | [Configurer un pipeline](../exploitation/configuration-et-hub.md) |
