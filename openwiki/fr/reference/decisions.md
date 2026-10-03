---
type: reference
title: Décisions de conception
description: Les décisions qui ont construit le système de dé-identification de PIIGhost, dans l'ordre où elles se sont posées, chacune avec son identifiant, son contexte, sa raison, ses conséquences et l'endroit du code où elle vit.
tags: [decisions, conventions, placeholder, detection, conversation, security]
generated: { by: "claude-code", at: "2026-10-03T18:00:00.000Z" }
---

# Décisions de conception

## En bref

Le système de dé-identification s'est construit par étapes, et chaque besoin nouveau a demandé une décision. Pour remplacer une donnée confidentielle par un jeton, il fallait d'abord la trouver dans le texte, à une position précise. Pour que le modèle comprenne encore le texte, le jeton devait dire de quel type de donnée il s'agit. Pour distinguer deux personnes, il lui fallait un identifiant, donc une façon de regrouper les détections d'une même personne. Pour que l'utilisateur lise ses vraies données, il fallait garder la correspondance entre chaque jeton et sa valeur. Viennent ensuite la conversation, les outils d'un agent, le flux et la mise en production.

Cette page raconte ces décisions dans l'ordre où elles se sont posées. Chacune porte un identifiant `DEC-NN`, et donne son contexte, ce qui a été décidé, pourquoi, ses conséquences et l'endroit du code où elle vit. Elle cite aussi les règles de gestion qui en découlent. Le guide technique décrit les composants qui appliquent ces décisions, dans [Conception du pipeline](../../../docs/fr/conception.md). Ces décisions engagent le reste de la librairie, donc en changer une demande d'en discuter d'abord.

## Dé-identifier un texte

**DEC-01. Remplacer chaque donnée confidentielle par un jeton.**

- **Contexte** : un texte doit partir vers un modèle d'IA sans ses données confidentielles, mais le modèle doit encore pouvoir y répondre.
- **Décision** : chaque valeur est remplacée par un jeton, un texte de remplacement. Elle n'est ni supprimée ni brouillée.
- **Pourquoi** : une phrase dont on retire les noms perd son sens. Avec un jeton à la place, la phrase reste lisible, et le modèle peut répondre en réutilisant le jeton.
- **Conséquences** : tout le reste du système sert à produire ces jetons, à les garder cohérents et à les remettre en valeurs.

**DEC-02. Trouver chaque valeur et sa position exacte.**

- **Contexte** : pour remplacer une valeur, il faut savoir où elle commence et où elle finit dans le texte.
- **Décision** : un détecteur rend des passages, c'est-à-dire une position de début et de fin, avec un type et une confiance. Deux familles se complètent. Les expressions régulières reconnaissent les formats fixes (e-mail, IBAN, téléphone). Les modèles de reconnaissance d'entités (NER) reconnaissent le texte libre (nom, lieu). Un détecteur LLM nomme des valeurs sans positions, et PIIGhost les recherche lui-même dans le texte.
- **Pourquoi** : aucune famille ne couvre tout. Plusieurs détecteurs peuvent tourner ensemble.
- **Conséquences** : une valeur qu'aucun détecteur ne voit part en clair. Une valeur inventée par un LLM, absente du texte, est ignorée. Une valeur est masquée sur sa seule forme, sans clé de contrôle, pour qu'une valeur abîmée par la reconnaissance de caractères reste détectée. Les expressions régulières sont en ASCII, et toute espace Unicode compte comme une espace ordinaire.
- **Dans le code** : `components/detector/`, `text/normalization.py`. Règles BR-MSG-06, BR-MSG-07, BR-MSG-10.

**DEC-03. Encadrer chaque jeton par `<<` et `>>`.**

- **Contexte** : il fallait une nomenclature pour écrire un jeton dans le texte.
- **Décision** : un jeton est encadré par deux chevrons doublés, comme `<<PERSON:1>>`.
- **Pourquoi** : cette suite est rare dans un texte ordinaire, donc une expression régulière retrouve un jeton facilement. Elle signale aussi au modèle qu'il lit une donnée masquée.
- **Conséquences** : un texte qui contient déjà cette suite demande une précaution, voir DEC-13. Un label commence par une lettre ou `_`, puis contient des lettres, des chiffres, `_`, des espaces ou des tirets.
- **Dans le code** : `components/placeholder/streaming.py` (`DEFAULT_PREFIX`, `DEFAULT_SUFFIX`, `LABEL_INNER`).

**DEC-04. Dire dans le jeton de quel type de donnée il s'agit.**

- **Contexte** : un modèle qui lit `<<1>>` ne sait pas s'il s'agit d'une personne, d'une adresse ou d'un e-mail, et répond mal.
- **Décision** : le jeton porte le type de la donnée, son label. Le label vient du modèle NER, ou du nom donné au motif dans le détecteur à expressions régulières.
- **Pourquoi** : avec `<<PERSON:1>>`, le modèle sait qu'il parle à une personne, et peut écrire « Bonjour `<<PERSON:1>>` ».
- **Conséquences** : un détecteur peut traduire les labels de son modèle vers ceux qu'on veut voir dans les jetons.
- **Dans le code** : `components/detector/ner/base.py` (correspondance des labels).

**DEC-05. Donner à chaque individu son propre identifiant.**

- **Contexte** : deux personnes dans le même texte ne doivent pas devenir le même jeton, sinon le modèle les confond.
- **Décision** : le jeton ajoute un identifiant au type. Par défaut, c'est un numéro compté par type, à partir de 1, dans l'ordre d'apparition (`<<PERSON:1>>`, `<<PERSON:2>>`). Une autre forme utilise l'empreinte SHA-256 de « type:rang », jamais de la valeur.
- **Pourquoi** : le numéro est lisible par le modèle. L'empreinte ne cache aucun secret, et on ne peut rien en déduire sur la valeur.
- **Conséquences** : il faut savoir quelles détections désignent le même individu, voir DEC-06.
- **Dans le code** : `components/placeholder/label_counter.py`, `components/placeholder/label_hash.py`. Règle BR-MSG-01.

**DEC-06. Regrouper les détections d'un même individu.**

- **Contexte** : une même personne apparaît plusieurs fois dans un texte, parfois écrite autrement. Toutes ses occurrences doivent recevoir le même jeton.
- **Décision** : les détections qui ont la même valeur et le même type forment une entité, qui reçoit un seul jeton. Deux valeurs qui ne diffèrent que par leurs espaces ou leur casse comptent comme la même. En option, une recherche rattrape les occurrences qu'un détecteur a ratées, et un rapprochement approximatif réunit des graphies proches.
- **Pourquoi** : sans ce regroupement, « Jean Dupont » et « jean dupont » recevraient deux jetons, et le modèle croirait parler de deux personnes.
- **Conséquences** : à la restauration, une valeur écrite de plusieurs façons revient sous la première graphie rencontrée.
- **Dans le code** : `components/linker/`, `components/expander/`, `components/entity_resolver/`, `text/normalization.py` (`value_key`). Règles BR-MSG-02, BR-MSG-03, BR-MSG-12.

**DEC-07. Ne garder qu'un passage quand deux détections se recouvrent.**

- **Contexte** : deux détecteurs peuvent repérer des passages qui se chevauchent, par exemple « Jean » et « Jean Dupont ».
- **Décision** : un seul passage est gardé. Par défaut, la détection la plus sûre gagne, et à égalité, le premier détecteur déclaré. Un autre réglage garde l'union des passages.
- **Pourquoi** : le remplacement suppose des passages disjoints. Deux remplacements qui se chevauchent abîmeraient le texte.
- **Conséquences** : cette étape ne se désactive pas.
- **Dans le code** : `components/overlap_resolver/`. Règle BR-MSG-05.

**DEC-08. Garder la correspondance pour restaurer les vraies valeurs.**

- **Contexte** : l'utilisateur doit lire la réponse avec ses vraies données, pas avec des jetons.
- **Décision** : PIIGhost garde, pour chaque jeton, la valeur qu'il remplace. Dans la réponse du modèle, chaque jeton connu est remplacé par sa valeur, du jeton le plus long au plus court.
- **Pourquoi** : sans correspondance, aucune restauration n'est possible. L'ordre du plus long au plus court évite que `<<PERSON:1>>` remplace le début de `<<PERSON:10>>`.
- **Conséquences** : au sens du RGPD, c'est une pseudonymisation et non une anonymisation. La correspondance est une donnée personnelle à protéger, voir DEC-18.
- **Dans le code** : `components/anonymizer/base.py`. Règle BR-CONV-05.

**DEC-09. Laisser corriger le repérage.**

- **Contexte** : un détecteur rate des valeurs et en masque à tort.
- **Décision** : deux listes s'imposent à chaque repérage. La liste blanche masque une valeur même si le détecteur l'a ratée. La liste noire laisse une valeur en clair même si le détecteur l'a repérée. Une personne peut aussi corriger à la main les valeurs d'un message.
- **Pourquoi** : un serveur ou une équipe connaît ses propres valeurs sensibles, et ses faux positifs.
- **Conséquences** : une correction manuelle ne vaut que pour son message, et les deux listes s'appliquent encore par-dessus.
- **Dans le code** : `components/override/`, `pipeline/thread.py`. Règles BR-LIST-01, BR-LIST-02, BR-CONV-07.

**DEC-10. Relire le texte protégé avant l'envoi, en option.**

- **Contexte** : une valeur ratée par tous les détecteurs part en clair.
- **Décision** : un contrôle final, le garde-fou, peut relire le texte déjà protégé. S'il y trouve une donnée confidentielle, l'envoi est bloqué.
- **Pourquoi** : c'est une seconde ligne de défense, avec un autre outil que les détecteurs.
- **Conséquences** : le garde-fou signale, il ne localise pas toujours la valeur. Il ralentit l'envoi.
- **Dans le code** : `components/guard/`. Règles BR-MSG-10, BR-MSG-11.

## Tenir une conversation

**DEC-11. Garder le même jeton pendant toute la conversation.**

- **Contexte** : une conversation compte plusieurs messages. Si « Jean Dupont » devient `<<PERSON:1>>` au premier message et `<<PERSON:2>>` au troisième, le modèle croit parler de deux personnes.
- **Décision** : une mémoire garde les détections de chaque message de la conversation. Les jetons sont attribués sur l'ensemble des messages, et une valeur reprend son jeton à chaque réapparition. Chaque conversation a ses propres jetons.
- **Pourquoi** : rejouer le pipeline message par message ne suffit pas, parce que les numéros changeraient d'un message à l'autre.
- **Conséquences** : la mémoire grandit avec les conversations, voir DEC-19. Plusieurs instances du service doivent partager la même mémoire pour donner les mêmes jetons.
- **Dans le code** : `pipeline/thread.py`, `conversation_memory/`. Règles BR-CONV-01, BR-CONV-02, BR-CONV-10.

**DEC-12. Exiger l'identifiant de la conversation.**

- **Contexte** : sans identifiant, deux utilisateurs partageraient la même mémoire, et l'un pourrait lire les valeurs de l'autre.
- **Décision** : chaque appel nomme sa conversation. Un appel sans identifiant échoue, au lieu de retomber sur une conversation commune.
- **Pourquoi** : une fuite entre conversations doit être impossible par accident.
- **Conséquences** : une application qui veut vraiment une conversation commune doit la nommer elle-même.
- **Dans le code** : `pipeline/thread.py`, `integrations/`. Règles BR-CONV-03, BR-AGT-01, BR-AGT-05.

**DEC-13. Neutraliser un jeton tapé par l'utilisateur.**

- **Contexte** : un utilisateur peut écrire lui-même `<<PERSON:2>>` pour faire apparaître la valeur d'une autre personne dans la réponse.
- **Décision** : un texte de l'utilisateur qui a la forme d'un jeton est neutralisé par un caractère invisible (U+200B), et n'est plus reconnu comme jeton.
- **Pourquoi** : seuls les jetons émis par PIIGhost doivent pouvoir être restaurés.
- **Conséquences** : le caractère invisible reste dans le texte restauré.
- **Dans le code** : `components/anonymizer/span.py`. Règle BR-MSG-09.

**DEC-14. Refuser un jeton inventé par le modèle.**

- **Contexte** : un modèle peut écrire un jeton au bon format que PIIGhost n'a jamais émis, par erreur ou sous l'effet d'une injection.
- **Décision** : par défaut, la réponse ou l'appel d'outil est refusé. Deux autres réglages retirent le jeton ou le gardent tel quel.
- **Pourquoi** : afficher un jeton inventé, ou l'envoyer à un outil, produirait une action sur une donnée qui n'existe pas.
- **Dans le code** : `integrations/_deidentify.py`. Règles BR-CONV-06, BR-TOOL-07, BR-STREAM-06.

**DEC-15. Laisser en clair une valeur que l'assistant cite le premier.**

- **Contexte** : le modèle peut introduire lui-même une valeur, un nom de ville par exemple, que l'utilisateur n'a jamais écrite.
- **Décision** : par défaut, une valeur citée d'abord par l'assistant reste en clair pour toute la conversation. Deux autres réglages la masquent ou l'ignorent.
- **Pourquoi** : cette valeur ne vient pas de l'utilisateur, donc elle ne fait pas partie de ses données à protéger.
- **Dans le code** : `integrations/langchain/middleware.py` (`EntityCreateByAssistantStrategy`). Règles BR-CONV-04, BR-AGT-03.

## Laisser un agent agir

**DEC-16. Donner la vraie valeur aux outils, et le jeton au modèle.**

- **Contexte** : un agent appelle des outils, par exemple pour envoyer un e-mail. L'outil a besoin de la vraie adresse, le modèle ne doit jamais la voir.
- **Décision** : par défaut, les arguments d'un outil sont restaurés avant l'appel, et son résultat est dé-identifié avant de revenir au modèle. Trois autres réglages limitent ce traitement.
- **Pourquoi** : c'est ce qui permet à un agent d'agir sur de vraies données sans les exposer au modèle.
- **Conséquences** : le résultat d'un outil passe par le repérage complet de la conversation. L'historique de l'agent garde les appels avec leurs jetons.
- **Dans le code** : `integrations/langchain/middleware.py` (`ToolCallStrategy.FULL`). Règles BR-TOOL-01, BR-TOOL-05, BR-TOOL-10.

**DEC-17. Restaurer la réponse pendant qu'elle arrive.**

- **Contexte** : un modèle peut envoyer sa réponse morceau par morceau. Un jeton peut alors arriver coupé, `<<PER` puis `SON:1>>`.
- **Décision** : un décodeur retient un jeton commencé jusqu'à ce qu'il soit complet, puis le restaure. Un `<` isolé en fin de morceau est retenu aussi. Au-delà de 128 caractères sans fermeture, le texte retenu est relâché tel quel.
- **Pourquoi** : restaurer chaque morceau séparément laisserait passer des jetons coupés.
- **Conséquences** : un flux arrêté au milieu d'un jeton affiche le fragment retenu, sans restauration.
- **Dans le code** : `components/placeholder/streaming.py`. Règles BR-STREAM-02 à BR-STREAM-05.

## Mettre en production

**DEC-18. Protéger la correspondance stockée.**

- **Contexte** : la correspondance entre jetons et valeurs contient les données confidentielles en clair, voir DEC-08.
- **Décision** : avec Redis, les clés passent par HMAC puis Argon2id avec un poivre, et les valeurs sont chiffrées en AES-GCM. Les secrets ne se lisent que dans l'environnement, jamais dans un fichier de configuration. Les traces d'observation peuvent être masquées.
- **Pourquoi** : une fuite du stockage ne doit pas livrer les données.
- **Conséquences** : l'identifiant de conversation reste lisible, pour qu'on puisse effacer une conversation. Un stockage sans chiffrement émet un avertissement.
- **Dans le code** : `crypto/`, `conversation_memory/redis_backend.py`. Règles BR-STO-01, BR-STO-02, BR-STO-03, BR-STO-08.

**DEC-19. Échouer du côté qui protège.**

- **Contexte** : un composant peut tomber en panne, et une mémoire peut grandir sans fin.
- **Décision** : chaque réglage par défaut choisit le côté qui protège. Un détecteur LLM dont la sortie est illisible refuse le message. Les hooks Claude Code bloquent si le serveur ne répond pas. La mémoire du processus garde au plus 10 000 conversations, et oublie une conversation après un jour sans activité.
- **Pourquoi** : une panne ne doit jamais devenir une fuite.
- **Conséquences** : un réglage explicite permet de laisser passer, pour qui préfère la disponibilité à la protection.
- **Dans le code** : `components/detector/llm.py`, `integrations/claude_code/runner.py`, `conversation_memory/memory.py`. Besoin DPO-9, règles BR-STO-04, BR-CONV-11.

**DEC-20. Configurer un pipeline par fichier et par le hub.**

- **Contexte** : une équipe doit déployer le même pipeline sur plusieurs serveurs, sans écrire de code.
- **Décision** : un pipeline se décrit dans un fichier TOML ou JSON. Les groupes de motifs viennent du hub, par une référence. Une référence épinglée sur un commit est mise en cache. Un tag ou `latest` est relu à chaque fois.
- **Pourquoi** : une référence épinglée ne change jamais, alors qu'une version périmée détecterait moins sans le dire.
- **Dans le code** : `config/`, `hub.py`.

## L'architecture

**DEC-21. Faire de chaque étape un port remplaçable.**

- **Contexte** : chaque équipe a ses propres détecteurs, son stockage et ses contraintes.
- **Décision** : chaque étape du pipeline a une interface, et la plupart ont un modèle de base. Seul le détecteur est obligatoire. La configuration connaît le cœur de la librairie, jamais l'inverse.
- **Pourquoi** : on remplace une étape sans toucher aux autres.
- **Conséquences** : le cœur ne contient aucune règle propre à une langue. Les listes de mots français ou métier vont dans les groupes du hub.
- **Dans le code** : `components/*/base.py`. Voir [Ajouter ou remplacer un composant](../architecture/ports-and-extension.md).

**DEC-22. Tout rendre asynchrone.**

- **Contexte** : les détecteurs à modèle et les serveurs distants répondent en différé.
- **Décision** : chaque étape du pipeline est asynchrone.
- **Pourquoi** : le pipeline attend un modèle ou un serveur sans bloquer le reste de l'application.
- **Dans le code** : `pipeline/base.py`.

Les termes sont définis dans le [glossaire](../glossary.md).
