---
type: reference
title: Décisions de conception
description: Les décisions qui ont construit le système de dé-identification de PIIGhost, dans l'ordre où elles se sont posées, chacune expliquée avec un exemple, et l'endroit du code où elle vit.
tags: [decisions, conventions, placeholder, detection, conversation, security]
generated: { by: "claude-code", at: "2026-10-03T18:00:00.000Z" }
---

# Décisions de conception

## En bref

Le système de dé-identification s'est construit par étapes, et chaque besoin nouveau a demandé une décision. Pour remplacer une donnée confidentielle par un jeton, il fallait d'abord la trouver dans le texte, à une position précise. Pour que le modèle comprenne encore le texte, le jeton devait dire de quel type de donnée il s'agit. Pour distinguer deux personnes, le jeton avait besoin d'un identifiant. Il fallait donc savoir quelles détections désignent la même personne. Pour que l'utilisateur lise ses vraies données, il fallait garder la correspondance entre chaque jeton et sa valeur. Viennent ensuite la conversation, les outils d'un agent, le flux et la mise en production.

Cette page présente ces décisions dans l'ordre où elles se sont posées. Chacune porte un identifiant `DEC-NN`. Elle explique le problème, le choix fait et ce qu'il change, avec un exemple quand il aide. Elle se termine par l'endroit du code où elle vit, et par les règles de gestion qui en découlent. Ces décisions forment ensemble le pipeline, c'est-à-dire la suite d'étapes qui va du texte d'origine au texte protégé. Le guide technique décrit les composants de ce pipeline, dans [Conception du pipeline](../../../docs/fr/conception.md). Le reste de la librairie dépend de ces décisions, donc en changer une demande d'en discuter d'abord.

## Dé-identifier un texte

### DEC-01 : Remplacer chaque donnée confidentielle par un jeton

Un texte doit partir vers un modèle d'IA sans ses données confidentielles. Le modèle doit pourtant encore pouvoir y répondre. Supprimer les données ne marche pas, parce qu'une phrase privée de ses noms perd son sens. « Préviens Jean Dupont que son rendez-vous est déplacé » deviendrait « Préviens que son rendez-vous est déplacé », et le modèle ne saurait plus qui prévenir.

PIIGhost remplace donc chaque valeur par un jeton, c'est-à-dire un court texte qui tient sa place. Par défaut, la valeur n'est ni supprimée ni masquée lettre par lettre. La phrase reste lisible, et le modèle peut répondre en réutilisant le jeton. Tout le reste du système sert à produire ces jetons, à les garder cohérents et à les remettre en valeurs.

### DEC-02 : Trouver chaque valeur et sa position exacte

Pour remplacer une valeur, il faut savoir où elle commence et où elle finit dans le texte. C'est le rôle d'un détecteur. Chaque valeur qu'il trouve s'appelle une détection. Une détection donne un passage, c'est-à-dire une position de début et de fin, avec le type de la donnée et un score de confiance. Ce score est un nombre entre 0 et 1, qui dit à quel point le détecteur est sûr de lui.

Aucun détecteur ne trouve tout, donc plusieurs peuvent tourner ensemble. Deux familles se complètent :

- Les expressions régulières : ce sont des motifs qui reconnaissent les formats fixes, comme un e-mail, un IBAN ou un téléphone.
- Les modèles NER : ce sont des modèles d'IA entraînés à reconnaître, dans le texte libre, les noms de personnes, de lieux ou d'organisations.

Un détecteur LLM fonctionne autrement. Un LLM est un grand modèle de langage, interrogé comme un assistant. Il nomme des valeurs sans donner leur position, et PIIGhost les recherche lui-même dans le texte. Une valeur que le LLM invente est donc ignorée, parce qu'elle n'est pas dans le texte.

Cette façon de détecter a trois limites. D'abord, une valeur qu'aucun détecteur ne voit part en clair. Ensuite, une expression régulière reconnaît une valeur à sa seule forme. Elle ne vérifie pas sa clé de contrôle, c'est-à-dire les chiffres de vérification que porte un IBAN. Un IBAN abîmé par la reconnaissance de caractères (OCR) reste ainsi détecté, même si sa clé est devenue fausse. Enfin, une expression régulière ne reconnaît que les chiffres et les lettres latines de base. Un chiffre arabe-indien, par exemple, n'est pas lu comme un chiffre. Toute espace Unicode, comme l'espace insécable, compte en revanche comme une espace ordinaire.

Cette décision vit dans `components/detector/` et `text/normalization.py`. Les règles BR-MSG-06, BR-MSG-07 et BR-MSG-10 en découlent.

### DEC-03 : Encadrer chaque jeton par `<<` et `>>`

Un jeton doit se distinguer du reste du texte. PIIGhost l'encadre par deux chevrons doublés, comme `<<REDACT>>`.

Cette suite de caractères est rare dans un texte ordinaire. Un programme retrouve donc chaque jeton facilement, avec une expression régulière. Les chevrons signalent aussi au modèle qu'il lit une donnée masquée, et non un mot de la phrase.

Rien n'empêche pourtant un utilisateur de taper lui-même cette suite. PIIGhost neutralise un jeton tapé à la main, voir DEC-13.

Cette décision vit dans `components/placeholder/streaming.py` (`DEFAULT_PREFIX`, `DEFAULT_SUFFIX`).

### DEC-04 : Dire dans le jeton de quel type de donnée il s'agit

Si chaque donnée devient `<<REDACT>>`, le modèle ne sait plus ce qu'il lit. Dans « Résume l'échange entre `<<REDACT>>` et `<<REDACT>>` », il ne sait pas s'il s'agit de deux personnes, de deux entreprises ou de deux adresses e-mail. Il répond donc mal.

Le jeton dit donc le type de la donnée, appelé label, comme `<<PERSON>>` ou `<<EMAIL>>`. Avec `<<PERSON>>`, le modèle sait qu'il s'agit d'une personne. Il peut écrire « Bonjour `<<PERSON>>` ».

Le label vient du détecteur. Pour un modèle NER, c'est la catégorie que le modèle donne. Pour une expression régulière, c'est le nom qu'on lui donne, par exemple `EMAIL`. Un détecteur peut aussi traduire les labels de son modèle vers ceux qu'on veut voir dans les jetons.

Un label s'écrit en lettres sans accent, chiffres, `_`, espaces ou tirets, et commence par une lettre ou `_`. `DATE_NAISSANCE` convient, `PRÉNOM` non.

Il reste un problème. Deux personnes reçoivent encore le même jeton, voir DEC-05.

Cette décision vit dans `components/detector/ner/base.py` (traduction des labels) et `components/placeholder/streaming.py` (`LABEL_INNER`).

### DEC-05 : Donner à chaque entité son propre identifiant

Avec `<<PERSON>>`, deux personnes du même texte reçoivent le même jeton. « Résume l'échange entre `<<PERSON>>` et `<<PERSON>>` » ne dit plus qui a parlé, et le modèle les confond.

Le jeton ajoute donc un identifiant après le label, comme `<<PERSON:1>>` et `<<PERSON:2>>`. Par défaut, c'est un numéro compté par label, à partir de 1, dans l'ordre d'apparition. Le modèle le lit sans peine.

Une autre forme remplace le numéro par une empreinte, comme `<<PERSON:a1b2c3d4>>`. Une empreinte est une suite de caractères calculée à partir d'un texte, ici avec l'algorithme SHA-256. PIIGhost la calcule sur le label et le numéro d'ordre, jamais sur la valeur. Elle n'a besoin d'aucune clé secrète, et on ne peut rien en déduire sur la valeur. Elle sert seulement à ce que deux jetons voisins n'aient pas l'air de se suivre.

Pour attribuer ces identifiants, il faut savoir quelles détections désignent la même personne ou la même valeur, voir DEC-06.

Cette décision vit dans `components/placeholder/label_counter.py` et `components/placeholder/label_hash.py`. La règle BR-MSG-01 en découle.

### DEC-06 : Regrouper les détections d'une même entité

Une même personne apparaît souvent plusieurs fois dans un texte, parfois écrite autrement. Toutes ses occurrences doivent recevoir le même jeton. Sinon, « Jean Dupont » et « jean dupont » recevraient deux jetons, et le modèle croirait parler de deux personnes.

PIIGhost distingue donc deux notions :

- La détection : une occurrence trouvée dans le texte, à une position précise. Elle vient du détecteur, voir DEC-02.
- L'entité : la personne ou la valeur elle-même, qui regroupe toutes ses détections. C'est l'entité qui reçoit un jeton.

Dans « Jean Dupont a appelé. Rappelle Jean Dupont demain. », le détecteur rend deux détections, une par occurrence. Elles forment une seule entité, et les deux occurrences deviennent `<<PERSON:1>>`.

PIIGhost regroupe en une entité les détections qui ont la même valeur et le même label. Deux valeurs qui ne diffèrent que par leurs espaces ou leurs majuscules comptent comme la même.

Deux options vont plus loin. Une option cherche dans le texte les autres occurrences d'une valeur déjà trouvée, au cas où un détecteur les aurait ratées. Une autre réunit des graphies proches, comme « Jean Dupont » et « Jean Dupond », par un rapprochement approximatif. Ce rapprochement peut aussi réunir sous un même jeton deux personnes réellement distinctes.

Une entité ne garde qu'une graphie. Quand la réponse est restaurée (voir DEC-08), l'entité revient sous la première graphie rencontrée. Si « Jean Dupont » apparaît avant « jean dupont », les deux reviennent écrits « Jean Dupont ».

Cette décision vit dans `components/linker/`, `components/expander/`, `components/entity_resolver/` et `text/normalization.py` (`value_key`). Les règles BR-MSG-02, BR-MSG-03 et BR-MSG-12 en découlent.

### DEC-07 : Ne garder qu'un passage quand deux détections se recouvrent

Deux détecteurs peuvent trouver des passages qui se chevauchent. L'un trouve « Jean », l'autre « Jean Dupont ». PIIGhost ne sait remplacer que des passages qui ne se chevauchent pas. S'il en reste au moment du remplacement, il refuse le texte plutôt que d'en laisser un morceau en clair.

Un seul passage est donc gardé. Par défaut, la détection au score de confiance le plus haut gagne. À score égal, la détection qui commence le plus tôt gagne, puis la plus courte. L'ordre des détecteurs ne départage que deux détections du même passage exact.

Ce réglage a un coût. Si « Jean » a le meilleur score, seul « Jean » est remplacé, et « Dupont » part en clair. L'autre réglage, la fusion, évite cette fuite. Il garde un seul passage qui couvre les deux, ici « Jean Dupont », avec le label de la détection la plus sûre.

Cette étape ne se désactive pas.

Cette décision vit dans `components/overlap_resolver/`. La règle BR-MSG-05 en découle.

### DEC-08 : Garder la correspondance pour restaurer les vraies valeurs

L'utilisateur doit lire la réponse avec ses vraies données, pas avec des jetons. PIIGhost garde donc la valeur que remplace chaque jeton. On appelle cette table la correspondance. Sans elle, aucune restauration n'est possible.

Dans la réponse du modèle, chaque jeton connu est remplacé par sa valeur. « Bonjour `<<PERSON:1>>` » redevient « Bonjour Jean Dupont ». Une valeur restaurée n'est jamais examinée une seconde fois. Une vraie valeur qui ressemble à un jeton s'affiche donc telle quelle.

Une autre approche se passe de correspondance. Google Sensitive Data Protection (anciennement Cloud DLP) peut chiffrer la valeur elle-même dans le jeton, avec une clé. Le jeton commence par un nom choisi par l'équipe, suivi de la longueur du texte chiffré, puis de ce texte, sous la forme `PHONE_TOKEN(36):AYCL…`. Pour restaurer la valeur, il faut le jeton entier et la même clé. Aucune valeur n'est stockée.

PIIGhost a choisi la correspondance pour quatre raisons :

- Le jeton reste court et lisible : le modèle recopie facilement `<<PERSON:1>>`. Un jeton chiffré en AES-SIV est une longue suite de caractères, plus difficile à recopier sans erreur.
- Le jeton ne contient pas la valeur : un jeton chiffré la contient. Les jetons envoyés au modèle restent dans ses journaux, et une fuite de la clé les rend tous lisibles. Un jeton PIIGhost ne révèle rien sans la mémoire de la conversation.
- Le jeton vaut pour une seule conversation : par défaut, avec la même clé, une valeur donne toujours le même jeton. On peut alors relier toutes les conversations où elle apparaît. Avec PIIGhost, `<<PERSON:1>>` peut désigner une autre personne dans une autre conversation, voir DEC-11.
- Une conversation peut être oubliée : effacer sa correspondance rend ses jetons impossibles à restaurer, dès que tous les processus du service l'ont oubliée. Avec une seule clé pour tout le service, un jeton chiffré reste déchiffrable tant que cette clé existe.

Ce choix a un coût. PIIGhost doit garder une mémoire qui retient les valeurs de chaque conversation. Ce n'est pas un simple cache, parce qu'elle ne se reconstruit pas. La perdre empêche de restaurer les jetons de la conversation. Cette mémoire doit être protégée (DEC-18) et bornée (DEC-19). Si le service tourne sur plusieurs serveurs, elle doit être partagée entre eux (DEC-11).

Les vraies valeurs restent récupérables. Au sens du RGPD, c'est donc une pseudonymisation, et non une anonymisation. La correspondance est elle-même une donnée personnelle à protéger, voir DEC-18.

Cette décision vit dans `components/anonymizer/base.py`. La règle BR-CONV-05 en découle.

### DEC-09 : Laisser corriger la détection

Un détecteur fait deux sortes d'erreurs. Il rate des valeurs, et il en masque d'autres à tort. Un serveur ou une équipe connaît pourtant ses propres valeurs sensibles, et les mots que le détecteur masque à tort.

Deux listes, fixées par le serveur, l'emportent donc sur le détecteur :

- La liste blanche : elle masque une valeur, même si le détecteur l'a ratée.
- La liste noire : elle laisse une valeur en clair, même si le détecteur l'a trouvée.

Le sens est l'inverse de l'usage courant, où une liste blanche autorise. Ici, la liste blanche force le masquage. Une liste blanche qui contient le code client `CLI-4821` le masque partout. Une liste noire qui contient « Docteur » empêche ce mot d'être pris pour un nom. Si une valeur figure dans les deux listes, elle est masquée par défaut.

Une personne peut aussi corriger à la main les valeurs d'un message. Cette correction ne vaut que pour ce message, et les deux listes s'appliquent encore par-dessus.

Cette décision vit dans `components/override/` et `pipeline/thread.py`. Les règles BR-LIST-01, BR-LIST-02 et BR-CONV-07 en découlent.

### DEC-10 : Relire le texte protégé avant l'envoi, en option

Une valeur ratée par tous les détecteurs part en clair. Un contrôle final, appelé garde-fou, peut relire le texte déjà dé-identifié avant l'envoi. S'il y trouve encore une donnée confidentielle, le texte n'est pas envoyé, et l'application reçoit une erreur.

Le garde-fou est une seconde ligne de défense. Son intérêt principal est de pouvoir utiliser un autre outil que les détecteurs. Prenons un modèle de classification, c'est-à-dire un modèle qui range un texte dans une catégorie comme « sûr » ou « non sûr ». Il sait dire qu'un texte contient une donnée confidentielle, sans savoir dire où elle se trouve. Il ne peut donc pas servir de détecteur, parce qu'un détecteur doit donner la position de chaque valeur (DEC-02). Il peut en revanche servir de garde-fou.

Le garde-fou ne corrige rien. Il signale une fuite et bloque l'envoi, mais ne remplace pas la valeur, parce qu'il ne sait pas toujours où elle se trouve. Un modèle qui sait situer les valeurs sert d'ordinaire de détecteur. Un garde-fou peut toutefois relancer un détecteur plus fort que celui du pipeline, pour rattraper ce que le premier a raté. Le garde-fou rend aussi l'envoi plus lent.

Cette décision vit dans `components/guard/`. Les règles BR-MSG-10 et BR-MSG-11 en découlent.

## Tenir une conversation

### DEC-11 : Garder le même jeton pendant toute la conversation

Une conversation compte plusieurs messages. Si « Jean Dupont » devient `<<PERSON:1>>` au premier message et `<<PERSON:2>>` au troisième, le modèle croit parler de deux personnes. Dé-identifier chaque message séparément ne suffit donc pas, parce que les numéros changeraient d'un message à l'autre.

PIIGhost garde une mémoire par conversation, qui retient les détections de chaque message. Les numéros sont comptés sur toute la conversation, et non message par message. « Jean Dupont » garde donc `<<PERSON:1>>` chaque fois qu'il revient. Chaque conversation a ses propres jetons, donc `<<PERSON:1>>` peut désigner deux personnes différentes dans deux conversations.

La mémoire grandit avec les conversations, voir DEC-19. Si le service tourne sur plusieurs serveurs, ils doivent partager la même mémoire pour donner les mêmes jetons.

Cette décision vit dans `pipeline/thread.py` et `conversation_memory/`. Les règles BR-CONV-01, BR-CONV-02 et BR-CONV-10 en découlent.

### DEC-12 : Exiger l'identifiant de la conversation

Chaque conversation a sa propre mémoire, retrouvée par l'identifiant de la conversation. Sans identifiant, deux utilisateurs partageraient la même mémoire, et l'un pourrait lire les valeurs de l'autre.

Chaque demande de dé-identification ou de restauration doit donc donner l'identifiant de sa conversation. Une demande sans identifiant échoue, au lieu de retomber sur une conversation commune. Une fuite entre conversations ne peut pas arriver par accident. Une application qui veut vraiment une conversation commune donne le même identifiant à toutes ses demandes, par exemple `default`.

Cette décision vit dans `pipeline/thread.py` et `integrations/`. Les règles BR-CONV-03, BR-AGT-01 et BR-AGT-05 en découlent.

### DEC-13 : Neutraliser un jeton tapé par l'utilisateur

Un utilisateur peut écrire lui-même `<<PERSON:2>>` dans son message. Sans précaution, ce texte serait restauré dans la réponse, et afficherait la valeur d'une autre personne de la conversation.

PIIGhost neutralise donc tout texte de l'utilisateur qui a la forme d'un jeton. Il y glisse un caractère invisible, l'espace sans largeur (U+200B), et le texte n'est plus reconnu comme jeton. Seuls les jetons émis par PIIGhost peuvent être restaurés.

L'utilisateur revoit son texte tel qu'il l'a tapé. Le caractère invisible y reste pourtant, et un copier-coller l'emporte avec lui.

Cette décision vit dans `components/anonymizer/span.py`. La règle BR-MSG-09 en découle.

### DEC-14 : Refuser un jeton inventé par le modèle

Un modèle peut écrire un jeton au bon format que PIIGhost n'a jamais émis, comme `<<PERSON:7>>` dans une conversation qui ne compte que deux personnes. Il le fait par erreur, ou parce qu'un texte malveillant le lui a demandé. Cette attaque s'appelle une injection de prompt, le prompt étant le texte d'instructions donné au modèle.

Ce jeton ne correspond à aucune valeur. Affiché, il tromperait l'utilisateur. Transmis à un outil (voir DEC-16), il ferait agir l'agent sur une donnée qui n'existe pas. Par défaut, la réponse ou l'appel d'outil est donc refusé. Deux autres réglages retirent le jeton, ou le gardent tel quel.

Cette décision vit dans `integrations/_deidentify.py`. Les règles BR-CONV-06, BR-TOOL-07 et BR-STREAM-06 en découlent.

### DEC-15 : Laisser en clair une valeur que l'assistant cite le premier

Le modèle peut citer une valeur que l'utilisateur n'a jamais écrite. Il propose par exemple « Lyon » pour un rendez-vous. Cette valeur ne vient pas de l'utilisateur, donc elle ne fait pas partie de ses données à protéger.

Par défaut, une valeur que l'assistant cite le premier reste en clair pour toute la conversation. Elle reste en clair même si l'utilisateur l'écrit ensuite, et même si elle figure sur la liste blanche (voir DEC-09), sauf si cette liste est réglée pour forcer le masquage.

Deux autres réglages existent. Le premier masque cette valeur comme une donnée de l'utilisateur. Le second n'analyse pas du tout les messages de l'assistant, ce qui économise la détection.

Cette décision vit dans `integrations/langchain/middleware.py` (`EntityCreateByAssistantStrategy`). Les règles BR-CONV-04 et BR-AGT-03 en découlent.

## Laisser un agent agir

### DEC-16 : Donner la vraie valeur aux outils, et le jeton au modèle

Un agent appelle des outils, par exemple pour envoyer un e-mail. L'outil a besoin de la vraie adresse. Le modèle, lui, ne doit jamais la voir.

Par défaut, PIIGhost restaure les arguments d'un outil avant l'appel. Le modèle demande d'écrire à `<<EMAIL:1>>`, et l'outil reçoit la vraie adresse. Le résultat de l'outil est ensuite dé-identifié avant de revenir au modèle. Un agent peut ainsi agir sur de vraies données sans les montrer au modèle.

Trois autres réglages existent. L'un restaure seulement les arguments. Un autre dé-identifie seulement le résultat. Le dernier ne fait ni l'un ni l'autre. Avec le premier et le dernier, le résultat de l'outil arrive au modèle en clair.

Le résultat d'un outil passe par la même détection que les messages de la conversation. Dans l'historique que l'agent enregistre, les appels d'outil restent en jetons. Le texte des messages y est en revanche enregistré restauré, donc avec les vraies valeurs.

Cette décision vit dans `integrations/langchain/middleware.py` (`ToolCallStrategy.FULL`). Les règles BR-TOOL-01, BR-TOOL-05 et BR-TOOL-10 en découlent.

### DEC-17 : Restaurer la réponse pendant qu'elle arrive

Un modèle peut envoyer sa réponse morceau par morceau, en flux. Un jeton peut alors arriver coupé en deux, `<<PER` dans un morceau puis `SON:1>>` dans le suivant. Restaurer chaque morceau séparément laisserait passer ces jetons coupés, et l'utilisateur les verrait.

PIIGhost retient donc un jeton commencé jusqu'à ce qu'il soit complet, puis le restaure. Un `<` seul en fin de morceau est retenu aussi, parce qu'il peut ouvrir un jeton. Un `<<` resté ouvert sur plus de 128 caractères ne peut plus être un jeton. Le texte retenu s'affiche alors tel quel.

Si le flux s'arrête au milieu d'un jeton, le fragment retenu s'affiche tel quel, sans restauration.

Cette décision vit dans `components/placeholder/streaming.py`. Les règles BR-STREAM-02 à BR-STREAM-05 en découlent.

## Mettre en production

### DEC-18 : Protéger la mémoire stockée

La mémoire d'une conversation garde les détections de chaque message, donc les données confidentielles en clair, voir DEC-11. Une fuite du stockage ne doit pas livrer ces données.

Cette mémoire peut vivre dans Redis, une base de données partagée entre serveurs, ou dans une base SQL. PIIGhost peut alors protéger ce qu'il stocke, si on lui configure les deux protections ensemble :

- Les clés : chaque message est rangé sous son empreinte, calculée avec un poivre, c'est-à-dire un secret ajouté avant le calcul. L'empreinte utilise HMAC-SHA256, ou Argon2id, plus lent à attaquer.
- Les valeurs : les détections de chaque message sont chiffrées avec AES-GCM, un chiffrement standard.

Sans ces deux protections, la mémoire est stockée en clair, et PIIGhost émet un avertissement. Les secrets se lisent seulement dans les variables d'environnement du serveur, jamais dans un fichier de configuration. L'identifiant de conversation reste lisible, pour qu'on puisse effacer une conversation.

Les traces d'observation suivent chaque étape du pipeline. Par défaut, elles contiennent le texte en clair. Un réglage les masque avec des jetons. Sans ce réglage, PIIGhost émet un avertissement dès que les traces sont réellement envoyées.

Cette décision vit dans `crypto/`, `conversation_memory/redis_backend.py` et `conversation_memory/sqlalchemy_backend.py`. Les règles BR-STO-01, BR-STO-02, BR-STO-03 et BR-STO-08 en découlent.

### DEC-19 : Préférer la protection à la disponibilité

Un composant peut tomber en panne, et une mémoire peut grandir sans limite. Une panne ne doit jamais devenir une fuite. Chaque réglage par défaut choisit donc le côté qui protège :

- Un détecteur ou un garde-fou LLM dont la sortie est illisible refuse le message, au lieu de le laisser partir sans détection ou sans vérification.
- Les hooks Claude Code, c'est-à-dire les points où PIIGhost relit ce que l'assistant de code Claude Code envoie, bloquent l'action si le serveur PIIGhost ne répond pas.
- La mémoire intégrée, qui vit dans l'application sans base de données, garde au plus 10 000 conversations. Elle oublie une conversation un jour après son dernier message.

Une conversation oubliée perd ses jetons. Un jeton qu'elle contenait s'affiche alors tel quel, sans restauration.

Chaque protection se lève par un réglage explicite, pour qui préfère la disponibilité à la protection. Le détecteur LLM et les hooks laissent alors passer le texte, et la mémoire n'a plus de limite.

Cette décision vit dans `components/detector/llm.py`, `components/guard/llm.py`, `integrations/claude_code/runner.py` et `conversation_memory/memory.py`. Elle répond au besoin DPO-9, et les règles BR-STO-04 et BR-CONV-11 en découlent.

### DEC-20 : Configurer un pipeline par fichier et par le hub

Une équipe doit pouvoir déployer le même pipeline sur plusieurs serveurs, sans écrire de code. Un pipeline se décrit donc dans un fichier TOML ou JSON.

PIIGhost ne livre lui-même aucune expression régulière. Les groupes d'expressions régulières, propres à un pays ou à un métier, viennent du hub, le catalogue partagé de PIIGhost. Sans groupe du hub, aucun e-mail ni IBAN n'est reconnu par expression régulière. Le hub fournit aussi des configurations complètes.

Le fichier désigne un groupe par une référence. Une référence peut viser une version figée, par son identifiant, comme `:2f602547`. Cette version ne change jamais, donc PIIGhost en garde une copie locale. Une référence par nom, ou `latest` pour la dernière version, peut changer. PIIGhost la télécharge donc à chaque chargement, parce qu'une copie périmée détecterait moins de valeurs sans le signaler.

Cette décision vit dans `config/` et `hub.py`.

## L'architecture

### DEC-21 : Faire de chaque étape un port remplaçable

Chaque équipe a ses propres détecteurs, son stockage et ses contraintes. Chaque étape du pipeline est donc un port, c'est-à-dire une interface qu'on peut remplacer. On change le détecteur ou le stockage sans toucher aux autres étapes. La plupart des étapes fournissent aussi un squelette commun, qu'un nouveau composant complète. Seul le détecteur est obligatoire.

Le fichier de configuration sait construire chaque composant, mais aucun composant ne dépend de ce fichier. On peut donc utiliser PIIGhost dans du code, sans configuration. Le cœur de la librairie ne contient aucune règle propre à une langue. Les listes de mots français ou d'un métier vont dans les groupes du hub.

Cette décision vit dans `components/*/base.py`. Voir [Ajouter ou remplacer un composant](../architecture/ports-and-extension.md).

### DEC-22 : Rendre asynchrones les étapes qui attendent

Les détecteurs à modèle et les serveurs distants mettent du temps à répondre. Les étapes qui les attendent sont donc asynchrones, c'est-à-dire qu'elles laissent l'application traiter d'autres demandes pendant l'attente. C'est le cas de la détection, des listes et du garde-fou. Les étapes de pur calcul, comme le regroupement ou le remplacement, restent ordinaires.

Cette décision vit dans `pipeline/base.py`.

Les termes sont définis dans le [glossaire](../glossary.md).
