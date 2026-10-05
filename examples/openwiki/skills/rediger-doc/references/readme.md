# README

Le README est la **porte d'entrée** du projet : il dit ce qu'est le projet et comment le lancer, puis il oriente vers le reste de la doc. Ce n'est pas une encyclopédie. Le lecteur décide en moins d'une minute s'il continue.

## Identifier le lecteur

| Type de projet | Lecteur principal | Le README doit lui permettre de… |
|---|---|---|
| Application interne / web app | Dev qui rejoint l'équipe, déployeur | lancer l'app en local et savoir où lire la suite |
| Bibliothèque / paquet | Dev qui évalue puis intègre | installer et faire un premier appel |
| CLI | Utilisateur en terminal | installer et lancer 3 commandes typiques |
| Monorepo / plateforme | Tous | **router** vers le bon sous-projet ou la bonne doc |

## Sections, dans l'ordre

Chaque section doit avoir sa raison d'être. Une section vide ou triviale fait plus de tort que son absence.

1. **Titre** (toujours) : le nom exact du projet, sans emoji ni version.
2. **Accroche** (toujours), directement sous le titre :
   - 1 phrase qui dit **ce que fait le projet et pour qui** ;
   - puis 2 à 4 phrases sur le problème résolu.

   Formule : `[Nom] est un [catégorie] qui [fait X] pour [public].`
3. **Badges**, seulement s'ils sont utiles :
   - 5 au maximum, sur une seule ligne, dans l'ordre CI, version, licence ;
   - aucun pour une application interne.
4. **Aperçu** (capture ou GIF), pour une UI ou une CLI, avec un texte alternatif.
5. **Démarrage rapide** (toujours) :
   - 5 étapes au maximum, dans un seul bloc copiable ;
   - prérequis en une ligne, avec des versions quand le projet les fixe. Pour un projet privé, les accès (SSH, registre, secrets à demander) font partie des prérequis et ne comptent pas dans les 5 étapes ;
   - se termine par le **résultat attendu** : URL à ouvrir, comment obtenir un compte de test, sortie de commande.
6. **Installation détaillée** : seulement si le démarrage rapide ne couvre pas tous les cas (OS, méthodes alternatives). Ajouter une commande de vérification (`outil --version`).
7. **Utilisation** : 2 à 4 scénarios, du plus simple au plus avancé, avec du vrai code et sa sortie.
8. **Configuration** :
   - un tableau `Variable | Rôle | Défaut | À définir en local ?` ;
   - le lecteur ne doit jamais aller lire le code pour trouver un défaut ;
   - les secrets ne sont jamais écrits : seulement leur nom et où les obtenir.
9. **Tests et outils dev** : la commande pour lancer les tests, en tête de section.
10. **Architecture** :
    - seulement si elle n'est pas évidente ;
    - 5 à 10 boîtes au maximum (Mermaid), centrées sur le **flux de données** ;
    - sinon, un lien vers la doc d'architecture.
11. **Documentation** : liens vers `docs/`, avec une ligne par lien qui dit à qui sert le document.
12. **Limites / non-objectifs** : ce que le projet ne fait pas, son niveau de maturité.
13. **Contribuer** : seulement si le projet accepte des contributions externes. Sinon, renvoyer vers le guide de dev.
14. **Licence** (toujours) : une ligne, cohérente avec le fichier `LICENSE`. « Propriétaire » pour un projet interne.

Une FAQ ou un dépannage n'apparaît que s'il existe de vraies questions récurrentes. Dans ce cas, chaque entrée prend pour titre le **message d'erreur exact**, suivi de la solution.

## Longueur

| Projet | Lignes |
|---|---|
| Utilitaire / petite lib | 50 à 150 |
| Application / framework | 150 à 400 |
| Plateforme | 300 à 600, en routage vers la doc |

Au-delà de 200 lignes, ajouter une table des matières. Au-delà de 600 lignes, déplacer du contenu dans `docs/`.

## Établir les faits avant d'écrire

Dresser la liste des faits à partir du code, avant d'écrire la moindre ligne :

- nom ;
- points d'entrée ;
- commandes : Makefile, Taskfile, scripts du `package.json`, `bin/console` ;
- variables d'environnement et leurs défauts (`.env*`) ;
- services : `compose.yml` ;
- versions : manifestes, `Dockerfile` ;
- CI.

**Contradictions.** Si deux sources se contredisent, par exemple `make install` lance `schema:update` alors que la doc dit `migrations:migrate`, ne pas les juxtaposer. Appliquer la règle « un seul chemin » de `SKILL.md`.

## Mettre à jour un README existant : passe de dérive

1. Extraire du README chaque commande, chemin, variable, option, import et URL.
2. Vérifier chacun contre sa définition réelle : manifeste, parser CLI, `.env`, routes, exports. Une simple occurrence de la chaîne dans le code ne suffit pas comme preuve.
3. Classer chaque écart : renommé, supprimé, déplacé, signature changée, non documenté, ambigu. Citer le fichier qui le prouve.
4. Corriger depuis la source. Ne jamais inventer d'alias ni de compatibilité. Si aucun remplaçant n'est prouvé, le dire.
5. Dans le bilan, ajouter un tableau `Avant | Maintenant | Preuve`.

## Anti-patterns

| Anti-pattern | Symptôme | Correctif |
|---|---|---|
| Le mensonge | Une commande ou une API ne correspond plus au code | Passe de dérive |
| Installer et prier | `composer install` sans prérequis ni versions | Prérequis, versions, vérification |
| Le roman | Le README duplique `docs/` | Garder l'orientation et mettre des liens |
| Template zombie | Sections « TODO » ou vides | Les supprimer |
| Soupe de badges | La description est sous la ligne de flottaison | 5 badges au maximum, ou aucun |
| Squelette d'outil | Le README par défaut du framework (« Symfony Standard Edition ») | Réécrire entièrement |
| Pitch marketing | « Moderne, rapide, puissant » | Un fait chiffré ou rien |

## Checklist

- [ ] **Test des 10 secondes.** En lisant seulement ce qui précède le premier `##`, on sait ce que fait le projet et pour qui.
- [ ] Le démarrage rapide fait 5 étapes au plus, finit par un résultat observable, et ses commandes existent dans le code.
- [ ] Les prérequis sont versionnés et les dépendances externes nommées (accès privés, services).
- [ ] Les variables de config ont leur défaut. Aucun secret n'est écrit en clair.
- [ ] La commande de tests est présente et exacte.
- [ ] Aucune section n'est vide, générique ou en double avec `docs/`.
- [ ] Tous les liens internes pointent vers des fichiers existants.
- [ ] La licence est indiquée.
