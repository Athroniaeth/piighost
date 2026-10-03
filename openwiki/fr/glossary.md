---
type: glossary
title: Glossaire
description: Définitions des termes de PIIGhost (dé-identification, jeton, détection, entité, conversation, provenance, liste blanche et liste noire, garde-fou, identifiants, poivre, chiffreur) avec la forme visible de chaque notion et son nom dans le code.
tags: [glossary, vocabulary, de-identification, placeholder, entity, thread]
sources:
  - id: openwiki-source-aa685735384e8973ddee846d
    resource: repo://src/piighost/components/linker/exact.py
  - id: openwiki-source-a4810bc908328d4c6013f381
    resource: repo://src/piighost/components/placeholder/base.py
  - id: openwiki-source-bf20a98e70f3bb3b8be6a584
    resource: repo://src/piighost/components/placeholder/label_hash.py
  - id: openwiki-source-2e9ef08220178b673a83c4b1
    resource: repo://src/piighost/components/placeholder/label.py
  - id: openwiki-source-657eb428104869e89297f5fd
    resource: repo://src/piighost/components/placeholder/mask.py
  - id: openwiki-source-9f3ba9afe8d0b86331fc300d
    resource: repo://src/piighost/components/placeholder/redact.py
  - id: openwiki-source-169555bcaa5f0efb2e817dc5
    resource: repo://src/piighost/config/models/override.py
  - id: openwiki-source-beb42dcd927067e197327036
    resource: repo://src/piighost/conversation_memory/base.py
  - id: openwiki-source-c8ac86a9a1c1e30960f0784f
    resource: repo://src/piighost/models/detection.py
  - id: openwiki-source-e1607726ec4e3f07dd3e5916
    resource: repo://src/piighost/models/span.py
  - id: openwiki-source-5ddce4dd4539293afb49cdfd
    resource: repo://src/piighost/pipeline/base.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Glossaire

PIIGhost n'a pas d'écran. Ce que vous « voyez » est un jeton dans le texte envoyé au modèle, un message d'erreur, une clé du fichier de configuration ou une sortie de la commande `piighost`. La colonne « Ce que vous voyez » donne cette forme. La colonne « Nom technique » sert aux développeurs.

Pour le contexte de chaque terme, partez du [quickstart](quickstart.md). Les écarts entre la documentation existante et le code sont dans le [registre des écarts](reference/doc-code-gaps.md).

## Protéger les données

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Données confidentielles | Tout ce que PIIGhost protège : les données personnelles et les secrets. | la valeur d'origine, avant protection | aucun |
| Donnée personnelle (PII) | Valeur qui peut identifier une personne : nom, adresse, téléphone, e-mail. PII signifie *Personally Identifiable Information*. | `Patrick`, `claire.dubois@example.com` | étiquette `PERSON`, `EMAIL`… |
| Secret | Identifiant d'accès qui ne doit jamais atteindre un modèle : clé d'API, mot de passe, clé privée. | une clé d'API dans un message | groupe du hub `piighost/logs` |
| Dé-identification | Remplacement des données confidentielles par des jetons, en gardant de quoi les restaurer. Au sens du RGPD (règlement général sur la protection des données), c'est une pseudonymisation. | `Bonjour <<PERSON:1>>` | pipeline par défaut |
| Anonymisation | Suppression sans retour possible. PIIGhost ne l'obtient qu'avec un jeton qui ne garde rien. | `<<REDACT>>` | `RedactPlaceholderFactory` |
| Restauration | Remise des vraies valeurs à la place des jetons, dans la réponse montrée à l'utilisateur. | `Bonjour Patrick` dans la réponse | `deanonymize` |

## Les jetons

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Jeton (placeholder) | Texte de remplacement d'une valeur. Le modèle ne voit que lui. | `<<PERSON:1>>` | token, `AnyPlaceholderFactory` |
| Jeton numéroté | Jeton qui garde le type et un numéro par type, dans l'ordre d'apparition. Valeur par défaut. | `<<PERSON:1>>`, `<<PERSON:2>>`, `<<EMAIL:1>>` | `LabelCounterPlaceholderFactory` |
| Jeton haché | Jeton numéroté dont le numéro est affiché sous forme d'empreinte. L'empreinte vient du type et du numéro, jamais de la valeur. | `<<PERSON:09ef3b74>>` | `LabelHashPlaceholderFactory` |
| Jeton de type | Jeton qui ne garde que le type. Deux personnes reçoivent le même jeton : pas de restauration fiable. | `<<PERSON>>` | `LabelPlaceholderFactory` |
| Masque | Valeur dont seuls les premiers caractères restent visibles. Pas de restauration. | `J*******` | `MaskPlaceholderFactory` |
| Jeton inventé | Jeton au bon format que PIIGhost n'a jamais émis : le modèle l'a halluciné ou un texte l'a injecté. | `Deanonymized text holds tokens the pipeline never issued: […]` | `InventedPlaceholderError` |
| Étiquette de préservation | Ce qu'un type de jeton garde : le type, l'identité, la forme, la possibilité d'être retrouvé. Sert au contrôle avant exécution. | aucune forme visible | `PreservesRecognizableIdentity`… |

## Ce que PIIGhost repère

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Détecteur | Composant qui trouve les valeurs sensibles dans un texte. Par motif, par modèle d'IA ou par grand modèle de langage. | clé `[detector]` | `AnyDetector` |
| Motif (regex) | Expression qui reconnaît une valeur à sa forme. Pas de contrôle de clé (Luhn, IBAN) : une valeur abîmée par une reconnaissance de caractères reste détectée. | clé `patterns` | `RegexDetector` |
| Catalogue | Liste de motifs publiée sur le hub et appelée par sa référence. | `hub:piighost/generic:fab51b33` | `catalogs`, `hub.pull` |
| NER | *Named Entity Recognition*, reconnaissance d'entités nommées : modèle d'IA qui classe les mots en personne, lieu, organisation. | clé `type = "gliner2"`, `"spacy"`… | `BaseNERDetector` |
| Détection | Une occurrence trouvée : position, texte, type et confiance entre 0 et 1. | une ligne de `piighost anonymize --json` | `Detection` |
| Position (span) | Intervalle de caractères `[début, fin)` d'une détection dans le texte. | `"start": 10, "end": 35` | `Span` |
| Entité | Toutes les occurrences d'une même valeur et d'un même type. Elles partagent un seul jeton. | `Patrick` et `patrick` donnent tous deux `<<PERSON:1>>` | `Entity`, `ExactEntityLinker` |
| Chevauchement | Deux détections qui couvrent des caractères communs. Une seule survit, ou leur union. | aucune forme visible | `ConfidenceOverlapResolver`, `MergeOverlapResolver` |
| Garde-fou | Contrôle final qui cherche une valeur sensible restée dans le texte protégé, et bloque l'envoi s'il en trouve. | `Anonymized text still contains PII: ['PERSON']` | `AnyGuardRail`, `PIIRemainingError` |

## Conversations

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Conversation (thread) | Échange suivi d'un message à l'autre, isolé des autres échanges. Une valeur garde le même jeton sur toute la conversation. | identifiant de conversation, `--thread-id` | `thread_id` |
| Fil par défaut | Fil commun que l'application nomme elle-même quand ses conversations n'ont pas besoin d'être séparées. Aucune intégration n'y retombe seule : un appel sans identifiant est refusé. | `default` | `DEFAULT_THREAD_ID`, `MissingThreadIdError` |
| Provenance | Auteur de la première apparition d'une valeur dans la conversation : l'utilisateur ou l'assistant. Une valeur apportée par l'assistant reste en clair par défaut. | aucune forme visible | `MessageRole`, `get_provenance` |
| Mémoire de conversation | Stockage des détections de chaque message, par conversation. Contient des données personnelles. Gardée dans le programme, elle garde au plus 10 000 conversations, chacune un jour après son dernier message. | clé `[memory]` | `AnyConversationMemory`, `InMemoryConversationMemory` |
| Effacement d'une conversation | Suppression de toute la mémoire d'une conversation, pour le droit à l'effacement. Renvoie le nombre de messages et de détections supprimés. | `Forgotten(messages=…, detections=…)` | `forget_thread` |
| Correction humaine | Jeu de détections corrigé par une personne pour un message, qui remplace celui du détecteur. | aucune forme visible | `anonymize_corrected` |
| Décodeur de flux | Composant qui restaure une réponse diffusée au fil de l'eau, en retenant un jeton coupé jusqu'à ce qu'il soit entier. | « `<<PER` » retenu, puis « Jean Dupont » | `AsyncPlaceholderStreamDecoder`, `deanonymize_stream` |
| Réglage d'outil | Ce que reçoit un outil (vraies valeurs ou jetons) et ce que lit le modèle de son résultat (masqué ou en clair). | « Complet », « Entrée seule », « Sortie seule », « Aucun » | `ToolCallStrategy` |

## Liste blanche et liste noire de la configuration

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Liste blanche | Valeurs toujours masquées, même si le détecteur les rate. Écrite dans la section `[override]` de la configuration, celle de l'application ou celle du serveur `piighost-api`. | clé `[override.whitelist]` | `DetectionOverride.whitelist` |
| Liste noire | Valeurs jamais masquées, même si le détecteur les trouve. | clé `[override.blacklist]` | `DetectionOverride.blacklist` |

## Stockage et sécurité

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Poivre (pepper) | Secret qui rend les empreintes des messages impossibles à recalculer sans lui. | variable `PIIGHOST_HASH_PEPPER` | `AnyHasher` |
| Chiffreur (cipher) | Composant qui chiffre les détections stockées, avec une clé AES (*Advanced Encryption Standard*) en mode GCM. | variable `PIIGHOST_CIPHER_KEY` | `AesGcmCipher` |
| Hub | Registre en ligne de motifs et de configurations, adressés par référence. | `https://hub.piighost.dev`, variable `PIIGHOST_HUB_URL` | `piighost.hub` |
| Masqueur de traces | Fabrique de jetons appliquée aux traces techniques, pour qu'elles ne contiennent pas de données en clair. | clé `[observation_redactor]` | `observation_redactor` |

## Identifiants du wiki

Les identifiants sont en anglais, les mêmes quelle que soit la langue de la page.

| Terme | Définition | Ce que vous voyez | Nom technique |
|---|---|---|---|
| Besoin | Ce qu'un profil attend de PIIGhost, avec ses critères observables. Le préfixe nomme le profil : responsable conformité, développeur, exploitant, utilisateur de l'application. | `DPO-1`, `DEV-10`, `OPS-7`, `USER-6` | [Besoins par profil](needs-by-profile.md) |
| Règle de gestion | Règle formulée en « Quand… alors… » dans une page de processus. *BR* signifie *business rule*, suivi du domaine. | `BR-MSG-05`, `BR-CONV-03` | parties « Règles à connaître » |
| Test d'acceptation | Test qui vérifie un critère d'un besoin. | `AT-DPO-1-2` | [Tests d'acceptation](tests/acceptance-tests.md), `tests/acceptance/` |
| Écart | Endroit où la documentation et le code divergent. | `ECART-09` | [Registre des écarts](reference/doc-code-gaps.md) |
