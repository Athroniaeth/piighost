---
icon: lucide/gavel
tags:
  - Avancé
  - Détecteur
---

# Masquer ou laisser en clair

Votre détecteur lit le nom de votre entreprise comme une personne et vous voulez qu'il reste en clair. Vos noms de code internes ne sont jamais détectés et vous voulez qu'ils soient remplacés à chaque fois. Ces deux décisions portent sur le jeu de détections plutôt que sur le détecteur. `DetectionOverride` est l'étape qui les impose, avec deux détecteurs. La liste à masquer (`deny_list`) porte ce qui est masqué même quand le détecteur le rate, et ce que son détecteur trouve est forcé dans le jeu. La liste à laisser en clair (`allow_list`) porte ce qui reste en clair même quand le détecteur le trouve, et ce que son détecteur trouve est retiré du jeu.

L'étape s'exécute juste après la détection, avant la résolution des chevauchements et la liaison. Ses deux listes l'emportent donc sur la lecture du détecteur, et aussi sur un jeu corrigé qui revient d'une relecture humaine. Voir [Architecture](../architecture.md) pour l'ordre complet des étapes.

!!! note "Prérequis"
    `piighost` seul, `pip install piighost`. Chaque exemple ci-dessous s'exécute tel quel, sans téléchargement de modèle. La section 2 et le fichier de configuration tirent le groupe générique du [catalogue piighost](https://catalog.piighost.dev), récupéré à chaque construction du pipeline, ce qui demande un accès réseau. La dernière section lit un fichier de configuration, ce qui demande l'extra config, `pip install "piighost[config]"`.

!!! note "Renommées en 2.0"
    La liste à masquer s'appelait la whitelist avant `piighost` 2.0, et la liste à laisser en clair la blacklist. Une config qui emploie encore les anciens noms est refusée au chargement, voir [Passer à la 2.0](../community/upgrading.md#les-listes-de-loverride-sont-renommees).

## 1. Laisser une valeur en clair avec une liste à laisser en clair

Pointez un détecteur sur la valeur, passez-le à `DetectionOverride` comme liste à laisser en clair, puis passez l'override au pipeline. Ce que la liste à laisser en clair trouve quitte le jeu de détections, donc la valeur arrive en clair au modèle.

```python
--8<-- "snippets/overrides_allow_list.py"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_allow_list.out"
```

`allow_list_strategy` décide quelles détections une valeur trouvée par la liste à laisser en clair emporte.

- Gardez `AllowListStrategy.VALUE`, le défaut, quand la valeur ne doit jamais être dé-identifiée, quel que soit le label que le détecteur lui donne. Il écarte toute détection qui porte le même texte, sans tenir compte de la casse, de la position ni du label. Le label que vous écrivez à côté de la valeur n'a donc jamais à correspondre à celui que le détecteur primaire émet.
- Utilisez `AllowListStrategy.EXACT` quand c'est le label qui compte, et que les deux détecteurs lisent la valeur de la même façon. Il n'écarte une détection que si son span et son label correspondent tous les deux à la valeur trouvée.
- Utilisez `AllowListStrategy.OVERLAP` quand une détection plus longue contenant la valeur doit tomber aussi. Il écarte toute détection dont le span touche un span de la liste à laisser en clair, labels ignorés.

Les trois modes sur un même texte, avec un détecteur qui étiquette `Acme`{ .pii } comme une personne et lit `Globex Ltd`{ .pii } comme une seule organisation.

```python
--8<-- "snippets/overrides_allow_list_strategies.py"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_allow_list_strategies.out"
```

`EXACT` n'a rien trouvé à écarter, pour deux raisons. La liste à laisser en clair dit que `Acme`{ .pii } est une organisation, là où le détecteur dit une personne. Et le span du détecteur couvre `Globex Ltd`{ .pii }, là où la liste à laisser en clair ne couvre que `Globex`{ .pii }. `VALUE` compare des valeurs entières, donc il a écarté `Acme`{ .pii } et laissé `Globex Ltd`{ .pii }, dont le texte n'est pas celui de la liste à laisser en clair. `OVERLAP` a écarté les deux, parce que le span de la liste à laisser en clair est à l'intérieur de la détection plus longue.

!!! note "Une valeur de la liste à laisser en clair ne déclenche pas le garde-fou"
    Un [garde-fou](../reference/guard-rails.md) relit la sortie et refuse les données confidentielles résiduelles. Le pipeline lui transmet les valeurs que la liste à laisser en clair a trouvées dans le texte, donc une valeur que vous laissez volontairement en clair est exemptée. Toute autre fuite lève quand même `PIIRemainingError`.

## 2. Forcer une valeur ratée avec une liste à masquer

Pointez un détecteur sur le motif que le détecteur principal rate, ici un nom de code qu'une regex décrit exactement, et passez-le comme liste à masquer. Ce qu'il trouve entre dans le jeu de détections, quoi qu'ait vu le détecteur principal.

```python
--8<-- "snippets/overrides_deny_list_catalog.py"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_deny_list_catalog.out"
```

Une détection forcée remplace aussi toute détection qu'elle chevauche, donc le label de la liste à masquer l'emporte sur la lecture principale. Servez-vous-en pour corriger un label, pas seulement pour ajouter une détection.

```python
--8<-- "snippets/overrides_deny_list_exact.py:example"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_deny_list_exact.out"
```

Une valeur forcée passe par la liaison et l'attribution de jeton comme n'importe quelle détection, donc le pipeline conversationnel la stocke en mémoire et `deanonymize` la restaure.

## 3. Dé-identifier une valeur introduite par l'assistant

Dans une conversation, une valeur que l'assistant a écrite le premier reste en clair même si la liste à masquer la trouve. Le modèle a produit cette valeur parce qu'elle était utile dans le contexte, et il ne sait pas qu'elle est confidentielle. La remplacer lui retirerait sa connaissance du monde, et signalerait que cette valeur précise est sensible. `deny_list_strategy` décide qui l'emporte.

- Gardez `DenyListStrategy.RESPECT_PROVENANCE`, le défaut, pour laisser en clair une valeur introduite par l'assistant. La liste à masquer garantit toujours que la valeur est détectée, et la même valeur introduite par l'utilisateur est bien dé-identifiée.
- Utilisez `DenyListStrategy.FORCE` pour dé-identifier une valeur de la liste à masquer quel que soit celui qui l'a écrite le premier.

```python
--8<-- "snippets/overrides_deny_list_provenance.py"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_deny_list_provenance.out"
```

## 4. Décider qui l'emporte quand les deux listes se contredisent

Une valeur que les deux listes trouvent est une contradiction, et `conflict_strategy` nomme le gagnant.

- Gardez `OverrideConflictStrategy.DENY_LIST_WINS`, le défaut, pour dé-identifier la valeur contredite. La liste à laisser en clair s'applique d'abord aux détections principales, puis la liste à masquer est forcée en dernier.
- Utilisez `OverrideConflictStrategy.ALLOW_LIST_WINS` pour la garder en clair. La liste à masquer est forcée d'abord, puis la liste à laisser en clair écarte le résultat, détections forcées comprises.
- Utilisez `OverrideConflictStrategy.RAISE` pour refuser la contradiction. Un span de la liste à masquer qui chevauche un span de la liste à laisser en clair lève `ConflictingOverrideError` avant l'application de l'une ou l'autre liste.

```python
--8<-- "snippets/overrides_conflict.py"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_conflict.out"
```

`ALLOW_LIST_WINS` écarte une détection forcée selon la stratégie de la liste à laisser en clair. Avec le défaut `VALUE`, une valeur forcée est donc écartée quel que soit le label que la liste à masquer lui a attaché. Sous `EXACT`, les deux listes doivent s'accorder sur le label pour que la liste à laisser en clair l'emporte.

## 5. Piloter les deux listes depuis un fichier de configuration

Les deux listes sont des configs de détecteur, `[override.deny_list]` et `[override.allow_list]`, et les trois stratégies sont des clés de `[override]`. Le fichier ci-dessous force le nom de code et garde en clair une boîte mail publique.

```toml
--8<-- "snippets/overrides_config.toml"
```

`load_pipeline` lit le fichier et construit le pipeline, les deux listes comprises.

```python
--8<-- "snippets/overrides_config.py"
```

La sortie doit être :

```text
--8<-- "snippets/overrides_config.out"
```

Pour chaque clé et chaque valeur acceptée, voir la [configuration TOML](../configuration/toml.md).

## Voir aussi

- [Détecteurs prêts à l'emploi](detectors.md) pour les détecteurs sur lesquels reposent les deux listes.
- [Référence du pipeline](../reference/pipeline.md) pour le paramètre `override` et l'ordre des étapes.
- [Garde-fous](../reference/guard-rails.md) pour le contrôle de sortie dont la liste à laisser en clair exempte une valeur.
- [Configuration TOML](../configuration/toml.md) pour les clés de `[override]`.
- [Imposer une liste à masquer et une liste à laisser en clair](../../../openwiki/fr/processes/impose-a-deny-list-and-an-allow-list.md) pour les règles de gestion des deux listes, de `BR-LIST-01` à `BR-LIST-08`.
