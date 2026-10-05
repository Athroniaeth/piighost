---
type: workflow
title: Imposer une liste à masquer et une liste à laisser en clair
description: Comment la liste à masquer de la configuration (section override) force le masquage d'une valeur que le détecteur rate, comment la liste à laisser en clair garde une valeur en clair, qui gagne quand les deux se contredisent, et pourquoi ces listes priment sur une correction humaine.
tags: [override, deny-list, allow-list, detection, guard, provenance]
sources:
  - id: openwiki-source-6b7f5f02702990f6448a1a5f
    resource: repo://src/piighost/components/override/detector.py
  - id: openwiki-source-aa2829050fd72de956faf3f4
    resource: repo://src/piighost/components/override/strategy.py
  - id: openwiki-source-169555bcaa5f0efb2e817dc5
    resource: repo://src/piighost/config/models/override.py
  - id: openwiki-source-5ddce4dd4539293afb49cdfd
    resource: repo://src/piighost/pipeline/base.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Imposer une liste à masquer et une liste à laisser en clair

## En bref

- Deux listes, écrites dans la section `[override]` de la configuration, corrigent le détecteur. La liste à masquer (`deny_list` dans la configuration) masque une valeur même si le détecteur la rate. La liste à laisser en clair (`allow_list`) garde une valeur en clair même si le détecteur la trouve. Une valeur que l'assistant cite le premier fait exception, et reste en clair par défaut.
- La configuration est celle du pipeline, qu'il tourne dans l'application ou dans le serveur `piighost-api`.
- Ces listes passent avant tout le reste, y compris avant une correction faite à la main par une personne.
- Une valeur de la liste à laisser en clair part au modèle en clair, et le contrôle final ne la bloque pas.
- Quand les deux listes visent la même valeur, la liste à masquer gagne par défaut, donc la valeur est masquée.
- Une liste modifiée ne s'applique qu'aux messages nouveaux d'une conversation déjà commencée.

Besoins couverts, décrits dans [Besoins par profil](../needs-by-profile.md) :

- Responsable conformité : DPO-3
- Utilisateur de l'application : USER-5, USER-6

Les termes sont définis dans le [glossaire](../glossary.md). Le déroulé complet d'un message est dans [Protéger un message avant l'envoi au modèle](protect-a-message.md).

## Pour le métier

`piighost` n'a pas d'écran. La liste à masquer et la liste à laisser en clair sont écrites par l'équipe technique, dans le code ou dans la section `[override]` du fichier de configuration de l'application ou du serveur `piighost-api`. Le DPO décide de leur contenu. Les tâches ci-dessous disent quoi demander.

### Le trajet d'un message à travers les listes

```mermaid
flowchart TD
    A["Message de l'utilisateur"] --> B["Repérage par le détecteur"]
    B --> C["Liste à laisser en clair : la valeur reste en clair"]
    B --> D["Liste à masquer : la valeur est masquée, même ratée"]
    C --> E{"Les deux listes visent le même passage ?"}
    D --> E
    E -- "réglage de conflit" --> F["Remplacement par jeton"]
    F --> G["Contrôle final, qui ignore la liste à laisser en clair"]
    G --> H["Envoi au modèle"]
```

### Exemple suivi d'un bout à l'autre

La liste à masquer contient la forme « PRJ- suivi de quatre chiffres », avec le type `CODE`. La liste à laisser en clair contient « Acme », le nom de l'entreprise. Le détecteur lit « Acme » comme une personne et ne connaît pas les numéros de dossier.

| Étape | Texte |
|---|---|
| Message de l'utilisateur | Écrivez à Jean Dupont, chez Acme, dossier PRJ-0042. |
| Sans les listes | Écrivez à `<<PERSON:1>>`, chez `<<PERSON:2>>`, dossier PRJ-0042. |
| Avec les listes, reçu par le modèle | Écrivez à `<<PERSON:1>>`, chez Acme, dossier `<<CODE:1>>`. |
| Réponse lue par l'utilisateur | C'est noté pour PRJ-0042. |

### Garder une valeur en clair

Cas typique : le nom de votre entreprise est lu comme un nom de personne, et le modèle en a besoin pour répondre.

1. Listez les valeurs exactes à garder en clair, avec leur orthographe.
2. Précisez si la valeur doit rester en clair quelle que soit la façon dont le détecteur la classe. C'est le réglage par défaut.
3. Si une valeur plus longue la contient (« Acme Services » pour « Acme »), dites si la valeur longue doit aussi rester en clair.
4. Transmettez la liste à l'équipe technique.

**Comment vérifier** : faites protéger une phrase de test. Par exemple, « Claire Dubois travaille chez Acme. » doit donner « `<<PERSON:1>>` travaille chez Acme. »

### Forcer le masquage d'une valeur

Cas typique : vos noms de code internes ne sont jamais repérés.

1. Décrivez la forme exacte des valeurs, par exemple « PRJ- suivi de quatre chiffres ».
2. Précisez si une valeur citée d'abord par l'assistant doit aussi être masquée. Par défaut, non (BR-LIST-05).
3. Transmettez la description à l'équipe technique.

**Comment vérifier** : faites protéger une phrase qui contient un nom de code. Il doit être remplacé par un jeton comme `<<CODE:1>>`.

### Règles à connaître

**BR-LIST-01.** Quand une valeur figure dans la liste à laisser en clair, alors elle est retirée des valeurs à masquer et part au modèle en clair.

**BR-LIST-02.** Quand une valeur figure dans la liste à masquer, alors elle est masquée, même si le détecteur l'a ratée. Si le détecteur avait repéré un morceau qui la chevauche, la détection de la liste à masquer remplace ce morceau.

**BR-LIST-03.** Quand la liste à laisser en clair vise une valeur, alors la façon de l'appliquer suit l'un de trois réglages. Exemple sur « Claire Dubois travaille chez Acme, puis chez Globex SA. », avec un détecteur qui lit « Acme » comme une personne et « Globex SA » comme une organisation, et une liste à laisser en clair qui contient « Acme » et « Globex » comme organisations.

Le tableau suivant donne le résultat de chaque réglage :

| Réglage | Retire | Résultat |
|---|---|---|
| Même valeur (par défaut) | toute détection du même texte, quels que soient position et type | `<<PERSON:1>>` travaille chez Acme, puis chez `<<ORG:1>>`. |
| Exact | seulement une détection de même position et de même type | `<<PERSON:1>>` travaille chez `<<PERSON:2>>`, puis chez `<<ORG:1>>`. |
| Chevauchement | toute détection qui touche la valeur, même plus longue | `<<PERSON:1>>` travaille chez Acme, puis chez Globex SA. |

« Même valeur » est le défaut parce que la liste à laisser en clair nomme une valeur, et le type écrit à côté n'est qu'une supposition sur ce que dira le détecteur.

**BR-LIST-04.** Quand les deux listes visent le même passage, alors le réglage de conflit décide.

Le tableau suivant donne le résultat de chaque réglage :

| Réglage | Résultat sur « Acme » présent dans les deux listes |
|---|---|
| La liste à masquer gagne (par défaut) | masqué : `<<ORG:1>>` |
| La liste à laisser en clair gagne | en clair : `Acme` |
| Refuser | arrêt avec `Overrides contradict each other on 'Acme': a span on the deny list overlaps one on the allow list.` |

Ce défaut vient d'un principe simple. En cas de doute, masquer protège.

**BR-LIST-05.** Quand l'assistant cite le premier une valeur de la liste à masquer, alors elle reste en clair par défaut. Un réglage « forcer » la masque quand même. La raison est que masquer une valeur que le modèle a lui-même apportée lui retire une connaissance utile. Le masquage lui signale aussi que cette valeur précise est sensible.

**BR-LIST-06.** Quand une personne corrige à la main les valeurs d'un message, alors les deux listes s'appliquent encore à sa correction et l'emportent sur elle. Par exemple, l'utilisateur retire « PRJ-0042 » des valeurs masquées de son message, mais le numéro reste masqué.

**BR-LIST-07.** Quand le contrôle final relit le texte protégé, alors il ignore les valeurs de la liste à laisser en clair. Toute autre valeur restée en clair bloque l'envoi.

**BR-LIST-08.** Quand une liste change pendant une conversation, alors un message déjà analysé garde son ancien résultat, même renvoyé à l'identique. Par exemple, le 2 octobre 2026, « Acme » entre dans la liste à masquer. Le message envoyé le 1er octobre 2026 dans la même conversation reste avec « Acme » en clair. Seuls les nouveaux messages appliquent la liste.

### Ce que voit l'utilisateur final

Rien de différent. La réponse restaurée contient les vraies valeurs. Seul le modèle voit la différence entre une valeur masquée et une valeur gardée en clair.

### Questions fréquentes

**Le nom de l'entreprise est encore masqué alors qu'il est dans la liste à laisser en clair.** Trois causes possibles. La valeur figure aussi dans la liste à masquer (BR-LIST-04). Ou le texte détecté est plus long que la valeur listée, avec le réglage « Même valeur » (BR-LIST-03). Ou le message avait été analysé avant l'ajout à la liste (BR-LIST-08).

**Un nom de code de la liste à masquer reste en clair.** L'assistant l'a probablement cité le premier dans la conversation (BR-LIST-05). Demandez le réglage « forcer » si la valeur doit toujours être masquée.

**Le traitement s'arrête avec `Overrides contradict each other on …`.** Le réglage de conflit est « Refuser » et une valeur figure dans les deux listes. Retirez-la de l'une des deux.

## Pour les développeurs

Le guide technique montre les deux listes à l'œuvre dans [Comment forcer une détection ou laisser une valeur en clair](../../../docs/fr/examples/overrides.md).

### Où vivent les règles

| Règle | Emplacement |
|---|---|
| BR-LIST-01, BR-LIST-03 | `src/piighost/components/override/detector.py:16-42`, `_clear` lignes 145-154 |
| BR-LIST-02 | `detector.py:126-143` (`_force`) |
| BR-LIST-04 | `detector.py:88-108` (`apply`), `_refuse_collisions` lignes 156-166 |
| BR-LIST-05 | `detector.py:117-124` (`forces_value`), `pipeline/thread.py:322-329` |
| BR-LIST-06 | `pipeline/thread.py:210` (`anonymize_corrected`) |
| BR-LIST-07 | `pipeline/base.py:225-234` (`_cleared_values`), `pipeline/base.py:313-341` (`_guard`) |
| BR-LIST-08 | `pipeline/thread.py:271-287` (`_detect` ne réapplique rien sur un message en cache) |
| Stratégies et défauts | `components/override/strategy.py`, `config/models/override.py:52-58` |
| Refus des noms de la 1.x (DEC-09) | `config/models/override.py:14-32`, `_refuse_renamed_keys` et `_refuse_renamed_conflict_values` lignes 60-90 |
| Liste à masquer et liste à laisser en clair dans le serveur | `piighost-api` lit la même section `[override]` de sa configuration |

Composants liés : `AnyDetectionOverride` (port, sans gabarit), `DetectionOverride` (implémentation pilotée par deux détecteurs), `AllowListStrategy`, `DenyListStrategy`, `OverrideConflictStrategy`, `ConflictingOverrideError`.

Position dans le pipeline : juste après la détection, avant les chevauchements et l'expansion (`pipeline/base.py:364-371`). Dans le pipeline de conversation, avant chaque écriture en mémoire (`pipeline/thread.py:276-286`).

### Configurer les listes

1. Partez de la section `[override]` documentée dans `docs/en/configuration/toml.md`.
2. Écrivez chaque liste comme un détecteur complet, souvent `type = "exact"` ou `type = "regex"` :

```toml
[override]
allow_list_strategy = "value"
conflict_strategy = "deny_list_wins"

[override.deny_list]
type = "regex"
patterns = { CODE = 'PRJ-[0-9]{4}' }

[override.allow_list]
type = "exact"
values = { Acme = "ORG" }
```

3. Pour masquer aussi les valeurs citées d'abord par l'assistant, ajoutez `deny_list_strategy = "force"`.
4. Ne reprenez pas telle quelle une configuration 1.x. Ses clés `whitelist` et `blacklist` sont refusées au chargement, avec le nom qui les remplace (DEC-09).

#### Vérifier

```bash
uv run pytest tests/components/override tests/config/test_guard_override_models.py
```

Puis lancez `piighost anonymize --config <votre fichier> "Claire Dubois travaille chez Acme sur PRJ-0042."`. Vous devez voir « Acme » en clair et `<<CODE:1>>` à la place du code.

### Pièges

- **Les listes sont des détecteurs complets.** Une liste regex lourde ou un détecteur à modèle relance un calcul à chaque message, et une seconde fois pour le contrôle final (`cleared_values`).
- **`forces_value` relance la liste à masquer sur chaque valeur d'entité** introduite par l'assistant, sous `FORCE`.
- **Une détection en cache n'est pas repassée dans les listes** (BR-LIST-08). Pour appliquer une nouvelle liste à une conversation en cours, effacez la conversation (`forget_thread`) ou corrigez le message par `anonymize_corrected`.
- **`ExactMatchDetector` est d'abord un outil de test.** Utilisé comme liste à masquer dans `DetectionOverride`, il survit aux corrections humaines. Utilisé seul comme détecteur principal, il n'y survit pas.

### Tests

| Test | Couvre |
|---|---|
| `tests/components/override/test_override.py` | Les trois stratégies de liste à laisser en clair, l'ordre selon le réglage de conflit, le refus, `forces_value` |
| `tests/config/test_guard_override_models.py` | Le modèle de configuration `[override]`, et le refus des clés et des valeurs de la 1.x |
| `tests/config/test_settings.py` | `test_deny_list_forces_a_detection` |
| `tests/pipeline/test_override_integration.py` | Les listes l'emportent sur une correction humaine (AT-USER-6-3), liste à masquer et liste à laisser en clair de bout en bout (AT-DPO-3-1, AT-DPO-3-2) |
