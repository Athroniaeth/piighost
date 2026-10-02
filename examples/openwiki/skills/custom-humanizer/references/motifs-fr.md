# Motifs d'IA en français

**Force** :
- **F** (fort) : une occurrence suffit ;
- **G** (grappe) : ne compte que répété, régulier ou combiné à d'autres motifs ;
- **C** (contexte) : ne compte que si le genre le rend creux.

Dans tous les exemples, l'« après » ne contient que des informations de l'« avant ». Quand il n'y a rien à garder, on supprime.

## 1. Formules et lexique

| Motif | Force | Avant → après | Ne pas signaler si |
|---|---|---|---|
| **Ouverture de remplissage** : *dans un monde où, à l'ère de, à l'heure où, de nos jours, dans un contexte de* | F | « À l'heure où la donnée est partout, notre équipe a refondu l'export. » → « Notre équipe a refondu l'export. » | La date ou le contexte apporte une information réelle |
| **Formule d'importance** : *il est important de noter que, il convient de souligner, force est de constater, il est essentiel de rappeler, il faut savoir que* | F | « Il convient de souligner que l'accès est payant. » → « L'accès est payant. » | « Notez que » dans une doc technique, devant un vrai piège |
| **Lexique gonflé, niveau 1** : *véritable* antéposé, *incontournable*, *au cœur de*, *s'inscrire dans*, *un enjeu majeur*, *un levier*, *mettre en lumière*, *témoigner de*, *plonger dans*, *franchir une étape* | F | « Ce module s'inscrit au cœur de notre stratégie. » → supprimer, ou dire ce que fait le module si la source le dit | Sens littéral (« le cœur du réacteur ») |
| **Lexique gonflé, niveau 2** : *crucial, essentiel, ambitieux, robuste, pertinent, innovant, optimal, fluide, intuitif, puissant, clé* (adjectif) | G (2 par paragraphe) | « une étape cruciale d'un projet ambitieux » → « une étape du projet » | Sens technique précis (« estimateur robuste »). Un seul emploi isolé |
| **Verbe de parade** à la place de *être* ou *avoir* : *s'impose comme, se positionne comme, fait figure de, se révèle être, représente* | G | « L'outil se positionne comme une alternative. » → « L'outil est une alternative. » | *Constituer* et *disposer de* en administratif |
| **Participe présent de commentaire** en fin de phrase : *…, permettant de / favorisant / témoignant de / soulignant…* | F | « Le service centralise les dossiers, favorisant une meilleure coordination. » → « Le service centralise les dossiers. » Garder la coordination seulement si la source la démontre | Participe nécessaire au sens ; noms en *-ant* (*participant, apprenant, soignant, intervenant, étudiant*) |
| **« permet de »** en chaîne | G | « Cet écran permet de consulter les sessions. » → « Cet écran affiche les sessions. » | Une seule occurrence porteuse de sens (autorisation) |
| **Nominalisations** : *procéder à la mise en place, effectuer une analyse, réaliser le suivi* | G | « Nous avons procédé à la mise en place d'un suivi. » → « Nous avons mis en place un suivi. » | Texte administratif ou juridique normé |
| **Faux registre soutenu** : *effectuer, problématique* (nom), *thématique, finalité, au sein de, afin de pouvoir* | G | « au sein de l'équipe, afin de pouvoir traiter la problématique » → « dans l'équipe, pour traiter le problème » | Registre soutenu cohérent dans tout le texte |
| **Calques** : *adresser* un problème, *faire sens, supporter* (prendre en charge), *délivrer* de la valeur, *impacter, opportunité* (occasion), *basé sur, en termes de, être en charge de, initier* | G (faible seul) | « Cette version adresse le bug et supporte IPv6. » → « Cette version corrige le bug et prend en charge IPv6. » | Emprunt installé dans le métier ; terme imposé par l'organisation |
| **Connecteurs en pluie** : *De plus, Par ailleurs, En outre, Ainsi, En effet, Toutefois* en tête de phrases successives | G (la régularité trahit) | « Ainsi, X. Par ailleurs, Y. En outre, Z. » → « X. Y. Z. », ou fusion | Connecteur qui porte une vraie relation (cause, opposition) |
| **Posture didactique** : *ce qu'il faut comprendre, c'est que ; derrière les chiffres se cache ; et c'est là que tout change* | F | « Ce qu'il faut comprendre, c'est que l'offre est limitée. » → « L'offre est limitée. » | — |
| **Formules de chatbot et de courrier** : *j'espère que ce message vous trouve en forme, je me permets de revenir vers vous, n'hésitez pas à, je reste à votre entière disposition, j'espère que cela vous aide, excellente question* | F | « N'hésitez pas à me contacter pour toute question. Je reste à votre entière disposition. » → « Pour toute question, écrivez-moi. » | Le genre attend une formule de politesse : la **raccourcir**, pas la supprimer. Garder le vouvoiement |
| **Conclusion annoncée et morale** : *en définitive, en somme, au final, vous l'aurez compris, en conclusion*, suivis d'une vérité générale | F | « En définitive, l'outil n'est qu'un moyen au service des équipes. » → supprimer | La conclusion apporte une information nouvelle (décision, date) |

## 2. Structures

| Motif | Force | Avant → après | Ne pas signaler si |
|---|---|---|---|
| **Faux contraste** : *ce n'est pas X, c'est Y ; pas seulement… mais avant tout ; bien plus qu'un ; loin d'être un simple ; il ne s'agit pas de* | F | « Ce n'est pas un simple outil, c'est une méthode. » → « L'outil impose une méthode. » (seulement si la source dit laquelle ; sinon supprimer) | X est une objection réelle du lecteur, que le texte réfute |
| **Question puis réponse** : *Le résultat ? … ; Pourquoi ? Parce que…* | F | « Le résultat ? Des délais divisés par deux. » → « Les délais ont été divisés par deux. » | FAQ ; vraie question posée au lecteur |
| **Triade adjectivale et doublet** : *simple, rapide et efficace ; simple et intuitif* | G | Doublet synonyme : « une interface simple et intuitive » → « une interface simple ». Trois affirmations distinctes : casser le moule sans les perdre, « L'outil est plus stable et moins cher. Il est aussi plus clair. » | Énumération réelle (trois étapes, trois produits) |
| **Puces à étiquette en gras** : « **Le suivi est clé** : … » | G | « • **La rigueur est essentielle** : nous relisons chaque contrat. » → « • Nous relisons chaque contrat. » | Doc de référence (terme puis définition) |
| **Phrase-chute, aphorisme** : *et ça change tout ; voilà tout l'enjeu ; la technologie n'est qu'un outil* | F | « Pas d'attente. Pas de relance. Et ça change tout. » → « Le dossier part sans attente ni relance. » | — |
| **Annonce de plan** : *voici ce que nous avons appris ; plongeons dans ; décryptage ; dans cet article, nous allons* | F | « Voici les trois leçons que nous en tirons : » → la liste seule, ou une introduction courte et factuelle (« Ce que nous en retenons : ») | « Voici » devant une liste attendue (ordre du jour, étapes) |
| **« Que vous soyez X ou Y »** | F | « Que vous soyez débutant ou expert, ce guide vous aidera. » → supprimer, ou dire à qui le guide sert | — |
| **Rythme uniforme** : 4 phrases ou plus de même longueur et de même moule | G | Fusionner deux idées liées, couper une phrase trop chargée, selon le sens | Liste d'instructions ; style uniforme assumé de l'auteur |
| **Appel à l'interaction plaqué** : *Et vous, comment… ? Partagez en commentaire ! 👇* | C | Garder une question si la source en pose une, formulée simplement | Genre LinkedIn : une question finale sobre est la norme |

## 3. Registre

| Motif | Force | Correction |
|---|---|---|
| **Registre incohérent** : *tu* et *vous*, *nous* et *on* mélangés | F | Aligner sur la forme dominante de la source |
| **Faux familier** : *ça pique, fait le job, bon, honnêtement*, **ajoutés** par une réécriture ou isolés dans un texte par ailleurs formel | F | C'est l'effet pervers de la sur-humanisation. Revenir au registre de la source. Les marques d'oral cohérentes de l'auteur dans un message informel ne sont pas un tic (§6) |
| **Accents absents** : *Etat, ca, a* pour *à* | F | Rétablir : *État, ça, à*. Majuscules accentuées (*À, É*) |

## 4. Mise en forme

| Motif | Force | Correction | Ne pas signaler si |
|---|---|---|---|
| Emojis décoratifs en tête de ligne (🚀 ✅ 👉) | G | Supprimer | Message informel où l'auteur en met d'habitude |
| Hashtags en grappe (plus de 3) | C | Réseaux sociaux : garder les 1 à 3 plus précis, en retirant d'abord les génériques (#Innovation, #Digital). Ailleurs : supprimer | — |
| Gras décoratif | G | Garder le gras pour un libellé d'écran ou un avertissement | — |
| Titres à l'anglaise (« Guide Complet Pour Déployer ») | F | Majuscule au premier mot et aux noms propres | — |

## 5. Typographie française

Harmoniser selon la convention **dominante** de la source. Ne corriger que les erreurs nettes : guillemets droits ou anglais dans de la prose française, styles mélangés, accents manquants. Ne pas **ajouter** d'insécables si la source n'en contient aucune, sauf demande d'une version à publier.

- **Guillemets** « » avec une espace insécable à l'intérieur ; “ ” seulement à l'intérieur d'une citation. Les guillemets droits `"…"` restent dans le code.
- **Espaces avant la ponctuation haute** : insécable (U+00A0) avant `:` ; insécable fine (U+202F) ou insécable avant `; ! ?`. Ne jamais retirer une insécable existante : un passage conservé garde ses insécables, même réécrit avec un outil d'édition.
- **Tirets** :
  - le tiret collé à l'anglaise (`mot—incise—suite`) devient des virgules, des parenthèses ou une incise espacée ;
  - l'incise espacée `mot — incise — suite` est correcte : la limiter à une par paragraphe ;
  - le demi-cadratin sert aux plages (`2024–2026`).
- **Nombres** : `12 500`, `2,5`, `15 %`, `12 €`, `9 h 30`, `1er`, `2e`. Ne jamais changer la valeur.
- Points de suspension en un seul caractère (`…`). Mois, jours et adjectifs de nationalité en minuscule.
- Pas de virgule avant le *et* final d'une énumération simple (virgule d'Oxford).

## 6. Ne pas signaler en français

- *notamment, ainsi, toutefois* employés seuls : la prose française en use plus que l'anglais.
- Le passif et le pronominal administratifs (« la demande est instruite »), le subjonctif, un registre soutenu cohérent.
- Les phrases sans verbe dans une fiche, une liste de prérequis ou un tableau.
- *disposer de, bénéficier de, à l'issue de, au regard de, mettre en œuvre* dans un texte administratif.
- Les insécables régulières : c'est de la bonne typographie, pas un indice.
- Les marques d'oral réelles de l'auteur (*du coup, bon*, ellipse du *ne*) dans un message informel.

## Exemple complet

**Avant**

> Dans un contexte de digitalisation croissante, notre service RH a franchi une étape majeure : le déploiement d'un nouvel outil de gestion des congés. Bien plus qu'un simple logiciel, il s'agit d'un véritable levier de simplification, permettant aux 340 salariés de poser leurs congés en quelques clics. De plus, les managers valident désormais les demandes depuis leur téléphone. En définitive, cette évolution témoigne de notre engagement envers la qualité de vie au travail.

**Après**

> Notre service RH a déployé un nouvel outil de gestion des congés. Les 340 salariés y posent leurs congés en quelques clics, et les managers valident désormais les demandes depuis leur téléphone.

**Bilan**

- **Modifié** : ouverture de remplissage, lexique de niveau 1 (*étape majeure, véritable levier*), faux contraste (*bien plus qu'un simple*), participe de commentaire, connecteur, conclusion morale.
- **Conservé volontairement** : « en quelques clics », qui est l'affirmation de la source sur la simplicité.
- **Retiré** : « engagement envers la qualité de vie au travail ». C'est une affirmation de la source, à remettre en une phrase factuelle si l'auteur y tient.
- **Contrôle du sens** : 340, « désormais » et « notre » conservés ; aucun ajout.
- **À confirmer** : le nom de l'outil, s'il doit apparaître.
