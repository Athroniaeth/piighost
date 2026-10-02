---
icon: lucide/list-checks
---

# Imposer les listes du serveur

Le serveur impose deux listes au-dessus du détecteur. La liste blanche nomme des valeurs toujours dé-identifiées, même quand le détecteur les rate. La liste noire nomme des valeurs jamais dé-identifiées, même quand le détecteur les relève. Ces deux listes priment sur le détecteur comme sur une correction faite par une personne.

Répond à : DPO-3, UTI-5, DPO-4, DPO-1

## Acteurs

- Le DPO, qui décide des valeurs à toujours ou à ne jamais dé-identifier
- L'équipe technique, qui écrit les listes dans la configuration du serveur
- L'utilisateur final, qui écrit son message en clair
- `piighost`, qui applique les listes à chaque message
- Le LLM, qui reçoit le texte dé-identifié

## Préconditions

- Les listes sont configurées côté serveur, dans le code ou dans la section `[override]` du fichier de configuration.
- La liste blanche contient le motif "PRJ- suivi de quatre chiffres", avec le type `PROJET`.
- La liste noire contient `Acme`{ .pii }, le nom de l'entreprise.
- Le détecteur principal relève les noms et les adresses e-mail, lit `Acme`{ .pii } comme une personne, et ne connaît pas les numéros de dossier.

## Scénario nominal

1. L'utilisateur écrit:

    ```text
    Écrivez à Jean Dupont, jean.dupont@exemple.fr, chez Acme, dossier PRJ-0042.
    ```

2. Le détecteur relève `Jean Dupont`{ .pii }, `jean.dupont@exemple.fr`{ .pii } et `Acme`{ .pii }. Sans les listes, le texte partirait ainsi:

    ```text
    Écrivez à <<PERSON:1>>, <<EMAIL:1>>, chez <<PERSON:2>>, dossier PRJ-0042.
    ```

3. Juste après la détection, la liste noire retire `Acme`{ .pii } des valeurs à dé-identifier.
4. La liste blanche ajoute `PRJ-0042`{ .pii }, que le détecteur avait raté, avec le type `PROJET`.
5. Le reste du pipeline suit son cours, et le LLM reçoit:

    ```text
    Écrivez à <<PERSON:1>>, <<EMAIL:1>>, chez Acme, dossier <<PROJET:1>>.
    ```

6. Le LLM répond "C'est noté pour `<<PROJET:1>>`{ .placeholder }.", et l'utilisateur lit "C'est noté pour PRJ-0042.".

## Scénarios alternatifs

### A1. La même valeur figure dans les deux listes

`Acme`{ .pii } est aussi dans la liste blanche, avec le type `ORG`. Le réglage de conflit décide.

| Réglage | `Acme` devient |
|---|---|
| La liste blanche gagne (par défaut) | `<<ORG:1>>`{ .placeholder } |
| La liste noire gagne | `Acme`{ .pii }, en clair |
| Refuser | erreur `Overrides contradict each other on 'Acme': a whitelisted span overlaps a blacklisted one.` |

Le défaut dé-identifie la valeur, le choix le plus prudent en cas de doute. Avec "Refuser", aucun texte ne part tant que la valeur reste dans les deux listes.

### A2. La valeur de la liste noire apparaît dans un nom plus long

La liste noire contient `Acme`{ .pii } et `Globex`{ .pii }. Le détecteur lit `Acme`{ .pii } comme une personne et `Globex SA`{ .pii } comme une organisation. Sur "Jean Dupont travaille chez Acme, puis chez Globex SA.", le mode de la liste noire décide de ce qui reste en clair.

| Mode | Retire | Résultat |
|---|---|---|
| Même valeur (par défaut) | toute détection du même texte, quels que soient sa position et son type | "`<<PERSON:1>>`{ .placeholder } travaille chez Acme, puis chez `<<ORG:1>>`{ .placeholder }." |
| Exact | une détection de même position et de même type | "`<<PERSON:1>>`{ .placeholder } travaille chez `<<PERSON:2>>`{ .placeholder }, puis chez `<<ORG:1>>`{ .placeholder }." |
| Recouvrement | toute détection qui touche la valeur, même plus longue | "`<<PERSON:1>>`{ .placeholder } travaille chez Acme, puis chez Globex SA." |

### A3. L'assistant cite le premier une valeur de la liste blanche

Le LLM écrit "Votre dossier est le PRJ-0042.", puis l'utilisateur écrit "Merci pour le PRJ-0042.". Par défaut, `PRJ-0042`{ .pii } reste en clair dans les deux messages, car le LLM l'a apporté lui-même. Avec le réglage "forcer", les deux messages portent `<<PROJET:1>>`{ .placeholder }.

### A4. Un relecteur remet une valeur de la liste noire

Un relecteur corrige les détections de "Jean Dupont travaille chez Acme." et y ajoute `Acme`{ .pii }. La liste noire s'applique aussi à la correction, et le message part encore sous la forme "`<<PERSON:1>>`{ .placeholder } travaille chez Acme.".

### A5. Une liste change pendant une conversation

Les deux listes sont mises en place alors que la conversation contient déjà le message du scénario, analysé sans elles. Ce message, renvoyé à l'identique, garde son ancien résultat, "chez `<<PERSON:2>>`{ .placeholder }, dossier PRJ-0042". Un message nouveau, "Relancez Acme sur PRJ-0042.", applique les listes et part sous la forme "Relancez Acme sur `<<PROJET:1>>`{ .placeholder }.". Pour appliquer les nouvelles listes aux anciens messages, effacez la conversation ou corrigez le message.

### A6. Un garde-fou relit le texte

Un garde-fou qui reconnaît `Acme`{ .pii } relit "chez Acme" et ne bloque pas le texte, car les valeurs de la liste noire sont exemptées. Toute autre valeur restée en clair bloque l'envoi. Un garde-fou à score, comme la modération, ne localise rien et ne peut pas exempter ces valeurs.

## Règles

| Règle | Énoncé |
|---|---|
| RG-LISTE-01 | Une valeur de la liste noire est retirée des détections et part au LLM en clair. |
| RG-LISTE-02 | Une valeur de la liste blanche est dé-identifiée même si le détecteur l'a ratée, avec le type que lui donne la liste. |
| RG-LISTE-03 | Une détection de la liste blanche remplace toute détection du détecteur qu'elle recouvre. |
| RG-LISTE-04 | Par défaut, la liste noire retire toute détection du même texte, quels que soient sa casse, ses espaces, sa position et son type. |
| RG-LISTE-05 | Le mode "exact" ne retire qu'une détection de même position et de même type, le mode "recouvrement" retire toute détection qui touche la valeur. |
| RG-LISTE-06 | Quand les deux listes visent le même passage, la liste blanche gagne par défaut, et deux autres réglages font gagner la liste noire ou refusent le texte. |
| RG-LISTE-07 | Les listes s'appliquent juste après la détection, avant le départage des recouvrements, et dans une conversation avant l'enregistrement en mémoire. |
| RG-LISTE-08 | Les listes s'appliquent aussi à une correction humaine et priment sur elle. |
| RG-LISTE-09 | Un garde-fou qui localise les valeurs ignore celles de la liste noire, un garde-fou à score ne peut pas les exempter. |
| RG-LISTE-10 | Une valeur de la liste blanche citée d'abord par l'assistant reste en clair, sauf avec le réglage "forcer". |
| RG-LISTE-11 | Un message déjà analysé dans une conversation garde son résultat, même renvoyé à l'identique après un changement de liste. |
| RG-LISTE-12 | Chaque liste est un détecteur complet, valeurs exactes ou motifs regex par exemple, relancé sur chaque message. |

## Postconditions

- Le LLM a reçu "chez Acme" en clair et `<<PROJET:1>>`{ .placeholder } à la place du numéro de dossier.
- La correspondance de `<<PROJET:1>>`{ .placeholder } est gardée comme celle de toute autre valeur, et la réponse est restaurée.
- La politique du DPO s'applique à chaque message, quoi que relève le détecteur, et l'utilisateur lit une réponse où le nom de l'entreprise garde son sens.

## Pour le développeur

Les listes forment l'étape `override`, une `DetectionOverride` passée au pipeline (`override=...`). Chaque liste est un détecteur, souvent un `ExactMatchDetector` ou un `RegexDetector`.

| Réglage de la page | Paramètre | Valeurs |
|---|---|---|
| Mode de la liste noire | `blacklist_strategy` | `VALUE` (défaut), `EXACT`, `OVERLAP` |
| Conflit | `conflict_strategy` | `WHITELIST_WINS` (défaut), `BLACKLIST_WINS`, `RAISE` |
| Valeur apportée par l'assistant | `whitelist_strategy` | `RESPECT_PROVENANCE` (défaut), `FORCE` |

Le refus lève `ConflictingOverrideError`. La section `[override]` équivalente, à côté de la section `[detector]` du fichier:

```toml
[override]
blacklist_strategy = "value"
whitelist_strategy = "respect_provenance"
conflict_strategy = "whitelist_wins"

[override.whitelist]
type = "regex"
patterns = { PROJET = "PRJ-[0-9]{4}" }

[override.blacklist]
type = "exact"
values = { "Acme" = "ORG" }
```

- `ThreadAnonymizationPipeline` applique l'`override` aux détections fraîches et dans `anonymize_corrected`, jamais aux détections relues depuis la mémoire (RG-LISTE-11).
- L'exemption du garde-fou passe par `cleared_values`, qui relance la liste noire sur le texte. Le forçage d'une valeur apportée par l'assistant passe par `forces_value`, qui relance la liste blanche sur la valeur.
- Une liste à base de modèle coûte une inférence par message. Quand un garde-fou est configuré, la liste noire tourne une seconde fois sur le texte.

À lire ensuite.

- [Comment forcer une détection ou laisser une valeur en clair](../examples/overrides.md)
- [Référence de configuration](../configuration/toml.md)
- [Référence des garde-fous](../reference/guard-rails.md)
- [Suivre une conversation et restaurer la réponse](follow-a-conversation.md), pour les corrections et l'effacement
