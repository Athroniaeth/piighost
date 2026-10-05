# Documentation métier (utilisateurs fonctionnels, non développeurs)

Le lecteur connaît son métier, pas le code. Il ouvre la doc **au milieu d'une tâche**, pour savoir quoi faire, ou bien parce que l'écran ne fait pas ce qu'il attend. Il pense en termes de dossiers, de dates, de personnes et d'écrans, pas en termes d'entités ou de flags.

## 1. Traduire, pas simplifier

Rester précis : seul le vocabulaire change.

| Vocabulaire technique (interdit dans le texte) | Ce qu'il faut écrire à la place |
|---|---|
| Nom de classe, table, route, champ (`noMailing`, `Participation`) | Le libellé exact de l'écran (**Ne pas envoyer d'e-mails**) ou le mot du métier (« inscription ») |
| « Le flag est à true », « null » | « La case est cochée », « Le champ est vide » |
| « Asynchrone », « en tâche de fond », « cron » | Le moment réel, vérifié : « dans les minutes qui suivent », « chaque nuit vers 2 h » |
| « Persisté », « flush », « synchronisé » | « Enregistré », « mis à jour à l'enregistrement de la fiche » |
| « Le système lève une exception » | Le message affiché à l'écran, puis ce que l'utilisateur doit faire |
| « Utilisateur avec ROLE_WEBMASTER » | Le nom du profil tel qu'il apparaît : « administrateur » |

**Avant d'écrire**, établir le lexique de la fonctionnalité :

- relever dans les templates et les fichiers de traduction **les libellés exacts** des menus, boutons, champs, colonnes et messages ;
- relever les noms de profils ;
- relever les termes métier déjà utilisés dans la doc fonctionnelle existante.

S'y tenir ensuite, sans synonymes.

## 2. Organiser par tâche métier

- Organiser le document selon **le déroulé du travail** : préparer, créer, suivre, clôturer, corriger. Pas selon les écrans ni les modules du code.
- Choisir des titres qui disent la tâche ou la question : « Rattacher un questionnaire après la création », « Pourquoi le champ est grisé ».
- Une page couvre une fonctionnalité, en sections typées qui ne se mélangent pas :

```
# <Fonctionnalité> : guide d'utilisation
<2 phrases : à quoi ça sert, qui est concerné>

## Ce qui change / en bref            (si évolution : impact sur le travail quotidien)
## Qui peut faire quoi                 (tableau profils × actions, si droits différents)
## <Tâche 1>                           (procédure)
## <Tâche 2>                           (procédure)
## Règles à connaître                  (règles de gestion)
## Ce que voit le participant / client (si l'action a un effet chez un autre acteur)
## Questions fréquentes et messages    (symptôme → explication → que faire)
## Glossaire                           (si plus de 3 termes métier spécifiques)
```

## 3. Procédures

1. **Point de départ** : le chemin de navigation complet, en gras (**Sessions > [nom de la session] > Modifier**).
2. **Une action par étape**, à l'impératif, en reprenant le libellé exact : « Dans **Questionnaire**, choisissez le questionnaire. »
3. **Résultat attendu** après chaque étape qui change quelque chose à l'écran : « Le message **Session enregistrée** s'affiche. »
4. **Effets invisibles** : dire ce que l'action déclenche ailleurs, par exemple un e-mail envoyé aux participants, un parcours recalculé ou un document généré.
5. **Actions irréversibles ou à effet externe** (envoi d'e-mails, suppression, clôture) : l'avertir **avant** l'étape, pas après, dans un `> [!WARNING]`.
6. Terminer par **Comment vérifier** : où regarder pour constater que c'est fait.

## 4. Règles de gestion

- Les numéroter (`RG-01`…) quand elles sont nombreuses ou qu'on s'y réfère ailleurs.
- Les formuler en **condition → conséquence** : « Quand un participant a déjà répondu au questionnaire, le champ **Questionnaire** est verrouillé. »
- Donner pour chaque règle non triviale **un exemple concret**, avec des dates et des personnes : « Session du 12/03 à 18 h : le questionnaire de satisfaction s'ouvre le 12/03 à 18 h. Les documents sont disponibles le 13/03 à 0 h. »
- Quand plusieurs conditions se combinent, utiliser un **tableau de décision** (situation × moment → ce qui est possible).
- Expliquer le **pourquoi** en une phrase si cela aide à appliquer la règle (« pour ne pas fausser les réponses déjà saisies »). Pas d'histoire du projet.
- Toute **limite connue** ou tout bug toléré est décrit par son effet visible et par la conduite à tenir : « Signalez-le à… ».

## 5. Exactitude : le code fait foi, le demandeur arbitre

- Les preuves (`fichier:ligne`) vont dans le **bilan** remis au demandeur, jamais dans le texte destiné aux utilisateurs.
- Les specs et la doc d'évolution décrivent l'**intention**. Le code décrit le **comportement réel**, c'est donc lui que l'utilisateur constatera.
- Écrire le comportement réel. Pour chaque écart entre spec et code, faire une entrée dans « À arbitrer » : « La spec dit X, le code fait Y (`fichier:ligne`). La doc décrit Y. Est-ce voulu ? » Ne jamais trancher en silence.
- Ne pas donner de nombres sans les avoir vérifiés : délais, nombre d'étapes, horaires des envois automatiques. Si un horaire dépend de la configuration du serveur, écrire « automatiquement, chaque jour » et mettre l'horaire précis dans « À arbitrer ».
- Faire correspondre les listes aux nombres annoncés : « 4 étapes » est suivi de 4 éléments, pas de 8.

## 6. Notes de version pour les fonctionnels

- Chaque entrée part de l'**impact sur leur travail** : « Vous pouvez maintenant créer une session sans questionnaire. »
- Indiquer pour chaque entrée :
  - qui est concerné ;
  - ce qui change concrètement à l'écran ;
  - ce qu'il faut faire (souvent rien : le dire) ;
  - ce qui arrive aux données existantes.
- Aucun nom de ticket technique, de MR ou de composant.

## 7. Captures d'écran

- Si l'agent peut produire une capture (Playwright…), la faire. Sinon, laisser un repère explicite : `[Capture : formulaire de session, champ Questionnaire grisé]`.
- Le texte doit rester compréhensible sans l'image.

## 8. Checklist

- [ ] Le texte ne contient aucun identifiant technique : classe, table, route, variable, flag, nom de commande.
- [ ] Les libellés d'écran et les chemins de navigation sont vérifiés dans les templates.
- [ ] Chaque procédure indique son point de départ, ses résultats attendus et sa vérification.
- [ ] Chaque action irréversible ou qui envoie quelque chose est signalée avant l'étape.
- [ ] Chaque règle de gestion est formulée en « quand… alors… », avec un exemple daté si elle n'est pas évidente.
- [ ] Chaque nombre annoncé (étapes, délais) correspond à la liste qui suit.
- [ ] Les écarts spec/code sont dans « À arbitrer », pas tranchés en silence.
- [ ] La FAQ part des symptômes que l'utilisateur constate (« Je ne peux plus… », « Le participant ne voit pas… »).
- [ ] Le test lecteur frais a été mené avec la consigne « Tu es [profil métier], tu ne connais pas le code ».
