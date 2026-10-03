# Consignes de rédaction du wiki

## Public visé

Le wiki s'adresse à deux publics, dans cet ordre de priorité :

1. **Les équipes métier / fonctionnelles** (chefs de projet, support,
   opérationnels, gestion). Elles connaissent leur métier, mais **ne lisent
   pas le code**. Elles ouvrent une page au milieu d'une tâche, ou parce
   qu'un écran ne fait pas ce qu'elles attendent.
2. **Les développeurs** : ils veulent savoir où vit chaque règle et comment la
   modifier sans casse.

Chaque page doit permettre à son lecteur de **faire ou décider quelque
chose**. Ce qui ne l'y aide pas sort de la page.

## Skills de rédaction

Si l'hôte dispose des skills suivants, les utiliser pour chaque page :

1. **`rediger-doc`** pour rédiger : la partie « Pour le métier » suit sa
   référence doc métier, la partie « Pour les développeurs » sa référence
   doc technique.
2. **`custom-humanizer`** en mode **Retoucher**, en relecture finale de la
   page.

Adaptations imposées par le cycle OpenWiki :

- ne lancer aucun sous-agent (le test « lecteur frais » de `rediger-doc` est
  sauté) ;
- n'écrire aucun fichier de bilan : un point non vérifiable se marque
  `[à vérifier]` dans la page, avec le moyen de trancher ;
- `custom-humanizer` ne touche ni aux titres (ancres), ni au code, ni aux
  tableaux, ni aux diagrammes, ni au frontmatter.

Sans ces skills, appliquer les règles ci-dessous, qui en sont le résumé.

## Le nom de cette documentation

Pour le lecteur, ce n'est pas un wiki : c'est la **documentation métier**
(*domain documentation* en anglais), à côté de la documentation technique.
Ne jamais écrire « wiki » dans les pages. OpenWiki reste le nom de l'outil qui
la tient à jour, et `openwiki/` celui du dossier.

## Deux langues, les mêmes pages

Le wiki existe en anglais et en français, toujours les deux :
`openwiki/en/` et `openwiki/fr/`. Chaque page existe dans les deux dossiers,
au **même chemin**, en anglais (`processes/protect-a-message.md`), avec la
même structure, les mêmes identifiants et les mêmes liens vers le code.

- Toute page créée, modifiée, déplacée ou supprimée l'est dans les deux
  langues, dans la même mise à jour. Une page dans une seule langue est une
  erreur.
- Seule la prose se traduit. Le code, les identifiants (`BR-MSG-05`,
  `DPO-9`), les noms de fichiers et les libellés `fichier:ligne` restent
  identiques.
- Les ancres de titre suivent la langue de la page : un lien vers une section
  vise le titre de cette langue.
- Vocabulaire : *dé-identifier*, *restaurer*, *jeton*, *conversation* en
  français ; *de-identify*, *restore*, *placeholder*, *conversation* en
  anglais.

## Source de vérité

- Le **code et les tests font foi**. Le texte décrit le comportement réel,
  celui que l'utilisateur constate.
- La **documentation existante** du dépôt (dossier de docs, README, ADR,
  spécifications) est une source d'information factuelle **quand elle est
  juste** : reprendre ses faits et son vocabulaire après les avoir vérifiés
  dans le code. Quand elle contredit le code, le code l'emporte et l'écart
  est signalé (voir « Écarts doc / code »).
- Ne jamais inventer : ni règle, ni libellé, ni chiffre, ni commande. Si un
  point n'est pas tranché dans le code, l'écrire (« non déterminé dans le
  code »).
- Vérifier chaque nombre : délais, montants, horaires, nombre d'étapes. Un
  horaire qui dépend de la configuration du serveur ne reçoit pas d'heure
  inventée.
- Ne jamais recopier un secret (mot de passe, clé, token), même versionné :
  donner seulement son nom et où le trouver.
- Ne pas modifier la documentation existante du dépôt : le wiki la cite, il
  ne la réécrit pas.
- **Les besoins et les règles métier sont des décisions, pas une description
  du code.** Ne jamais modifier le texte d'un besoin (`DPO-`, `DEV-`, `OPS-`,
  `USER-`) ni d'une règle (`BR-`) pour le faire correspondre au code. Quand le
  code s'en écarte, ajouter une ligne au registre des écarts
  (`reference/doc-code-gaps.md`) et laisser la règle telle quelle. Seul un
  humain change une décision. Les emplacements de code, les tests et les
  écarts restent à mettre à jour.

## Mots de l'écran

Dans les parties métier, employer les libellés exacts de l'interface (menus,
boutons, champs, colonnes, messages, noms de profils), relevés dans les
gabarits et les fichiers de traduction. S'y tenir, sans synonyme. Les écrire
en **gras**, à l'identique, avec le chemin de navigation complet.

Quand le nom d'un concept à l'écran diffère de son nom dans le code, donner
la correspondance une fois dans le glossaire, puis employer le nom de l'écran
dans le texte métier et le nom du code dans la partie développeurs.

## Structure obligatoire d'une page de processus

### 1. En bref

Trois à cinq puces, sans aucun nom de code : à quoi sert le processus, qui
est concerné, ce qu'il faut retenir.

### 2. Pour le métier

**Aucun identifiant technique** dans cette partie : ni classe, ni méthode,
ni table, ni route, ni variable, ni commande, ni nom de rôle technique.
Traduire sans simplifier : l'état d'un champ devient ce que l'utilisateur
voit à l'écran, une tâche planifiée devient le moment réel où elle agit, une
exception devient le message affiché puis ce que l'utilisateur doit faire.

Sections, dans cet ordre (omettre celles qui ne servent pas) :

1. **Qui peut faire quoi** : tableau profils × actions, si les droits
   diffèrent.
2. **Une section par tâche**, avec un titre qui dit la tâche. Chaque
   procédure :
   - part d'un chemin de navigation complet ;
   - donne une action par étape, à l'impératif, avec le libellé exact ;
   - indique le résultat attendu après chaque étape qui change l'écran ;
   - signale les effets invisibles : e-mail envoyé, calcul relancé, document
     généré ;
   - avertit **avant** l'étape de toute action irréversible ou qui envoie
     quelque chose ;
   - se termine par **Comment vérifier**.
3. **Règles à connaître** : règles de gestion numérotées (`BR-<DOMAINE>-NN`,
   *business rule*, avec un code de domaine en anglais : `MSG`, `CONV`,
   `LIST`, `TOOL`, `STREAM`, `AGT`, `CFG`, `STO`),
   formulées en « Quand… alors… », avec un exemple concret daté pour chaque
   règle non évidente. Utiliser un tableau de décision quand plusieurs
   conditions se combinent. Expliquer le pourquoi en une phrase si cela aide
   à appliquer la règle.
4. **Ce que voit l'utilisateur final** (client, usager), si l'action a un
   effet chez lui : écran, e-mail, document.
5. **Questions fréquentes** : partir du symptôme constaté, puis
   l'explication et ce qu'il faut faire.

Une limite connue ou un bug toléré se décrit par son effet visible et par la
conduite à tenir.

### 3. Pour les développeurs

Sections typées, sans les mélanger :

1. **Où vivent les règles** (référence) : un tableau `BR-… | fichier:ligne`,
   en reprenant les identifiants de la partie métier, plus les entités,
   services et commandes liés.
2. **Modifier…** (how-to), quand une modification courante existe : étapes
   numérotées, en partant du modèle existant le plus proche dans le code,
   avec une section **Vérifier** (test, commande ou requête).
3. **Pièges** : comportements par défaut dangereux, erreurs avalées, valeurs
   codées en dur, noms trompeurs.
4. **Écarts doc / code** : un encadré « ⚠ Écart doc / code » par écart (ce
   que dit la doc, ce que fait le code, `fichier:ligne`). Les écarts ne vont
   **que** dans cette partie, jamais dans la partie métier. Chaque écart est
   aussi listé dans `reference/doc-code-gaps.md`.
5. **Tests** : tests existants, et ce qu'ils ne couvrent pas.

Marquer `[à vérifier]` toute affirmation qui dépend de code absent du dépôt
(dépendances externes, `vendor/`, services tiers), avec le moyen de trancher.

Les pages purement techniques (architecture, exploitation, tests) gardent un
format technique, mais commencent aussi par un « En bref » lisible par un
non-développeur.

## Quickstart : router par intention

Le quickstart oriente le lecteur selon ce qu'il veut faire, pas selon
l'arborescence du wiki. Sections, dans cet ordre :

1. **En bref** : quatre blocs, chacun ouvert par un libellé en gras.
   - **Ce qu'est PIIGhost** : ce qu'il fait en une phrase, ce qu'il est
     (bibliothèque, intégrations, configuration), puis le trajet d'un
     message en 3 à 6 étapes numérotées, chaque terme défini à sa première
     apparition.
   - **Ce qu'est cette documentation métier** : ce qu'elle décrit, la
     différence avec la documentation technique, et la liste de ce qu'on y
     définit (besoins par profil, règles, tests d'acceptation, emplacement
     dans le code).
   - **Son objectif** : écrire des règles qui n'existent nulle part ailleurs,
     pour les discuter et les faire évoluer ensemble.
   - **Comment la lire** : par où commencer, le rappel que le code et les
     tests ont raison en cas de désaccord, avec un lien vers le registre des
     écarts et vers le glossaire.
2. **Je cherche à comprendre…** (public métier) : un tableau
   `Besoin métier | Page à lire`. Chaque ligne formule un besoin comme le
   lecteur le pense, avec ses mots, sans identifiant technique. Une ligne
   par page métier, plus une ligne vers le glossaire et une vers le registre
   des écarts. Suivi d'un diagramme du cycle de vie (10 boîtes au plus).
3. **Modifier le code** : une seule phrase qui renvoie vers la page
   « Modifier le code de piighost » de la documentation technique
   (`docs/<langue>/community/changing-the-code.md`). Le tableau des
   changements courants et les repères pour démarrer en local vivent dans
   cette page, pas dans la documentation métier.
4. **Les groupes de la documentation métier** : une puce par groupe, avec les liens.
5. **Points de vigilance transverses** : trois à six pièges qui traversent
   plusieurs processus, chacun avec un lien.

Toute page ajoutée, déplacée ou supprimée met à jour le tableau de routage,
et le tableau de la page « Modifier le code de piighost » quand un fichier
qu'il cite change.

## Pages attendues

Organiser le wiki **par processus métier**, pas par module ou par écran.
Couvrir au minimum :

- **Glossaire** (page dédiée, liée depuis toutes les pages) : chaque terme et
  sigle du métier, avec une définition métier d'une ou deux phrases, le
  libellé de l'écran, puis, si utile, le nom technique correspondant.
- **Registre des écarts doc / code** (`reference/doc-code-gaps.md`).
- **Décisions de conception** (`reference/decisions.md`) : les décisions
  qui ont construit le système de dé-identification, dans l'ordre où elles se
  sont posées. Chacune est un titre `### DEC-NN : titre`, suivi d'une
  explication en prose pour un lecteur métier, sans rubriques imposées. Elle
  dit le problème, le choix fait et ce qu'il change, avec un exemple quand il
  aide. Elle ne montre que ce que les décisions précédentes ont introduit. Elle
  finit par l'endroit du code où elle vit et les règles qui en découlent. Une
  décision nouvelle prend le numéro suivant, au bon endroit dans l'ordre. Une
  raison écrite par le mainteneur ne se réécrit pas, elle se complète.
- **Besoins par profil** (`needs-by-profile.md`) et **tests d'acceptation**
  (`tests/acceptance-tests.md`) : chaque processus cite les besoins qu'il
  couvre, et chaque besoin ses tests.

## Identifiants

Les identifiants sont en anglais, les mêmes quelle que soit la langue de la
page : besoins `DPO-n`, `DEV-n`, `OPS-n`, `USER-n` ; règles
`BR-<DOMAINE>-NN` ; décisions de conception `DEC-NN` ; tests d'acceptation `AT-<besoin>-<n>` ; écarts
`ECART-NN`. Un identifiant publié ne change plus de sens : une règle retirée
laisse son numéro libre.

## Style

- Une idée par phrase. Moins de 20 mots par phrase dans les parties métier,
  moins de 25 dans les parties développeurs.
- Commencer chaque section et chaque paragraphe par l'information principale.
- Voix active, avec un acteur explicite.
- S'adresser au lecteur avec « vous », consignes à l'impératif, au présent.
- Un terme par concept dans toute la page. Développer chaque sigle à sa
  première occurrence.
- Supprimer : « permet de », « il suffit de », « simplement »,
  « facilement », les phrases de narrateur, les mots creux, les faux
  contrastes (« ce n'est pas X, c'est Y ») sauf s'ils répondent à une vraie
  idée reçue du lecteur.
- Les titres seuls doivent permettre de parcourir la page : en forme de tâche
  ou de réponse, jamais « Généralités » ou « Divers ».
- Tableaux pour comparer ou donner des valeurs (3 à 5 colonnes), pas pour
  mettre en page de la prose. Listes numérotées pour les étapes.
- Deux encadrés au maximum par page, hors « ⚠ Écart doc / code ».
  `> [!WARNING]` est réservé à la perte de données, à la sécurité et aux
  actions irréversibles.
- Une liste suit le nombre annoncé.
- Dates : JJ/MM/AAAA dans les parties métier, AAAA-MM-JJ dans les parties
  développeurs.
- Exemples : le plus petit exemple réaliste, avec des données fictives
  crédibles.
- Typographie française dans la prose : espace avant `;`, `:`, `!`, `?`,
  guillemets « ».
- Un diagramme Mermaid par processus, de 10 boîtes au plus, avec des
  libellés métier. Dans les libellés : pas de `<br/>`, pas de `;`, pas de
  chevron `<` ou `>` (donc pas de chemin de navigation avec chevrons), et
  guillemets autour d'un libellé qui contient des parenthèses.

## Avant de soumettre une page

- [ ] La partie métier ne contient aucun identifiant technique.
- [ ] Les libellés et chemins de navigation sont vérifiés dans les gabarits.
- [ ] Chaque procédure a son point de départ, ses résultats attendus et sa
      vérification.
- [ ] Chaque règle est en « Quand… alors… », avec un exemple daté si elle
      n'est pas évidente.
- [ ] Les faits repris de la documentation existante sont vérifiés dans le
      code.
- [ ] Les écarts doc / code sont dans la partie développeurs et dans le
      registre.
- [ ] Les liens et les ancres internes fonctionnent.
- [ ] Si la page est ajoutée, déplacée ou supprimée : les tableaux de
      routage du quickstart sont à jour.
