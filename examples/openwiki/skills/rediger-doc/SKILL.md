---
name: rediger-doc
description: À utiliser pour rédiger, réécrire, auditer ou mettre à jour de la documentation - un README, une documentation technique pour développeurs (architecture, guide, how-to, référence, runbook, ADR, guide de migration, changelog) ou une documentation métier/fonctionnelle pour utilisateurs non techniques (guide utilisateur, procédure back-office, règles de gestion, notes de version, FAQ). Use when writing, reviewing or updating a README, developer docs, or end-user/business documentation.
---

# Rédiger de la documentation

## Principe

Un document sert **un lecteur précis** qui doit pouvoir **faire ou décider quelque chose** après l'avoir lu. Tout ce qui ne sert pas ce lecteur sort. Les faits viennent du code, pas de la mémoire.

## Choisir la référence

| Demande | Lire |
|---|---|
| README (création, refonte, audit) | `references/readme.md` |
| Doc pour développeurs, ops, intégrateurs | `references/doc-technique.md` |
| Doc pour utilisateurs métier, non développeurs | `references/doc-metier.md` |

Lire **toujours** `references/style.md` avant de rédiger ou de relire.

## Processus

1. **Cadrer.** Avant d'écrire, fixer quatre choses : le type de document, le lecteur (rôle et niveau), ce qu'il doit pouvoir faire après lecture, ce qui est hors périmètre. Si l'un de ces points est ambigu et change le résultat, poser **une** question ciblée. Sinon, poser une hypothèse et l'annoncer. S'il n'y a pas d'interlocuteur (sous-agent, tâche autonome), ne pas s'arrêter : continuer sur les hypothèses et les lister dans le bilan.
2. **Collecter les faits.** Lire le code, la config, les manifestes, les templates et les libellés d'écran. La doc existante et les specs sont des **indices**, pas des preuves. Noter la provenance de chaque fait (`fichier:ligne`).
3. **Relever les écarts.** Écart entre spec, doc existante et code : le doc décrit le comportement **réel** (le code). Chaque écart va dans la liste « À arbitrer » remise au demandeur. Il ne doit pas rester enfoui dans le texte. Cette liste fait partie du bilan, pas du document : le document ne la cite jamais.
4. **Plan.** Écrire les titres dans l'ordre des besoins du lecteur. Pour un document long (plus de 150 lignes) ou une demande ambiguë, montrer le plan avant de rédiger, s'il y a un interlocuteur.
5. **Rédiger** selon la référence du type et `style.md`.
6. **Relire** avec la checklist de la référence, puis faire une passe de suppression : chaque phrase qui n'aide pas le lecteur à agir ou à décider est supprimée.
7. **Tester avec un lecteur frais.** Lancer un sous-agent **sans contexte**. Lui donner le document seul, plus 3 à 5 questions réalistes du public cible (« Comment je fais X ? », « Que se passe-t-il si Y ? »). Lui demander aussi ce qui est ambigu et ce que le doc suppose connu. Corriger chaque réponse fausse ou hésitante, puis relancer le test. Sur un point marqué `[à vérifier]`, une réponse qui le présente comme incertain compte comme correcte. Le test est terminé quand toutes les réponses sont correctes et qu'il ne reste plus d'ambiguïté susceptible de produire une mauvaise action. Une simple retouche de formulation ne demande pas de nouveau passage. Trois passages au maximum : au-delà, le problème vient de la structure, pas des phrases.
8. **Livrer.** Remettre le document et un bilan court en trois rubriques :
   - **Vérifié** : sources lues, commandes réellement lancées ;
   - **Supposé** : ce qui n'a pas été vérifié, et pourquoi. Une procédure qui n'a pas pu être exécutée est marquée « non testée » ici, en clair ;
   - **À arbitrer** : écarts et questions au demandeur. Les problèmes de sécurité passent en premier.

## Règles non négociables

- Ne rien inventer : ni API, ni commande, ni option, ni libellé, ni chiffre, ni capture. Si une information manque, la signaler dans « À arbitrer » ou poser la question.
- Ne jamais recopier un secret (mot de passe, clé, token), même s'il est versionné dans le dépôt. Écrire seulement son nom et où l'obtenir. Un secret trouvé en clair dans le dépôt est signalé en tête de « À arbitrer ».
- Une procédure se termine par **comment vérifier que ça a marché**.
- Un seul chemin recommandé. Si le code montre deux façons concurrentes de faire, ne pas les juxtaposer. Recommander celle que l'équipe utilise réellement, d'après la CI, le Makefile et l'historique récent. Si ces indices divergent entre eux (le Makefile fait A, mais les commits récents ajoutent B), recommander A et mettre la question dans « À arbitrer ».
- Mise à jour d'un doc existant : corriger d'abord les faits, ensuite la structure, ensuite le style. Garder la structure et le ton existants, sauf si la demande les remet en cause. Montrer les changements de fond avant de les appliquer.

## Erreurs fréquentes

| Erreur | Correctif |
|---|---|
| Le doc suit l'ordre du code (classes, modules) | Suivre l'ordre des tâches du lecteur |
| La tâche principale arrive au §6, après la théorie | Mettre en tête ce que le lecteur vient faire, et l'explication en dessous ou à part |
| Les écarts spec/code ne sont mentionnés que dans le chat | Les mettre dans « À arbitrer », au demandeur |
| Deux méthodes présentées côte à côte sans trancher | Une méthode recommandée, l'autre en note |
| Une procédure sans résultat attendu | Ajouter « Vous devez voir… » et l'étape de vérification |
| Des titres génériques (« Généralités », « Divers ») | Des titres qui disent la tâche ou la réponse |
