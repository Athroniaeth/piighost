---
icon: lucide/list-checks
---

# Roadmap

Cette page liste ce qui reste en attente pour `piighost` et les capacités écartées volontairement. Tout ce que la réécriture v2 a livré est documenté dans le reste du site. Cela comprend les détecteurs enfichables, linking et résolution d'entités, placeholder factories, guard de données confidentielles résiduelles, mémoire de conversation Redis à valeurs chiffrées, configuration TOML et JSON, middleware LangChain, et observation OpenTelemetry.

!!! note "Comment lire cette page"
    Cette roadmap n'est pas un engagement de calendrier. Elle liste les items identifiés comme encore manquants, pas une promesse de les construire dans l'ordre.

## ~~Proxy compatible OpenAI~~

~~Livré dans `piighost-api`, sous la forme d'un endpoint compatible OpenAI sous `/openai/v1`. Une application ne change que son `base_url` et nomme le vrai upstream dans un header. Le proxy dé-identifie chaque requête, la relaie, puis restaure la réponse. La partie HTTP vit dans `piighost-api`, pas dans cette bibliothèque. Voir [Dé-identifier un client OpenAI avec le proxy](examples/openai-proxy.md).~~

## Cache de résultat optionnel

La mémoire de conversation cache les détections de chaque message par conversation, donc renvoyer un message dans une conversation évite la détection. Aucun cache n'est partagé entre conversations, donc le même texte envoyé sous deux `thread_id` différents est détecté deux fois. Un cache de résultat optionnel, indexé par le hash du texte, laisserait un contenu identique éviter la détection quelle que soit la conversation. Un backend SQLAlchemy (aiosqlite pour le développement, PostgreSQL pour un déploiement partagé) en serait l'option persistante, à côté de l'option en processus.

## ~~Câblage du décodeur de streaming~~

~~Désormais câblé, `AsyncPlaceholderStreamDecoder` atteint les intégrations via `TextDeidentifier.deanonymize_stream`. Le middleware LangChain expose cette méthode sous `deanonymize_stream`, et le proxy Anthropic de `piighost-api` l'utilise. Une app enveloppe `deanonymize_stream` autour de sa propre boucle de streaming pour restaurer une réponse à la volée, en ne tamponnant qu'au passage d'un jeton. Pour un autre framework, toute factory construit aussi le décodeur brut sur sa grammaire avec `async_stream_decoder`.~~

## ~~Hub de configurations~~

~~Désormais livré comme projet séparé, le [hub piighost](https://hub.piighost.dev) publie des groupes de motifs relus et des configurations de pipeline complètes sous un identifiant court, chacune épinglée par commit. Un détecteur regex tire un groupe via `catalogs`. `load_config`, `load_pipeline`, `load_thread_pipeline` et `piighost --config` prennent une référence comme `hub:piighost/fr-notarial` pour lancer une configuration directement.~~

## ~~Intégration aux harness d'agents~~

~~Désormais livré pour Claude Code, via son système de hooks. `piighost.integrations.claude_code` dé-identifie le prompt et les sorties d'outils, et restaure les entrées d'outils. Il passe par un client léger vers `piighost-api`. Voir [Dé-identifier Claude Code avec les hooks](examples/claude-code.md). Le proxy compatible OpenAI de `piighost-api` couvre toujours tout harness qui laisse une application changer son `base_url`. À côté des hooks, `piighost-api` fournit aussi un endpoint proxy compatible Anthropic, pour les harness qui parlent l'API Messages d'Anthropic. Ce proxy réutilise ce que le cœur fait déjà, c'est-à-dire la dé-identification et la restauration, le réassemblage du streaming et la gestion de la frontière des outils. Voir [Dé-identifier Claude Code avec le proxy Anthropic](examples/anthropic-proxy.md).~~

## Application document locale dans le navigateur (WebAssembly)

Une application web de dé-identification de documents qui tourne entièrement dans le navigateur répond aux contraintes de confidentialité et de consentement remontées de façon répétée autour des données clients. Un professionnel réglementé y dé-identifie un fichier client sans qu'aucune donnée ne quitte la machine. Le moteur existe déjà. Le site du projet fait tourner le vrai `piighost` dans le navigateur via Pyodide, avec une détection GLiNER elle aussi dans le navigateur. La bibliothèque elle-même n'a donc rien à réimplémenter. Il reste à construire l'application autour. Elle comprend le parsing de documents côté client (PDF, DOCX) et l'OCR, une étape de revue où l'utilisateur valide ou complète la dé-identification, et une étape de partage. C'est une application distincte bâtie sur la bibliothèque, pas une fonctionnalité de la bibliothèque.

## Hors périmètre

Certaines capacités ont été envisagées puis écartées volontairement. Le raisonnement est consigné ici pour que la frontière soit explicite. Chacune pourrait être réexaminée si un besoin futur répond à la réserve qui l'a fait écarter.

- **Placeholders surrogates réalistes (Faker).** Un faux plausible se lit naturellement, mais un vivier fini de faux finit par produire des collisions. Deux personnes peuvent tirer le même surrogate, et un faux peut coïncider avec une vraie valeur, donc la substitution n'est pas restaurable de façon fiable. `piighost` garde plutôt des jetons synthétiques sans collision.
- **Chiffrer la valeur dans le jeton.** La restauration lit la map jeton-vers-valeur depuis la mémoire de conversation, pas un chiffré autoportant. Embarquer le chiffré donne un jeton long que le modèle doit recracher mot pour mot. Le modèle le fait de façon peu fiable.
- **Hachage déterministe de la valeur.** Un hash à clé d'une valeur à faible entropie comme un prénom ou un e-mail est réversible par dictionnaire et révèle l'égalité des valeurs entre enregistrements. Le jeton d'une valeur est déjà stable au sein d'une conversation, et les jointures cross-corpus ne sont pas le cas d'usage visé.
- **Bloquer des requêtes ou supprimer des données confidentielles.** `piighost` sécurise les données confidentielles en les détectant et en les dé-identifiant. Refuser une requête ou effacer une valeur relève de la politique de l'appelant, décidée à partir des détections que `piighost` expose, pas imposée ici.
- **Schémas qui transforment la valeur, décalage de dates et chiffrement format-preserving.** `piighost` substitue un span détecté par un jeton restaurable, pas une valeur transformée. Le décalage de dates sort de ce modèle, et les schémas FPE courants FF3 et FF3-1 ont été retirés du standard NIST.
- **Détection de quasi-identifiants.** Une valeur comme un âge, un code postal ou une date de rendez-vous n'identifie personne seule, mais peut ré-identifier une personne en combinaison. Sweeney a montré que code postal plus date de naissance plus sexe est quasi unique. `piighost` détecte et dé-identifie des valeurs identifiables, pas des combinaisons ré-identifiantes. Contre une combinaison, les seules réponses sont de généraliser la valeur ou de la remplacer par un faux. Les deux transforment la valeur, et sont déjà hors périmètre.
- **Modèles de confidentialité analytiques (k-anonymity, l-diversity, t-closeness, differential privacy, données synthétiques).** Ils protègent un jeu de données entier publié pour analyse, en généralisant ou en ajoutant du bruit sur toutes les lignes d'un coup. `piighost` protège un flux conversationnel un message à la fois. De plus, ces modèles reposent sur la généralisation, qui transforme la valeur et sort donc déjà du périmètre.
- **Routage de placeholder par type de label.** Un pipeline applique une seule placeholder factory à toutes les entités. Router selon le label, par exemple un counter pour les noms et un masque pour les numéros de carte, est mécaniquement léger. Mais la garantie de tag du pipeline tombe alors à celle de la factory la plus faible du lot. Le routage casse aussi la garantie d'identité reconnaissable, dont le middleware a besoin pour restaurer. Le gain ne justifiait pas de brouiller le design à base de tags.
- **Dé-identification multimodale.** `piighost` lit du texte. Détecter des données confidentielles dans une image ou un flux audio supposerait de l'OCR ou de la transcription, puis d'éditer les pixels ou les échantillons, car un jeton ne se replace pas dans une image comme dans du texte. Caviarder une zone est un autre problème, sans restauration fiable. Le caviardage reste donc hors du modèle de substitution de texte.
- **Journal d'audit inviolable.** Un journal inviolable est un journal append-only des événements de dé-identification et de restauration, chaîné par hash, où une entrée supprimée ou modifiée devient détectable. C'est une fonctionnalité d'accountability pour un déploiement multi-utilisateur ou hébergé, pas pour la bibliothèque. Il revient à `piighost-api` ou `piighost-chat`, où existent un acteur, un magasin et une frontière de confiance. Le contrôle d'accès sur un sink append-only est la défense principale. Le chaînage n'ajoute de la valeur que si celui qui garde le magasin n'est pas de confiance, ou si un tiers a besoin d'une preuve portable. La bibliothèque expose les événements. Les enregistrer de façon inviolable relève du déploiement.

La regex par forme seule, sans validation de checksum, est un autre hors-périmètre assumé. Voir [Limitations](limitations.md).

## Voir aussi

- [Placeholder factories](placeholder-factories.md) : les axes de tags et les factories actuels.
- [Sécurité](security.md) : le modèle de menace et la comparaison des backends de mémoire.
- [Déployer un pipeline en production](deployment.md) : la mémoire Redis en production.
