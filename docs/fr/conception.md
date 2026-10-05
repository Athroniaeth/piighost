---
icon: lucide/blocks
---

# Conception du pipeline

Une fois admis qu'il faut dé-identifier (voir [Pourquoi dé-identifier ?](why-anonymize.md)),
reste le comment. La construction ci-dessous se fait pas à pas. Elle part de la première
brique, la détection des données confidentielles (données personnelles, secrets), puis ajoute une contrainte à la fois. Chaque
composant du pipeline apparaît parce qu'une contrainte précédente l'a rendu nécessaire. À la fin,
l'ordre des étapes et les choix techniques ne sont plus arbitraires, ils découlent du
problème.

!!! note "Dé-identification, pas anonymisation"
    `piighost` garde le lien entre une valeur et son jeton pour pouvoir la restaurer.
    C'est de la dé-identification réversible. On réserve le mot anonymisation à une
    suppression irréversible, par exemple avec `RedactPlaceholderFactory`.

!!! note "Pour la vue d'ensemble"
    Pour la carte des couches et l'API de chaque composant, voir
    [Architecture](architecture.md).

---

## Étape 1, le détecteur

Dé-identifier, c'est remplacer une valeur sensible par un *placeholder*, c'est-à-dire le
*jeton* qui prend sa place dans le texte. Sur un texte libre, on ne sait pas d'avance où
sont les données confidentielles ni de quel type. La première brique est donc la détection.

Deux approches classiques se complètent.

- La **regex** reconnaît des motifs, c'est-à-dire des chaînes de caractères qui suivent
  une structure fixe (IBAN, téléphone, e-mail). Efficace sur ces formats, inutilisable
  sur du texte non structuré comme un prénom, un nom, une date écrite ou un lieu.
- Le **NER** (Named Entity Recognition) est un modèle d'IA qui, sur un texte, classe les
  mots selon une classification décidée à l'avance (nom, prénom, lieu, organisation). Il
  saisit le contexte là où la regex ne voit qu'un format.

C'est le rôle du détecteur (`AnyDetector`). Il lit le texte et renvoie une liste de
détections, une par valeur trouvée, avec sa position, son type et un score de confiance.

```mermaid
flowchart LR
    T["Patrick habite à Paris"] --> D{{"AnyDetector"}}
    D --> R1["PERSON (0,7) 0.95"]
    D --> R2["LOCATION (17,22) 0.92"]
```

*Le détecteur transforme un texte brut en détections positionnées et typées.*
{ .figure-caption }

`piighost` fournit ces approches comme détecteurs interchangeables, `Gliner2Detector`,
`SpacyDetector`, `TransformersDetector` et `PresidioDetector` pour le NER,
`BridgeDetector` pour un modèle exécuté ailleurs (en JavaScript dans le navigateur),
`RegexDetector` pour les motifs, `LLMDetector` quand le contexte métier dépasse les
détecteurs étroits, et `ExactMatchDetector` pour les tests. On peut les combiner avec `CompositeDetector`, parce
qu'une regex plus un NER couvrent plus de cas qu'un seul détecteur. Le détecteur est donc
un port (une interface que chaque détecteur implémente) et non une classe figée. On
injecte celui qu'on veut.

La regex ne valide **aucun checksum**. Un IBAN ou un numéro de carte reconnu par le
motif est gardé tel quel, sans vérifier sa clé de contrôle. Une valeur abîmée par un OCR
reste ainsi une détection plutôt que d'être écartée par un calcul qui échoue sur le
bruit. Mieux vaut une détection de trop, arbitrée plus tard, qu'une valeur laissée en
clair.

---

## Étape 2, le placeholder typé

Avec la détection, on connaît le type de chaque valeur. Le placeholder le plus simple
serait un jeton constant, le même pour tout, comme `<<REDACT>>`{ .placeholder }. On
l'enrichit avec le type, `<<PERSON>>`{ .placeholder } ou `<<EMAIL>>`{ .placeholder }.

Le type est utile parce que le modèle qui lit le texte dé-identifié en a besoin pour
raisonner. "Contacte `<<PERSON>>`{ .placeholder } à
`<<EMAIL>>`{ .placeholder }" reste exploitable. "Contacte `<<REDACT>>`{ .placeholder }
à `<<REDACT>>`{ .placeholder }" ne l'est plus.

La placeholder factory (`AnyPlaceholderFactory`) décide de la forme du jeton. Elle prend
une entité et rend son jeton. C'est elle qu'on change pour passer de
`<<REDACT>>`{ .placeholder } à `<<PERSON>>`{ .placeholder }.

---

## Étape 3, l'entité et le linker

Un texte peut citer deux personnes différentes. Si les deux deviennent
`<<PERSON>>`{ .placeholder }, le modèle ne peut plus les distinguer, et on ne peut plus
revenir en arrière sans ambiguïté. Il faut donc une identité par individu.

```text
Patrick écrit à Marie  →  <<PERSON:1>> écrit à <<PERSON:2>>
```

`Patrick`{ .pii } devient `<<PERSON:1>>`{ .placeholder }, `Marie`{ .pii } devient
`<<PERSON:2>>`{ .placeholder }. Le compteur distingue les individus du même type.

Mais une même personne apparaît souvent plusieurs fois, parfois avec une casse
différente (`Patrick`{ .pii }, `patrick`{ .pii }). Toutes ces occurrences doivent partager le même
jeton. Une détection isolée ne suffit donc pas. Il faut une notion au-dessus, l'entité,
qui regroupe toutes les détections désignant la même valeur.

D'où une nouvelle étape, passer des détections aux entités. C'est le linker
(`AnyEntityLinker`). `ExactEntityLinker` groupe les détections par clé canonique
`(value_key(texte), label)`, c'est-à-dire la valeur sans tenir compte de la casse ni des
espaces, et le label. Il crée une entité par clé, dont la valeur est la première
graphie rencontrée.

```mermaid
flowchart LR
    D["détections\nPatrick, patrick, Marie"] --> L{{"ExactEntityLinker"}}
    L --> E1["entité PERSON 'Patrick'"]
    L --> E2["entité PERSON 'Marie'"]
```

*Le linker regroupe les détections d'une même valeur en une entité, qui recevra un jeton
unique.*
{ .figure-caption }

C'est l'entité, pas la détection, qui reçoit un jeton. Toutes les occurrences d'une
entité partagent donc le même `<<PERSON:1>>`{ .placeholder }.

---

## Étape 4, le résolveur de spans

Dès qu'on combine des détecteurs, ou qu'un détecteur trouve plusieurs candidats sur la
même zone, des détections se chevauchent. Exemple classique, un NER propose `LOCATION`
sur `Paris`{ .pii } et un autre `PERSON` sur la même position, ou deux modèles donnent des
bornes légèrement différentes.

Si on laissait passer ces chevauchements jusqu'au remplacement, on produirait des jetons
imbriqués et un texte corrompu. Il faut donc résoudre les conflits de positions avant de
regrouper en entités.

C'est le résolveur de spans (`AnyOverlapResolver`). Un span est la position d'une
détection dans le texte, de son début à sa fin. `ConfidenceOverlapResolver` groupe
les détections qui se chevauchent, puis garde dans chaque groupe la plus confiante.
`MergeOverlapResolver` garde plutôt l'union de chaque groupe. Ainsi, une détection sûre
mais courte ne laisse jamais en clair une partie d'une détection plus longue.

---

## Étape 5, l'expander

Le linker ne groupe que les détections **qu'on lui donne**. Or un NER rate des
occurrences. Il trouve `Patrick`{ .pii } dans la phrase 1, mais rate le `Patrick`{ .pii }
tout seul de la phrase 3. Si on s'arrête au linker, cette occurrence reste en clair dans
le texte dé-identifié.

Rattraper les occurrences ratées est un travail à part, celui de l'expander
(`AnyDetectionExpander`). `WordBoundaryExpander` cherche, pour chaque valeur déjà
détectée, ses autres occurrences dans le texte par recherche aux frontières de mot, et
ajoute une détection pour chacune.

On sépare l'expander du linker à dessein. Le linker regroupe, l'expander cherche. Chacun
a une seule responsabilité. L'expander reste optionnel, parce qu'un jeu de détections
déjà complet n'en a pas besoin.

L'ordre des étapes est contraint.

```mermaid
flowchart LR
    A["détecter"] --> B["résoudre les spans"] --> C["rattraper les occurrences"] --> D["lier en entités"] --> E["résoudre les entités"] --> F["dé-identifier"]
```

*Les positions se résolvent avant le linking, les identités après.*
{ .figure-caption }

On résout les positions tôt, sur des détections encore brutes, puis on rattrape les
occurrences ratées, puis on groupe en entités, et on résout les identités en dernier
(voir l'étape suivante).

---

## Étape 6, le résolveur d'entités

Après le linking, deux entités peuvent encore désigner la même personne. C'est le cas de
`Patrick`{ .pii } et `Patric`{ .pii } (faute de frappe), ou de deux entités issues de
détecteurs différents qui partagent une détection. Les réconcilier évite de donner deux jetons à une seule
personne.

C'est le résolveur d'entités (`AnyEntityResolver`).

- `MergeEntityResolver` fusionne les entités qui partagent une détection (union-find,
  transitif).
- `FuzzyEntityResolver` fusionne par similarité de texte (Jaro-Winkler), pour rattraper
  les variantes orthographiques.
- `SeparateEntityResolver` fait l'inverse, il garde séparées les entités qui partagent
  une détection. Chaque détection partagée revient à la plus grande entité qui la
  contient, et quitte les autres.

À ce stade, on a une liste d'entités propres, chacune devant recevoir un jeton unique et
stable.

---

## Étape 7, l'anonymiseur

L'anonymiseur (`AnyAnonymizer`) applique enfin le remplacement. Il demande un jeton à la
factory pour chaque entité, puis remplace chaque détection par son jeton.

Grâce à l'étape 4, le remplacement se fait en un seul passage sur les spans, de gauche à
droite. Il construit un nouveau texte en recopiant le texte situé entre les spans, si bien
qu'aucun remplacement ne décale la position d'un autre. Ce passage unique suppose des
spans qui ne se chevauchent pas, et l'étape 4 le garantit.

---

## Étape 8, la restauration

Dé-identifier ne sert que si l'on peut restaurer les vraies valeurs pour l'utilisateur.
Pour cela il faut savoir que `<<PERSON:1>>`{ .placeholder } valait `Patrick`{ .pii }.
La dé-identification d'un texte rend justement ce mapping, une entité par jeton émis.

La restauration remplace, dans un texte, chaque jeton connu par la valeur de son entité.
Elle ne se limite pas au texte que le pipeline a produit. Le modèle génère souvent une
réponse nouvelle contenant un jeton, par exemple "Bien sûr,
`<<PERSON:1>>`{ .placeholder } !". Le pipeline n'a jamais produit cette phrase. Mais
comme on connaît le couple jeton vers valeur, on remplace le jeton dans n'importe quel
texte.

```mermaid
flowchart LR
    IN["Bien sûr, #lt;#lt;PERSON:1#gt;#gt;#160;!"] --> D{{"deanonymize"}} --> OUT["Bien sûr, Patrick#160;!"]
```

*La restauration remplace les jetons connus par leur valeur, dans n'importe quel
texte.*
{ .figure-caption }

La restauration n'est sans ambiguïté que si les jetons préservent l'identité. Deux
entités qui partageraient un jeton, comme avec `<<PERSON>>`{ .placeholder }, se
confondraient sur une seule valeur. C'est pourquoi le middleware exige une factory qui
identifie chaque entité, `<<PERSON:1>>`{ .placeholder } et non
`<<PERSON>>`{ .placeholder }.

---

## Étape 9, la mémoire de conversation

Tout ce qui précède traite un texte, isolément. Un agent, lui, enchaîne des messages, et
le même `Patrick`{ .pii } doit garder le même `<<PERSON:1>>`{ .placeholder } du premier
au dernier.

### Pourquoi rejouer le pipeline par message ne suffit pas

La tentation est de rappeler simplement `anonymize` sur chaque message. Mais le pipeline
mono-texte n'a aucune mémoire. Il repart de zéro à chaque appel, et le compteur
recommence à 1. Sur deux messages, on obtiendrait ceci.

```text
Message 1 : "Patrick appelle Marie"   →  <<PERSON:1>> appelle <<PERSON:2>>
Message 2 : "Marie rappelle Patrick"  →  <<PERSON:1>> rappelle <<PERSON:2>>
```

`Marie`{ .pii } est `<<PERSON:2>>`{ .placeholder } au message 1 puis
`<<PERSON:1>>`{ .placeholder } au message 2. Les identités se croisent, et plus rien
n'est réversible de façon cohérente sur la conversation. Une conversation porte donc un état
partagé d'un message au suivant.

### La mémoire de conversation

`ThreadAnonymizationPipeline` ajoute cet état partagé. C'est une mémoire
(`AnyConversationMemory`) qui enregistre, pour chaque conversation, les détections de
chaque message. Les jetons sont ensuite
attribués sur l'union des détections de tous les messages de la conversation, pas sur un message
seul. Une personne revue dans un message ultérieur retrouve donc son entité, et son
jeton, au lieu d'en créer un nouveau.

```text
Message 1 : "Patrick appelle Marie"   →  <<PERSON:1>> appelle <<PERSON:2>>
   mémoire : patrick→1, marie→2
Message 2 : "Marie rappelle Patrick"  →  <<PERSON:2>> rappelle <<PERSON:1>>
   (réutilise la mémoire, aucun nouveau compteur)
```

### Les règles qui en découlent

- **Ordre de première apparition.** Le compteur d'une entité est attribué à sa première
  apparition dans la conversation et ne bouge plus. Sans cette règle, une nouvelle
  entité placée tôt dans son message volerait le compteur d'une entité plus ancienne.
- **Isolation par `thread_id`.** Le `thread_id` est obligatoire, et il n'y a pas de conversation
  partagée par défaut. Ainsi, deux appelants ne tombent pas dans la même conversation et ne
  fuitent pas leurs données confidentielles. `forget_thread` peut tout effacer d'une conversation, pour le droit à
  l'oubli.

### Le rendu reste par message

Les détections d'une entité viennent de messages différents, dont les positions n'ont
pas de référentiel commun. On ne peut donc pas remplacer par positions à l'échelle de la
conversation. Les jetons sont attribués sur toute la conversation. Le rendu, lui, ne remplace que les
spans du message courant, les seuls dont les offsets valent dans ce message.

---

## Étape 10, la provenance des valeurs

Toute valeur d'un message n'est pas une donnée confidentielle à protéger. Prenons une
personnalité publique que le modèle cite à partir de sa connaissance du monde. La dé-identifier
cacherait ce nom au modèle au tour suivant, sans rien protéger de l'utilisateur.

La mémoire enregistre donc le rôle de la première occurrence de chaque valeur,
`MessageRole.USER` ou `MessageRole.ASSISTANT`. Une valeur dont la première occurrence
vient d'un message du modèle est laissée en clair, car elle n'est pas une donnée
confidentielle de l'utilisateur. Le middleware règle ce comportement par
`EntityCreateByAssistantStrategy`. Ses trois valeurs laissent la valeur en clair,
la dé-identifient quand même, ou ignorent les messages du modèle.

---

## Étape 11, l'asynchrone

Le pipeline est asynchrone de bout en bout, pour deux raisons concrètes.

- **La mémoire persistante est un service externe.** Un backend Redis lit et écrit sur
  le réseau. Le faire en asynchrone évite de bloquer pendant l'attente.
- **Un serveur sert plusieurs requêtes à la fois.** Une API qui héberge le pipeline
  traite des conversations concurrentes sur une seule boucle d'événements.

Mais l'inférence d'un modèle NER local est, elle, synchrone et lourde. Elle demande des
centaines de millisecondes de calcul CPU ou GPU. Appelée directement dans une coroutine,
elle gèle toute la boucle, et aucune autre requête ne progresse pendant ce temps. Les
détecteurs à modèle déportent donc l'inférence dans un thread. Un détecteur qui appelle une API
distante reste, lui, en asynchrone natif, parce que son travail est de l'I/O réseau et
non du calcul.

En résumé, asynchrone pour l'I/O et l'orchestration, déport en thread pour le calcul
bloquant.

---

## Étape 12, le chiffrement du mapping

Sur un seul worker, la mémoire tient dans un dictionnaire du processus
(`InMemoryConversationMemory`). Un déploiement multi-worker a besoin d'une mémoire partagée,
`RedisConversationMemory` ou `SqlAlchemyConversationMemory`, pour qu'un worker voie les
conversations d'un autre.

Mais le mapping inverse, la table qui relie chaque jeton à sa vraie valeur, est fait de
données confidentielles en clair. Une fuite du store révélerait ces données. Deux
composants crypto optionnels protègent les backends Redis et SQL. Un hasher (`AnyHasher`) transforme chaque
message en clé déterministe sans révéler le texte. Un cipher (`AnyCipher`) chiffre les
détections au repos, de sorte qu'une fuite de la base ne rende ni le message ni les valeurs.
Le `thread_id` reste en clair comme préfixe de clé, pour qu'une conversation puisse être
énumérée et oubliée.

---

## Étape 13, le garde-fou

Même avec tout ce qui précède, une valeur peut passer entre les mailles, par exemple un nom
que le NER a raté. Le garde-fou (`AnyGuardRail`) re-analyse le texte dé-identifié et lève
`PIIRemainingError` s'il y trouve encore une valeur en clair.

Le garde-fou n'examine que la sortie dé-identifiée. Un contrôle prévu pour de vraies
valeurs ne prend pas les placeholders de cette sortie pour de vraies valeurs, parce
qu'ils sont clairement synthétiques. Le garde-fou est optionnel mais c'est la dernière barrière avant la sortie.
`DetectorGuardRail` rejoue un détecteur, `Gliner2GuardRail` classe la sortie avec un
modèle GLiNER2 local, `LLMGuardRail` interroge un LLM et `ModerationGuardRail` l'API de
modération de Mistral.

---

## Étape 14, le middleware

Reste à brancher tout cela dans une boucle d'agent LangChain, de façon transparente.
C'est le `PIIAnonymizationMiddleware`, qui intervient en trois points.

- Avant le modèle (`abefore_model`), il dé-identifie les messages avant que le LLM ne
  les voie.
- Après le modèle (`aafter_model`), il restaure la sortie pour l'affichage utilisateur.
- Autour des appels outils (`awrap_tool_call`), selon la stratégie choisie
  (`ToolCallStrategy`), il restaure les arguments pour que l'outil reçoive de vraies
  données, puis dé-identifie sa réponse.

Le middleware ne contient aucune logique de dé-identification. Il délègue tout au
pipeline conversationnel. C'est un simple adaptateur entre le monde LangChain et le
cœur. Il exige, dès le typage, une factory qui préserve l'identité. Il reconnaît aussi
les jetons que le modèle invente (`InventedPlaceholderStrategy`). Il les reconnaît parce
qu'après la restauration, tout jeton qui suit encore la grammaire des placeholders n'a
pas été émis par le pipeline.

---

## Récapitulatif, chaque composant répond à une contrainte

<div class="wide-table" markdown="1">

| Contrainte rencontrée | Composant né de la contrainte |
|---|---|
| On ne sait pas où sont les données confidentielles | Détecteur (`AnyDetector`) |
| Le modèle a besoin du type | Placeholder typé (`AnyPlaceholderFactory`) |
| Distinguer deux individus du même type | Identité par entité et linker (`AnyEntityLinker`) |
| Détections qui se chevauchent | Résolveur de spans (`AnyOverlapResolver`) |
| Occurrences ratées par le détecteur | Expander (`AnyDetectionExpander`) |
| Entités équivalentes à fusionner | Résolveur d'entités (`AnyEntityResolver`) |
| Produire le texte sans corruption | Anonymiseur, un seul passage de gauche à droite |
| Revenir en arrière sur un texte quelconque | `deanonymize`, remplacement jeton par jeton |
| Cohérence sur toute la conversation | Mémoire par `thread_id`, ordre de première apparition |
| Valeur venant du modèle, pas de l'utilisateur | Provenance en mémoire (`MessageRole`) |
| I/O sans bloquer et calcul lourd | Asynchrone et déport en thread de l'inférence |
| Mapping inverse persistant à protéger | Crypto, hasher et cipher des backends Redis et SQL |
| Données confidentielles résiduelles | Garde-fou (`AnyGuardRail`) |
| Intégration agent transparente | Middleware LangChain |

</div>

---

## Voir aussi

- [Architecture](architecture.md) : la carte des couches et l'API de chaque composant.
- [Fabriques de placeholders](placeholder-factories.md) : les familles de jetons et ce qu'elles préservent.
- [Stratégies d'appel outil](tool-call-strategies.md) : le détail de `awrap_tool_call`.
