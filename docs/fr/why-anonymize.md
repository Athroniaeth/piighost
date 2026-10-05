---
icon: lucide/shield-alert
---

# Pourquoi dé-identifier ?

Le constat qui justifie de dé-identifier les données personnelles avant qu'elles n'atteignent un LLM tient indépendamment de `piighost`. Il est posé ci-dessous pour un lecteur technique ou non, de façon à être opposable à un décideur ou à un interlocuteur sceptique.

La réflexion se construit en trois temps. D'abord, comment un LLM en cloud fonctionne techniquement et pourquoi la promesse contractuelle d'un fournisseur de ne pas exploiter la donnée ne suffit pas. Ensuite, le cadre juridique qui s'applique à ces services, et ses zones grises. Enfin, ce que la dé-identification change concrètement, les cas où elle est avantageuse et ce qu'elle ne résout pas.

!!! abstract "TLDR"
    - Un texte envoyé à un LLM en cloud est lu en clair par le fournisseur, journalisé et conservé.
    - La promesse du fournisseur de ne pas exploiter vos données peut tomber, par un incident, une exploitation pour l'entraînement ou une injonction judiciaire.
    - Le droit ne suffit pas non plus. Une loi américaine comme le CLOUD Act peut contraindre un fournisseur américain, même pour des données hébergées en Europe.
    - Une fois collectées, ces données peuvent être croisées pour de la surveillance de masse, du fichage politique ou du ciblage publicitaire.
    - Dé-identifier avant l'envoi retire les valeurs sensibles du texte, sans dépendre du fournisseur, de sa promesse, de la sécurité de son infrastructure ni d'une décision politique future.
    - La dé-identification ne règle pas tout, voir [Ce que la dé-identification ne résout pas](#ce-que-la-de-identification-ne-resout-pas).

!!! note "Dé-identification, pas anonymisation"
    `piighost` remplace chaque donnée personnelle par un jeton, c'est-à-dire un texte de remplacement comme `<<PERSON:1>>`{ .placeholder }. Il garde le lien entre le jeton et la valeur d'origine, pour restaurer la vraie valeur ensuite. Au sens du RGPD, c'est de la **pseudonymisation**, pas de l'anonymisation. Cette documentation emploie partout le mot dé-identification. Le mot anonymisation est réservé à un retrait irréversible, sans restauration possible, et signalé comme tel quand il apparaît.

---

## Fonctionnement d'un LLM en cloud

Un LLM comme ChatGPT, Claude ou Mistral Le Chat n'est pas un logiciel qui tourne sur votre ordinateur. C'est un service distant. Votre question quitte votre machine, traverse Internet, arrive sur les serveurs du fournisseur, y est traitée, puis une réponse revient.

!!! warning "L'interface peut être locale, le modèle ne l'est pas"
    Même si vous utilisez une application de bureau, une extension navigateur ou un plugin IDE, le modèle n'est pas exécuté sur votre machine. Seule l'interface l'est. Le calcul a lieu dans le cloud du fournisseur. Le terme "LLM local" désigne uniquement l'inférence sur votre propre matériel via des outils comme Ollama ou llama.cpp.

Le trajet de votre message a plusieurs conséquences souvent sous-estimées :

- Le message est reçu en clair par l'infrastructure du fournisseur. Le chiffrement TLS protège le transit, il ne protège pas la lecture côté serveur.
- Il est généralement journalisé pour la facturation, la détection d'abus, le débogage et l'amélioration du modèle.
- Il peut être conservé pendant des semaines, des mois ou des années, selon la politique du fournisseur et les obligations légales qui s'imposent à lui.

Parler à un LLM en cloud n'est, du point de vue de la confidentialité, pas plus privé qu'envoyer un e-mail via Gmail. Le fournisseur a un accès technique complet au contenu. Tout ce qui empêche cet accès est contractuel, pas technique.

---

## Les limites d'une promesse contractuelle

Partons du principe le plus favorable. Les grands fournisseurs (OpenAI, Anthropic, Google, Mistral et les autres) veulent sincèrement protéger les données de leurs utilisateurs. Leurs politiques de confidentialité contractualisent des engagements ("nous n'entraînons pas sur vos données API", "nous supprimons après 30 jours", "nous refusons les demandes abusives"), et ces engagements sont généralement tenus.

Cela ne suffit pas, parce qu'un engagement contractuel peut tomber pour trois raisons différentes, dont aucune ne relève de la mauvaise foi du fournisseur.

### Un incident technique, un bug ou une attaque

Aucune politique ne protège contre une erreur d'ingénierie ou une intrusion réussie. Deux cas suffisent à l'illustrer.

Le 20 mars 2023, un bug dans la bibliothèque Redis utilisée par OpenAI a exposé pendant environ neuf heures les titres de conversations ChatGPT à d'autres utilisateurs. Pour environ 1,2 % des abonnés ChatGPT Plus actifs dans la fenêtre concernée, des informations de paiement partielles (nom, e-mail, quatre derniers chiffres de la carte bancaire, date d'expiration) ont également été visibles à des comptes tiers. OpenAI a publié un post-mortem public reconnaissant l'incident.

En janvier 2025, les chercheurs de Wiz Research ont découvert qu'une base ClickHouse de DeepSeek était accessible sur Internet, sans authentification. Plus d'un million de lignes de logs y étaient exposées, incluant des historiques de conversations, des clés d'API et des métadonnées internes de l'infrastructure.

Dans les deux cas, les données ont fuité sans procès, sans injonction et sans intention malveillante de l'entreprise. Un bug, une configuration manquante, et le périmètre contractuel perd son sens.

### L'exploitation de vos données pour l'entraînement

"Si c'est gratuit, c'est vous le produit." Le principe, vieux comme le Web commercial, s'applique aussi aux LLM.

L'inférence d'un grand modèle coûte cher. Chaque réponse mobilise des GPU en temps réel, et le fournisseur paie cette facture à chaque requête. Pourtant, OpenAI, Google et d'autres proposent des offres gratuites très généreuses. Les raisons commerciales classiques (acquisition d'utilisateurs, effet de standard de facto) n'expliquent qu'une partie du modèle économique. Ces offres alimentent aussi la collecte de données d'entraînement.

Sur les offres grand public gratuites, vos conversations peuvent être exploitées pour améliorer le modèle de plusieurs façons. Le feedback explicite (👍/👎, reformulation, régénération d'une réponse) sert de signal d'apprentissage par renforcement. Les échanges peuvent être relus par des annotateurs humains pour identifier les cas d'échec. L'ensemble des conversations peut servir de matière première pour construire les jeux de données des itérations suivantes.

Les offres payantes (API, ChatGPT Enterprise, Claude Team, etc.) excluent généralement vos données de l'entraînement par défaut. Sur les offres gratuites en revanche, le refus de l'entraînement est souvent enfoui dans les paramètres, parfois désactivé par défaut, et la politique peut évoluer avec le temps.

### Une injonction judiciaire

Même quand le fournisseur *veut* supprimer vos données, un tribunal peut l'en empêcher.

Le 13 mai 2025, dans le cadre de son procès contre OpenAI, le New York Times a obtenu de la *Magistrate Judge* Ona T. Wang une ordonnance de préservation. OpenAI devait conserver toutes les conversations ChatGPT et les appels API de ses clients, y compris celles que l'entreprise aurait normalement supprimées selon sa propre politique. OpenAI s'y est opposée publiquement. Elle a d'abord déposé une motion de reconsidération, qui a été refusée. Elle a ensuite fait appel devant le *District Judge* Sidney Stein, qui a rejeté l'appel en juin 2025. L'ordonnance a finalement été levée le 26 septembre 2025 (terminaison formelle le 9 octobre). Les utilisateurs de l'EEE, de Suisse et du Royaume-Uni avaient par ailleurs été exemptés de la mesure.

L'affaire ne s'arrête pas là. Le 7 novembre 2025, la même *Magistrate Judge* a ordonné à OpenAI de livrer au New York Times 20 millions de logs ChatGPT dé-identifiés à des fins de preuve. OpenAI a demandé une reconsidération, refusée, puis a fait appel. Le 5 janvier 2026, le *District Judge* Stein a affirmé la décision, scellant l'obligation de livraison.

Cet épisode a deux conséquences pratiques. D'abord, la politique de confidentialité d'un fournisseur n'est jamais définitive, parce qu'une décision de justice à laquelle vous n'êtes pas partie peut la réécrire, imposer la conservation ou forcer la livraison massive de conversations à un tiers. Ensuite, vos données restent exposées plus longtemps à une future fuite ou attaque. La probabilité qu'une autorité publique y accède grandit d'autant, qu'elle soit américaine ou étrangère via une commission rogatoire internationale.

---

## Le droit ne suffit pas non plus

La réponse instinctive à ce constat technique est de se tourner vers le droit, c'est-à-dire choisir un fournisseur "conforme RGPD", vérifier les certifications, exiger des clauses contractuelles. Cette approche est utile mais incomplète, pour deux raisons. Le droit américain donne des voies d'accès légales aux données, et le droit européen n'a pas encore produit de garde-fou appliqué sur les LLM.

### Le cadre américain, CLOUD Act, FISA 702 et Executive Order 12333

Trois textes structurent l'accès américain aux données des fournisseurs. Aucun des trois n'est le Patriot Act.

!!! info "Pourquoi pas le Patriot Act ?"
    Le Patriot Act (2001) revient souvent dans ce débat, mais il n'est plus le bon texte à citer. Sa disposition la plus connue pour la surveillance, la Section 215 (collecte massive de métadonnées téléphoniques révélée par Snowden), a été restreinte par le USA FREEDOM Act en 2015, puis laissée expirer par le Congrès en mars 2020. Elle n'est plus en vigueur. Par ailleurs, le Patriot Act visait les enquêtes antiterroristes, pas la question qui nous intéresse ici ("un fournisseur américain peut-il être contraint de livrer des données stockées en Europe ?"). Les arrêts de la CJUE qui structurent le débat actuel ne citent pas le Patriot Act, ils citent FISA 702 et l'Executive Order 12333.

- **Le CLOUD Act (2018)** oblige tout fournisseur sous juridiction américaine à livrer les données qu'il contrôle, peu importe où ces données sont physiquement stockées. Un datacenter en Irlande ou en France ne met pas les données hors de portée dès que l'entreprise est américaine.
- **FISA Section 702** est la base légale des programmes de surveillance de masse comme PRISM, révélés en 2013 par Edward Snowden. Il permet la collecte de communications via les grands fournisseurs américains de services de communication électronique.
- **Executive Order 12333** est le cadre plus large de la surveillance par l'exécutif américain, sans supervision judiciaire directe.

Ces trois textes se cumulent et offrent des voies d'accès légales, discrètes (sans notification préalable aux personnes concernées), et applicables aux données des citoyens non américains.

### Schrems II, la CJUE invalide le Privacy Shield

En juillet 2020, la Cour de justice de l'Union européenne a invalidé le Privacy Shield, l'accord qui encadrait les transferts de données entre l'UE et les États-Unis. En résumé, la Cour a jugé que FISA 702 et l'Executive Order 12333 sont trop permissifs pour respecter le RGPD, et qu'ils n'offrent aucun recours judiciaire effectif aux citoyens européens.

Plus de 5 300 entreprises s'appuyaient sur le Privacy Shield pour leurs transferts transatlantiques. Un second accord, le Data Privacy Framework (2023), a remplacé le précédent, mais il repose sur les mêmes fondations juridiques américaines et sa durabilité est contestée. Plusieurs plaintes (notamment celles portées par l'association noyb de Max Schrems) visent explicitement une troisième invalidation.

### Microsoft Ireland, la juridiction prime la géographie

Entre 2013 et 2018, les autorités américaines ont exigé de Microsoft, via un mandat émis sous le Stored Communications Act, qu'elle livre des données d'un client stockées sur ses serveurs en Irlande. Microsoft a résisté jusqu'à la Cour Suprême. La procédure n'a jamais été tranchée sur le fond, parce que le Congrès a voté le CLOUD Act en mars 2018 pour clarifier la réponse. Ce texte dit que les entreprises américaines doivent livrer les données, où qu'elles soient stockées. L'affaire a été déclarée sans objet.

Il en découle directement que l'hébergement européen par un fournisseur américain n'offre pas d'étanchéité juridique face aux États-Unis. Le marketing "vos données restent en Europe" masque cette asymétrie.

!!! note "Une nuance honnête sur le champ d'application"
    Le CLOUD Act ne s'applique pas à n'importe quelle entreprise ayant un simple lien avec les États-Unis. Il faut que l'entité soit sous juridiction américaine (incorporée aux US ou contrôlée par une entité américaine) et qu'elle ait la "possession, la garde ou le contrôle" des données. Un fournisseur européen avec une simple filiale commerciale américaine n'est pas automatiquement captif. Une analyse au cas par cas est nécessaire.

### Le cadre européen, un RGPD qui n'a pas encore tenu sur les LLM

Le RGPD reste un outil solide sur le papier, mais sa mise en œuvre sur les LLM est balbutiante. L'affaire la plus emblématique le montre.

La Garante, autorité italienne de protection des données (équivalent de la CNIL), ouvre une enquête contre OpenAI dès mars 2023. En décembre 2024, elle inflige une amende de 15 millions d'euros à OpenAI pour traitement sans base légale, manquements à la transparence et absence de mécanisme de vérification d'âge. Mais en mars 2026, le tribunal de Rome annule cette décision dans son intégralité. Au 4 octobre 2026, aucune autorité européenne n'a fait confirmer en dernier ressort une sanction contre un grand LLM pour violation du RGPD sur la phase de collecte d'entraînement.

Le RGPD reste puissant, mais compter uniquement sur lui pour protéger des données sensibles envoyées à un LLM, c'est parier sur un rempart qui n'a pas encore démontré sa capacité à tenir en appel.

---

## Ce que permettent les données collectées

Les sections précédentes expliquent comment les données sortent de votre périmètre. Reste à préciser ce qu'elles rendent possible une fois collectées. Trois usages, inégalement documentés, méritent d'être distingués pour ne pas amalgamer un risque structurel et une pratique avérée.

### Surveillance de masse

Une conversation LLM ressemble techniquement à un e-mail ou un chat, c'est-à-dire du texte daté, rattaché à un compte identifiable. Elle tombe dans le même périmètre de collecte que les autres communications électroniques couvertes par FISA 702. Ce texte a été renouvelé pour deux ans en avril 2024 par le RISAA. Les rapports déclassifiés du PCLOB documentent plusieurs centaines de milliers de sélecteurs (identifiants de cibles) actifs chaque année. La collecte "à propos" des cibles (suspendue en 2017, réautorisée ensuite) élargit mécaniquement le périmètre à des communications qui ne sont ni envoyées à la cible ni par la cible, mais qui la mentionnent.

Que cette capacité soit aujourd'hui appliquée aux conversations LLM ou non, le cadre juridique et l'architecture technique sont en place.

### Fichage et ciblage politique

L'inquiétude n'est pas spéculative. Elle s'appuie sur des cas documentés de surveillance ciblée dans d'autres couches de l'Internet.

- **Angela Merkel, octobre 2013** : les révélations Snowden documentent la surveillance par la NSA du téléphone portable de la chancelière allemande, inscrit comme cible depuis 2002. Les sources allemandes (Süddeutsche Zeitung, NDR) indiquent que Gerhard Schröder, prédécesseur de Merkel, avait lui aussi été surveillé à partir de 2002, en raison de son opposition à l'intervention en Irak. Obama a confirmé implicitement en promettant par téléphone que la surveillance était terminée. Le gouvernement allemand a publiquement protesté.
- **Associated Press, 2012-2013** : le Department of Justice saisit secrètement en avril-mai 2012 les relevés de plus de vingt lignes téléphoniques AP, dans le cadre d'une enquête sur une fuite. L'agence ne l'apprend qu'en mai 2013, par notification *après coup*.
- **Pegasus / NSO, 2021** : la coalition Forbidden Stories documente l'usage du spyware Pegasus contre environ 180 journalistes ciblés, ainsi que des activistes, avocats, diplomates et chefs d'État dans plus de 20 pays, dont la France, par l'intermédiaire de plusieurs États clients de NSO.

Aucun de ces cas ne concerne spécifiquement un LLM. Mais ils établissent trois faits :

- les États surveillent régulièrement les communications de journalistes, d'avocats et de personnalités politiques
- les outils juridiques et techniques pour le faire existent déjà
- un LLM qui voit passer les conversations d'un cabinet d'avocats, d'une rédaction d'investigation ou d'un mouvement militant devient, par construction, un point de concentration d'informations à haute valeur

### Ciblage commercial et courtiers en données

Le risque est différent des deux précédents. Il ne nécessite ni juge, ni mandat. Il repose sur l'écosystème commercial qui entoure les fournisseurs, et se construit en trois temps.

**D'abord, une structure d'incitation.** Plusieurs grands acteurs du LLM ont des intérêts adjacents à la publicité ciblée. Google en fait son cœur de métier, Microsoft (actionnaire majeur d'OpenAI) opère Bing Ads, Meta, dont la quasi-totalité des revenus provient du ciblage publicitaire, pousse son propre écosystème d'IA générative. Les politiques de confidentialité, seules, ne neutralisent pas cette incitation. Elles peuvent évoluer quand la pression économique monte.

**Ensuite, l'état actuel des preuves.** Rien ne prouve aujourd'hui qu'un fournisseur ait revendu des conversations LLM à des courtiers en données. L'argument ne repose donc pas sur une pratique avérée, mais sur un risque structurel. Une donnée qui entre dans le système d'un acteur qui a économiquement intérêt à l'exploiter peut en ressortir plus tard, par des canaux qui ne sont pas ceux annoncés initialement.

**Enfin, la porosité documentée entre écosystème publicitaire et surveillance.** Un rapport de l'Office of the Director of National Intelligence daté de janvier 2022 et déclassifié en juin 2023 reconnaît que les agences de renseignement américaines achètent régulièrement des données commerciales auprès de courtiers en données, notamment des données de localisation et de navigation. Ce qui est collecté pour vendre de la publicité peut donc être racheté pour surveiller, sans mandat ni notification.

Dans ce contexte, la question n'est pas "est-ce que les conversations LLM seront un jour monétisées ou revendues" mais "que reste-t-il de ce risque si les données qui quittent votre périmètre ne contiennent plus de données personnelles identifiantes ?". La dé-identification en amont retire de ces données les valeurs qui leur donnent une utilité commerciale et stratégique, avant même qu'elles n'entrent dans l'écosystème du fournisseur.

### Pourquoi la dé-identification casse ce graphe

Une donnée personnelle envoyée en clair devient un nœud dans un graphe potentiel. Elle peut être croisée avec des réseaux sociaux, des brèches antérieures, des registres publics ou des bases commerciales, pour ré-identifier, enrichir ou cibler. Un jeton `<<PERSON:1>>`{ .placeholder } ne se croise, lui, avec aucune base. La dé-identification avant envoi retire donc la valeur que toutes les chaînes d'usage secondaire décrites plus haut exploitent. Le contexte autour du jeton peut toutefois suffire à ré-identifier une personne, voir [Ce que la dé-identification ne résout pas](#ce-que-la-de-identification-ne-resout-pas).

---

## Où se placer dans le spectre des fournisseurs ?

Le choix n'est pas binaire entre "cloud américain" et "rien". Il existe un continuum, du plus exposé au plus isolé, et chaque palier modifie à la fois le risque juridique et la responsabilité qui vous incombe.

| Option | CLOUD Act / FISA 702 | RGPD | Entraînement sur vos données |
|---|---|---|---|
| Fournisseur US, serveurs US (OpenAI, Anthropic, Google) | Oui, directement | Indirect (via DPF, fragile) | Offres payantes, exclu par défaut. Offres gratuites, refus souvent enfoui |
| Fournisseur US, serveurs UE (Azure OpenAI EU, AWS Bedrock EU) | Oui (voir Microsoft Ireland) | S'applique, mais primé par l'injonction US | Exclu par défaut sur les offres entreprise |
| Fournisseur UE (Mistral, OVHcloud AI, Scaleway) | Non (sauf filiale US contrôlée) | S'applique pleinement | Exclu par défaut sur les offres payantes |
| Modèle en local (llama.cpp, Ollama, vLLM sur infra privée) | Non | Vous êtes responsable du traitement | Non, vous contrôlez |

Dans les trois premiers cas, le fournisseur garde un accès technique au contenu. Seul le modèle en local le retire, parce que vous êtes alors le fournisseur.

Au départ du spectre, le fournisseur américain hébergé aux États-Unis cumule les trois risques vus plus haut. CLOUD Act, FISA 702 et Executive Order 12333 s'appliquent sans filtre, les transferts de données depuis l'UE reposent sur le Data Privacy Framework contesté, et une injonction d'un juge américain peut forcer la conservation indéfinie des conversations. C'est le scénario le plus exposé.

Déplacer physiquement les serveurs en Europe ne change presque rien sur le plan juridique. Dès que l'entité opératrice est sous juridiction américaine, le CLOUD Act s'applique peu importe où se trouvent les disques durs. Cette option apporte des bénéfices réels sur d'autres axes (latence plus faible, garanties opérationnelles, parfois certifications SecNumCloud partielles via joint-venture), mais pas d'étanchéité face aux États-Unis.

Changer de juridiction en passant à un fournisseur européen (Mistral, OVHcloud AI, Scaleway, Aleph Alpha, etc.) fait tomber le risque CLOUD Act par défaut, sauf si le fournisseur a une filiale américaine sous contrôle. Le RGPD s'applique pleinement et les autorités européennes peuvent sanctionner. Le fournisseur européen n'est pas aveugle au contenu pour autant. Il conserve un accès technique complet, la protection reste contractuelle et étatique, et une commission rogatoire française ou allemande reste possible. Un fournisseur européen peut aussi, pour des raisons pratiques, héberger son infrastructure sur AWS ou Azure. Cet hébergement réintroduit un lien avec une juridiction tierce. Vérifier au cas par cas.

!!! note "Le cas de l'hébergement sur site"
    Certains fournisseurs européens, comme Mistral, proposent un hébergement sur site, c'est-à-dire que leurs clients font héberger le modèle dans leur propre datacenter. C'est une option intéressante pour bénéficier de l'expertise d'un acteur européen tout en gardant la maîtrise de l'infrastructure, mais elle reste peu répandue et coûteuse.

Enfin, exécuter le modèle localement sur votre propre infrastructure (Ollama, vLLM, llama.cpp ou équivalent) supprime entièrement le tiers. Par construction, aucun fournisseur n'a d'accès technique au contenu. C'est la protection maximale sur le plan de la confidentialité. La contrepartie est que toute la responsabilité bascule chez vous, c'est-à-dire sécurité physique et logique, chiffrement au repos, gestion des accès, mises à jour, journalisation. Les modèles ouverts exécutables localement (Llama, Mistral, Qwen, DeepSeek, etc.) peuvent rester en retrait des meilleurs modèles propriétaires sur certaines tâches complexes, bien que l'écart se réduise rapidement.

Le choix du fournisseur continue de compter pour beaucoup de choses, comme la latence, le coût, la qualité du modèle, la conformité RGPD d'ensemble, l'écosystème d'intégration. Pour le risque de fuite des données personnelles détectées, la dé-identification réduit en revanche fortement l'enjeu de ce choix. Si seuls des jetons comme `<<PERSON:1>>`{ .placeholder } quittent votre infrastructure, un fournisseur américain ne reçoit pas ces valeurs. Il ne devient pas pour autant équivalent à un modèle exécuté en local. Il reçoit le texte qui entoure chaque jeton, et une valeur que le détecteur a manquée part en clair. Voir [Ce que la dé-identification ne résout pas](#ce-que-la-de-identification-ne-resout-pas).

---

## Les obligations sectorielles et les choix déjà faits

### Quand la confidentialité est une obligation légale

Dans plusieurs professions, l'envoi de données personnelles à un LLM non souverain est une impossibilité réglementaire.

- **Finance** : MiFID II, secret bancaire, obligations de confidentialité client.
- **Avocats** : secret professionnel absolu (article 66-5 de la loi du 31 décembre 1971). Une consultation client envoyée brute et nominative à un LLM américain peut constituer une faute déontologique. Les guides récents du CNB exigent au minimum une dé-identification, le consentement client et le choix d'un fournisseur adéquat.
- **Médecine** : secret médical (article L.1110-4 du Code de la santé publique en France), HIPAA aux États-Unis. Un dossier patient ne peut pas transiter par un service tiers sans garanties techniques lourdes (hébergeur certifié HDS, DPO, etc.).
- **Défense et secteurs stratégiques** : régimes spécifiques (classification, CUI (*Controlled Unclassified Information*) aux US, Diffusion Restreinte en France). Le croisement potentiel entre l'accès légal du gouvernement américain et des intérêts stratégiques (énergie, défense, technologie) rend ce risque non-théorique.

Dans ces secteurs, la dé-identification avant envoi peut rendre l'usage possible pour une partie des données, selon l'analyse du responsable de traitement. Certaines données ne doivent pas sortir de votre infrastructure, même dé-identifiées.

### Ce que les grandes entreprises ont déjà décidé

À défaut de protection technique disponible en 2023, plusieurs grands groupes ont tranché en interdisant purement l'usage des LLM en cloud à leurs employés.

- **Samsung, avril 2023** : plusieurs incidents internes où des ingénieurs collent du code source et des notes de réunion dans ChatGPT. Samsung rappelle publiquement que les données ainsi partagées sont impossibles à récupérer, puisqu'elles sont désormais sur les serveurs d'OpenAI. En mai 2023, l'entreprise interdit l'usage des LLM génératifs sur les appareils professionnels.
- **Secteur bancaire américain, printemps 2023** : JPMorgan Chase, Bank of America, Citigroup, Goldman Sachs, Deutsche Bank et Wells Fargo bloquent ou restreignent l'usage de ChatGPT par leurs employés. Verizon, Amazon et Walmart émettent des avertissements internes.

Ces décisions proviennent de directions juridiques et de RSSI qui ont fait le calcul. Le risque structurel dépasse le gain de productivité, tant qu'aucune barrière technique ne garantit que les données personnelles ne quittent pas l'entreprise. La dé-identification ouvre précisément une troisième voie, entre l'interdiction pure et l'envoi en clair.

---

## Protection juridique face à protection technique

Toutes les protections mobilisées jusqu'ici reposent sur des instruments juridiques, comme les politiques de confidentialité, les clauses contractuelles types, les accords internationaux, les amendes administratives. Elles partagent un défaut commun. Elles sont révocables, par une décision politique ou judiciaire sur laquelle vous n'avez aucune prise.

| Type de protection           | Exemple                                    | Pourquoi c'est fragile                                   |
|------------------------------|--------------------------------------------|----------------------------------------------------------|
| Promesse contractuelle       | "Nous ne lisons pas vos données"           | Écrasable par une injonction (cas NYT contre OpenAI)         |
| Clauses contractuelles types | Transferts UE vers US                      | Déjà fragilisées par Schrems II                        |
| Accord international         | Privacy Shield, Data Privacy Framework | Le premier a été invalidé, le second est contesté        |
| Régulation régionale         | RGPD                                       | Lent à produire des sanctions appliquées sur les LLM     |
| Hébergement régional         | "Datacenters en Europe"                    | Neutralisé par le CLOUD Act si le fournisseur est américain |

La protection technique fonctionne différemment. Si la donnée personnelle ne quitte jamais votre infrastructure, et que seul un jeton (par exemple `<<PERSON:1>>`{ .placeholder }) est envoyé au LLM :

- aucune injonction ne peut obliger un tiers à divulguer ce qu'il n'a pas,
- aucun changement d'accord international ne vous affecte,
- aucune politique de conservation du fournisseur n'est en cause,
- le fournisseur peut être piraté, racheté, ou disparaître sans exposer vos données, qui n'y étaient pas.

C'est la différence entre "on vous promet de ne pas regarder" et "on ne reçoit pas la valeur". Pour une valeur détectée, l'incapacité technique est plus robuste que la promesse.

---

## Ce que la dé-identification ne résout pas

La dé-identification est une couche dans une défense en profondeur, pas une solution miracle.

- Elle ne rend pas un LLM conforme à tous les régimes réglementaires. Certaines données (santé nominative, secret-défense) ne doivent pas sortir de l'infrastructure, même dé-identifiées.
- Elle dépend de la qualité des détecteurs. Une donnée personnelle non détectée passe en clair. C'est un enjeu d'ingénierie, pas un défaut conceptuel. Voir [Limites](limitations.md).
- Elle ne masque pas le contexte. Le texte autour d'un jeton peut suffire à ré-identifier une personne, par exemple "le seul cardiologue d'une commune de 300 habitants". Voir [Sécurité](security.md).
- Le lien entre jeton et valeur d'origine reste stocké quelque part chez vous. Cette correspondance contient des données personnelles en clair. Il faut donc le protéger. Voir [Sécurité](security.md).
- Elle ne remplace pas les autres bonnes pratiques, comme le chiffrement au repos, la journalisation auditée, la gestion des accès, la formation des équipes.

---

## Pour aller plus loin

Sources citées et lectures utiles :

- **CJUE, arrêt Schrems II** (C-311/18, 16 juillet 2020) : [curia.europa.eu](https://curia.europa.eu/)
- **CLOUD Act** (H.R. 4943, 2018) : texte officiel sur [congress.gov](https://www.congress.gov/)
- **Rapports PCLOB sur FISA 702** (Privacy and Civil Liberties Oversight Board) : [pclob.gov](https://www.pclob.gov/)
- **Garante italienne, décision contre OpenAI** (décembre 2024, annulée par le tribunal de Rome en mars 2026) : [garanteprivacy.it](https://www.garanteprivacy.it/)
- **NYT contre OpenAI, ordonnance de préservation et livraison de 20 millions de logs** (US District Court SDNY, de mai 2025 à janvier 2026 avec l'affirmation du District Judge Stein)
- **OpenAI, post-mortem de l'incident Redis** (20 mars 2023) : [openai.com/blog](https://openai.com/)
- **Wiz Research, exposition DeepSeek** (janvier 2025) : [wiz.io](https://www.wiz.io/)
- **Samsung, politique interne sur les LLM** (mai 2023, couverture Bloomberg)
- **Surveillance du téléphone d'Angela Merkel par la NSA** (révélations Snowden, octobre 2013, couverture Der Spiegel, Süddeutsche Zeitung, NDR)
- **Saisie des relevés AP par le DOJ** (saisie avril-mai 2012, divulguée en mai 2013, communiqué public d'Associated Press)
- **Pegasus Project / Forbidden Stories** (juillet 2021) : [forbiddenstories.org](https://forbiddenstories.org/)
- **ODNI, *Report on Commercially Available Information*** (janvier 2022, déclassifié juin 2023) : [dni.gov](https://www.dni.gov/)
- **SecNumCloud** (ANSSI) : [cyber.gouv.fr](https://cyber.gouv.fr/)

Pour un regard critique et équilibré, voir aussi les publications de la CNIL sur l'IA générative, du CEPD (EDPB) sur les transferts internationaux, et de l'ENISA sur la souveraineté numérique.
