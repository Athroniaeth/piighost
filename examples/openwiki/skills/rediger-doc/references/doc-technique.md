# Documentation technique (développeurs, ops, intégrateurs)

## 1. Choisir le type (Diátaxis)

Chaque document, ou à défaut chaque section, sert **un seul** des quatre besoins.

|  | Le lecteur **apprend** | Le lecteur **travaille** |
|---|---|---|
| **Il agit** | Tutoriel | Guide pratique (how-to) |
| **Il cherche à savoir** | Explication | Référence |

Deux questions suffisent :

1. Le lecteur sait-il déjà ce qu'il veut faire ? Non : tutoriel. Oui : how-to.
2. Le contenu décrit-il **ce qui existe** (référence) ou **pourquoi ça existe ainsi** (explication) ?

Cas fréquents :

- **« Comment fonctionne X, comment ajouter un Y, comment tester »** : une demande, trois besoins.
  - Faire un fichier par type, reliés par des liens, si `docs/` est déjà rangé par type (`guides/`, `reference/`…) ou si la page dépasserait 300 lignes.
  - Sinon, faire une seule page avec des sections typées, dans cet ordre :
    1. Vue d'ensemble courte (10 lignes au maximum) : explication.
    2. Les tâches : how-to. C'est souvent la raison pour laquelle on ouvre la page.
    3. Référence : tableaux, configuration, inventaire.
    4. Pièges.
- Un **onboarding de nouvel arrivant**, c'est un tutoriel : un seul chemin, un résultat visible à chaque étape.
- Les **ADR, runbooks, guides de migration et changelogs** ont chacun leur propre gabarit (§4).

**Contamination**, c'est-à-dire du contenu d'un autre type qui s'infiltre dans une section : l'extraire et laisser un lien à la place.

| Dans… | Signal | Contenu qui s'est infiltré |
|---|---|---|
| How-to / tutoriel | « Commençons par comprendre… », long paragraphe sur le pourquoi | explication |
| How-to / tutoriel | tableau exhaustif d'options | référence |
| Référence | « D'abord…, puis… », « nous recommandons » | how-to |
| Explication | étapes numérotées, signatures | how-to / référence |

## 2. Règles par type

### How-to

- Titre : « Ajouter… », « Configurer… », « Déboguer… », c'est-à-dire le **résultat** visé par le lecteur, pas le nom du composant.
- Première ligne : ce que le guide permet de faire et quand on en a besoin.
- Si plusieurs chemins existent : commencer par un **arbre de décision** (« Votre e-mail part à date fixe → checker. Il part sur action → méthode de `EmailSender` »).
- Étapes numérotées, une action par étape. Partir du **modèle existant le plus proche dans le code** (« Copiez `src/.../EmailFormationOpened.php` ») plutôt que d'un exemple inventé.
- Les étapes peuvent contenir des conditions (« Si l'item n'est pas une `Participation`, … »). Pas de cours dans les étapes : une phrase de contexte au maximum, plus un lien.
- Section **Vérifier** obligatoire : commande, URL, requête SQL ou test qui prouve que ça marche.

### Référence

- Calquée sur la structure du produit : par module, par commande, par endpoint.
- Ton neutre : décrire, sans instruire ni recommander.
- Par élément : description en une phrase qui commence par un verbe (avec ses effets de bord), paramètres ou options (`Nom | Type | Défaut | Obligatoire | Description`), retour, erreurs, puis un exemple court.
- Exhaustive sur son périmètre. Si elle est générée (OpenAPI, phpDoc), ne pas la dupliquer : la compléter.

### Explication

- Elle répond au **pourquoi** : contexte, contraintes, choix faits, alternatives écartées, compromis (`Choix | Gain | Coût`).
- Elle n'a pas d'étapes. Un diagramme Mermaid de 10 boîtes au plus, centré sur le flux, avec un texte qui dit la même chose.

### Tutoriel

- Il décrit ce que le lecteur va **obtenir** (et non « ce que vous allez apprendre »).
- Un seul chemin, sans alternative. Chaque étape montre une **sortie attendue** (« Vous devez voir… »).
- Il est fiable à 100 %, ce qui suppose de rejouer les étapes ou de dire ce qui n'a pas pu l'être.

## 3. Ancrage dans le code

- Citer les chemins réels (`src/Eduprat/DomainBundle/Services/EmailSender.php`) et les noms exacts (classes, commandes, routes, variables d'environnement). Vérifier chacun.
- Distinguer **vérifié** et **supposé**. Une affirmation qui dépend de code absent (`vendor/` non installé, service externe) est marquée `[à vérifier]`, accompagnée de la commande qui permettrait de trancher (`php bin/console debug:container --tag=…`).
- Les exemples de code compilent dans le projet : vrais namespaces, vraies signatures.
- Une section **Pièges** recense ce qui surprend et coûte cher : comportements par défaut dangereux, erreurs avalées, valeurs codées en dur, noms trompeurs. C'est souvent la partie la plus utile du document.
- Si la doc existante dit faux (nom de commande obsolète…), le signaler dans « À arbitrer » et proposer la correction.

## 4. Gabarits

**How-to**

```
# <Verbe + résultat>
<1 phrase : ce que ça permet, quand l'utiliser>
## Avant de commencer      (prérequis, en liens)
## Choisir l'approche      (si plusieurs chemins)
## Étapes                  (1. 2. 3. ; une action par étape, puis le résultat)
## Vérifier
## Pièges / dépannage      (symptôme → cause → correctif)
## Voir aussi              (référence, explication)
```

**Runbook** : `# <Service> : runbook`

- En-tête : propriétaire, date de dernière vérification, escalade.
- Accès : tableau `Système | URL | Logs`.
- Alertes : tableau `Alerte | Sévérité | Signification`.
- Par scénario : symptômes, impact, résolution (commandes exactes, puis vérification), puis « Escalader après N min vers X ».

**ADR** : `# ADR-NNN : <décision>`

- Statut (Proposé, Accepté, Remplacé par ADR-X) et date.
- Contexte, puis décision.
- Conséquences, positives et négatives.
- Alternatives écartées, chacune avec la raison.

**Guide de migration** : `# Migrer de vX à vY`

- En tête : effort estimé, nombre de changements cassants.
- Prérequis : sauvegarde, version de départ.
- Par changement cassant : quoi, pourquoi, avant, après.
- Dépréciations, vérification, **retour arrière**.

**Changelog** (format Keep a Changelog) : `## [version] - AAAA-MM-JJ`

- Rubriques : Ajouté, Modifié, Déprécié, Supprimé, Corrigé, Sécurité.
- Une phrase par entrée, orientée vers l'impact (« Vous pouvez maintenant… »), avec le lien vers le ticket ou la MR.

**Dépannage**

- Organisé par symptôme. Titre = **message d'erreur exact**.
- Puis diagnostic (commande), solution, cause en bref.
- Les causes vont de la plus probable à la plus rare.

## 5. Checklist

- [ ] Le type est identifié. Aucune section ne mélange deux types.
- [ ] La tâche principale du lecteur est accessible depuis le haut de la page (plan ou arbre de décision).
- [ ] Chaque chemin, classe, commande et variable cité existe, avec l'orthographe exacte.
- [ ] Chaque how-to se termine par une vérification.
- [ ] Les hypothèses sont marquées `[à vérifier]`, avec le moyen de trancher.
- [ ] La section Pièges est présente quand le code réserve des surprises.
- [ ] Les liens vont vers les autres types (how-to vers référence, explication vers how-to).
- [ ] La longueur est proportionnée : au-delà de 300 lignes, découper en plusieurs fichiers.
