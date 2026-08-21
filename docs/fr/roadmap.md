---
icon: lucide/list-checks
---

# Roadmap

Cette page liste ce qui reste en attente pour `piighost` et les capacités écartées volontairement. Tout ce que la réécriture v2 a livré est documenté dans le reste du site. Détecteurs enfichables, linking et résolution d'entités, placeholder factories, guard de PII résiduelle, mémoire de conversation Redis à valeurs chiffrées, configuration TOML et JSON, middleware LangChain, et observation OpenTelemetry.

!!! note "Comment lire cette page"
    Cette roadmap n'est pas un engagement de calendrier. Elle liste les items identifiés comme encore manquants, pas une promesse de les construire dans l'ordre.

## Proxy compatible OpenAI

`piighost` dé-identifie aujourd'hui à l'intérieur d'un framework d'agent, via le middleware LangChain ou les hooks Pydantic AI. Un proxy déplacerait cette protection à la frontière HTTP. `piighost-api` exposerait un endpoint compatible OpenAI, une application ne change donc que son `base_url` et n'a besoin d'aucun autre code. À chaque appel `/v1/chat/completions`, le proxy anonymise les messages, relaie la requête anonymisée au vrai fournisseur, désanonymise la réponse, et la renvoie au format OpenAI, le fournisseur ne reçoit donc jamais `Patrick`{ .pii }, seulement `<<PERSON:1>>`{ .placeholder }. Le même proxy se place devant n'importe quel endpoint compatible OpenAI, comme Azure OpenAI ou un serveur auto-hébergé.

Trois briques existent déjà pour ça. Le pipeline conversationnel anonymise et restaure, la dé-identification de la frontière des outils couvre les appels d'outils, et le décodeur de streaming réécrit un jeton coupé entre deux chunks server-sent-event. Les questions ouvertes sont la façon dont une requête sans état cadre ses jetons, via un thread par requête ou un header d'identifiant de thread adossé à la mémoire de conversation, et la part du streaming et des appels d'outils qu'une première version couvre.

Au-delà du format OpenAI, le même cœur de dé-identification pourrait se placer derrière plusieurs protocoles de fournisseur, une route OpenAI `/v1`, une route Anthropic Messages, une route Bedrock, chacune un mince adaptateur sur le pipeline partagé, pour qu'une application garde son SDK natif et ne pointe que vers le proxy.

## Normalisation de texte

Un détecteur voit le texte exactement tel qu'il est écrit. Accents, casse, espacement ou bruit d'OCR peuvent cacher une valeur à une regex ou décaler les frontières d'un modèle NER. Un étage de normalisation tournerait avant la détection, en donnant au détecteur une forme nettoyée tout en gardant une carte d'offsets vers le texte d'origine, pour qu'un span trouvé sur le texte normalisé soit remonté sur le texte brut au moment du remplacement. La remontée d'offset est le point délicat, car une normalisation qui insère ou supprime des caractères ne s'aligne plus un pour un avec la source.

## Cache de résultat optionnel

La mémoire de conversation cache les détections de chaque message par thread, donc renvoyer un message dans un thread évite la détection. Il n'existe pas de cache sous le thread, donc le même texte envoyé sous deux `thread_id` différents est détecté deux fois. Un cache de résultat optionnel clé par hash de texte laisserait un contenu identique éviter la détection quel que soit le thread, avec un backend SQLAlchemy (aiosqlite pour le développement, PostgreSQL pour un déploiement partagé) comme option persistante à côté de celle en processus.

## Câblage du décodeur de streaming

`AsyncPlaceholderStreamDecoder` réassemble déjà un token coupé entre deux chunks server-sent-event, mais rien ne le relie encore aux intégrations. Une réponse en streaming arrive en fragments, donc `<<PER`{ .placeholder } peut tomber dans un chunk et `SON:1>>`{ .placeholder } dans le suivant, et une restauration naïve laisse l'utilisateur voir le token cassé. Câbler le décodeur dans le middleware LangChain, les hooks Pydantic AI et le futur proxy laisserait chacun désanonymiser un flux à la volée, en ne tamponnant qu'au passage d'un token et en émettant le texte restauré au fil de l'eau. Cela finit une brique existante plutôt que d'en construire une neuve, et c'est un prérequis du streaming à travers le proxy.

## Hors périmètre

Certaines capacités ont été envisagées puis écartées volontairement. Le raisonnement est consigné ici pour que la frontière soit explicite. Un besoin futur qui répond au caveat pourrait réexaminer chacune d'elles.

- **Placeholders surrogates réalistes (Faker).** Un faux plausible se lit naturellement, mais un vivier de faux fini finit par collisionner. Deux personnes peuvent tirer le même surrogate, et un faux peut coïncider avec une vraie valeur, donc la substitution n'est pas restaurable de façon fiable. piighost garde plutôt des jetons synthétiques sans collision.
- **Chiffrer la valeur dans le jeton.** La restauration lit la map jeton-vers-valeur depuis la mémoire de conversation, pas un chiffré autoportant. Embarquer le chiffré donne un jeton long que le modèle doit recracher mot pour mot, ce qu'il fait de façon peu fiable.
- **Hachage déterministe de la valeur.** Un hash à clé d'une valeur à faible entropie comme un prénom ou un e-mail est réversible par dictionnaire et révèle l'égalité des valeurs entre enregistrements. Le jeton d'une valeur est déjà stable au sein d'un thread, et les jointures cross-corpus ne sont pas le cas d'usage visé.
- **Bloquer des requêtes ou supprimer des PII.** piighost sécurise les PII en les détectant et en les anonymisant. Refuser une requête ou effacer une valeur relève de la politique de l'appelant, décidée à partir des détections que piighost expose, pas imposée ici.
- **Schémas qui transforment la valeur, décalage de dates et chiffrement format-preserving.** piighost substitue un span détecté par un jeton restaurable, pas une valeur transformée. Le décalage de dates sort de ce modèle, et les schémas FPE courants FF3 et FF3-1 ont été retirés du standard NIST.
- **Détection de quasi-identifiants.** Une valeur comme un âge, un code postal ou une date de rendez-vous n'identifie personne seule mais peut ré-identifier en combinaison, Sweeney a montré que code postal plus date de naissance plus sexe est quasi unique. piighost détecte et tokenise des valeurs identifiables, pas des combinaisons ré-identifiantes, car les seules réponses, généraliser la valeur ou la remplacer par un faux, la transforment et sont déjà hors périmètre.
- **Modèles de confidentialité analytiques (k-anonymity, l-diversity, t-closeness, differential privacy, données synthétiques).** Ils protègent un jeu de données entier publié pour analyse, en généralisant ou en ajoutant du bruit sur toutes les lignes d'un coup. piighost protège un flux conversationnel un message à la fois, et la généralisation sur laquelle ils reposent transforme la valeur, ce qui est déjà hors périmètre.
- **Routage de placeholder par type de label.** Un pipeline applique une seule placeholder factory à toutes les entités. Router selon le label, un counter pour les noms mais un masque pour les numéros de carte, est mécaniquement léger mais rabaisse la garantie de tag du pipeline à la factory la plus faible du lot et casse la garantie d'identité reconnaissable dont le middleware a besoin pour restaurer. Le gain ne justifiait pas de brouiller le design à base de tags.
- **Dé-identification multimodale.** piighost lit du texte. Détecter des PII dans une image ou un flux audio supposerait de l'OCR ou de la transcription, puis d'éditer les pixels ou les échantillons, car un token ne se replace pas dans une image comme dans du texte. Caviarder une zone est un autre problème, sans restauration fiable, donc cela reste hors du modèle de substitution de texte.

La regex par forme seule, sans validation de checksum, est un autre hors-périmètre assumé. Voir [Limitations](limitations.md).

## Voir aussi

- [Placeholder factories](placeholder-factories.md) : les axes de tags et les factories actuels.
- [Sécurité](security.md) : le modèle de menace et la comparaison des backends de mémoire.
- [Déployer un pipeline en production](deployment.md) : la mémoire Redis en production.
