---
icon: lucide/list-checks
---

# Roadmap

Cette page liste ce qui reste en attente pour `piighost` et les capacités écartées volontairement. Tout ce que la réécriture v2 a livré est documenté dans le reste du site. Détecteurs enfichables, linking et résolution d'entités, placeholder factories, guard de PII résiduelle, mémoire de conversation Redis à valeurs chiffrées, configuration TOML et JSON, middleware LangChain, et observation OpenTelemetry.

!!! note "Comment lire cette page"
    Cette roadmap n'est pas un engagement de calendrier. Elle liste les items identifiés comme encore manquants, pas une promesse de les construire dans l'ordre.

## ~~Proxy compatible OpenAI~~

~~Livré dans `piighost-api` : un endpoint compatible OpenAI sous `/openai/v1` où une application ne change que son `base_url`, nomme le vrai upstream dans un header, et le proxy anonymise chaque requête, la relaie, puis désanonymise la réponse. L'affaire HTTP vit dans `piighost-api`, pas dans cette bibliothèque.~~

## Cache de résultat optionnel

La mémoire de conversation cache les détections de chaque message par thread, donc renvoyer un message dans un thread évite la détection. Il n'existe pas de cache sous le thread, donc le même texte envoyé sous deux `thread_id` différents est détecté deux fois. Un cache de résultat optionnel clé par hash de texte laisserait un contenu identique éviter la détection quel que soit le thread, avec un backend SQLAlchemy (aiosqlite pour le développement, PostgreSQL pour un déploiement partagé) comme option persistante à côté de celle en processus.

## ~~Câblage du décodeur de streaming~~

~~Désormais câblé : `AsyncPlaceholderStreamDecoder` atteint les intégrations via `TextDeidentifier.deanonymize_stream`, exposé sur le middleware LangChain sous `deanonymize_stream` et utilisé par le proxy Anthropic dans `piighost-api`. Une app l'enveloppe autour de sa propre boucle de streaming pour désanonymiser une réponse à la volée, en ne tamponnant qu'au passage d'un token. Toute factory construit aussi le décodeur brut sur sa grammaire avec `async_stream_decoder`, pour un autre framework.~~

## Hub de configurations

Un pipeline est entièrement décrit par un fichier TOML ou JSON, mais chaque utilisateur reconstruit cette description à la main. Un hub de configurations laisserait un utilisateur récupérer une configuration prête à l'emploi via un identifiant court et la lancer directement, comme un hub de prompts distribue des prompts. La bibliothèque a déjà les briques sur lesquelles il s'appuie, `load_config`, `load_pipeline` et `load_thread_pipeline` parsent et construisent un pipeline depuis un fichier. Ce qui manque est la distribution, un registre pour publier et récupérer une configuration par identifiant, l'épinglage de version à une release piighost, et une frontière de confiance, puisqu'une configuration est de la donnée déclarative et non du code. Un catalogue de configurations par métier, notaires, comptables, un défaut généraliste, grandirait par-dessus au fil du temps.

## Intégration aux harness d'agents

Le proxy compatible OpenAI de `piighost-api` dé-identifie déjà tout harness qui laisse une application changer son `base_url`. Un harness d'agent de code comme Claude Code parle l'API Messages d'Anthropic plutôt que la forme OpenAI, donc le couvrir suppose soit un endpoint proxy compatible Anthropic, soit les hooks propres au harness. La dé- et ré-anonymisation, le réassemblage du streaming et la gestion de la frontière des outils vivent déjà dans le pipeline conversationnel et le middleware, donc c'est surtout un nouvel adaptateur de transport devant le cœur existant plutôt qu'un nouveau travail d'anonymisation.

## Application document locale dans le navigateur (WebAssembly)

Une application web d'anonymisation de documents qui tourne entièrement dans le navigateur, pour qu'un professionnel réglementé dé-identifie un fichier client sans qu'aucune donnée ne quitte la machine, répond aux contraintes de confidentialité et de consentement remontées de façon répétée autour des données clients. Le moteur existe déjà, le site du projet fait tourner le vrai piighost dans le navigateur via Pyodide, avec détection GLiNER dans le navigateur, donc la bibliothèque elle-même n'a rien à réimplémenter. Ce qui reste est l'application autour, le parsing de documents côté client (PDF, DOCX) et l'OCR, une étape de revue où l'utilisateur valide ou complète l'anonymisation, et une étape de partage. C'est une application distincte bâtie sur la bibliothèque, pas une fonctionnalité de la bibliothèque.

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
- **Journal d'audit inviolable.** Un journal append-only chaîné par hash des événements de dé- et ré-anonymisation, où une entrée supprimée ou modifiée devient détectable, est une fonctionnalité d'accountability pour un déploiement multi-utilisateur ou hébergé, pas pour la bibliothèque. Il revient à `piighost-api` ou `piighost-chat`, où existent un acteur, un magasin et une frontière de confiance. Le contrôle d'accès sur un sink append-only est la défense principale, et le chaînage n'ajoute de la valeur que si le custodian du magasin n'est pas de confiance ou si un tiers a besoin d'une preuve portable. La bibliothèque expose les événements ; les enregistrer de façon inviolable relève du déploiement.

La regex par forme seule, sans validation de checksum, est un autre hors-périmètre assumé. Voir [Limitations](limitations.md).

## Voir aussi

- [Placeholder factories](placeholder-factories.md) : les axes de tags et les factories actuels.
- [Sécurité](security.md) : le modèle de menace et la comparaison des backends de mémoire.
- [Déployer un pipeline en production](deployment.md) : la mémoire Redis en production.
