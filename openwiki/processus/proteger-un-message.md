---
type: workflow
title: Protéger un message avant l'envoi au modèle
description: Les étapes qu'un texte traverse dans PIIGhost avant d'atteindre un modèle (repérage, liste blanche et liste noire, chevauchements, occurrences manquées, regroupement, remplacement par jeton, contrôle final), les règles de chacune et leur emplacement dans le code.
tags: [pipeline, detection, overlap, expander, linker, anonymizer, guard, placeholder]
sources:
  - id: openwiki-source-fb8df46c8512226bd88d01a2
    resource: repo://src/piighost/components/anonymizer/base.py
  - id: openwiki-source-8139bad008851a4fdde3893e
    resource: repo://src/piighost/components/anonymizer/span.py
  - id: openwiki-source-88cbb51a86bd375e7313028b
    resource: repo://src/piighost/components/detector/regex.py
  - id: openwiki-source-d9cd7261173eb27a74d01911
    resource: repo://src/piighost/components/expander/base.py
  - id: openwiki-source-f60a3f52d1991a7fff78b451
    resource: repo://src/piighost/components/expander/word_boundary.py
  - id: openwiki-source-c4c3433e4ac3ce8dcbc19382
    resource: repo://src/piighost/components/guard/base.py
  - id: openwiki-source-aa685735384e8973ddee846d
    resource: repo://src/piighost/components/linker/exact.py
  - id: openwiki-source-403bd9c899325c51a9edae95
    resource: repo://src/piighost/components/overlap_resolver/base.py
  - id: openwiki-source-4d78db3f83c84e2c66a1f3a0
    resource: repo://src/piighost/components/overlap_resolver/confidence.py
  - id: openwiki-source-5edc3a966c24311549f53a92
    resource: repo://src/piighost/components/overlap_resolver/merge.py
  - id: openwiki-source-5ddce4dd4539293afb49cdfd
    resource: repo://src/piighost/pipeline/base.py
  - id: openwiki-source-a667a8b4336071b724160a9a
    resource: repo://src/piighost/text/boundaries.py
  - id: openwiki-source-5d73d23fe59a4693c4e58d4a
    resource: repo://src/piighost/text/normalization.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---
# Protéger un message avant l'envoi au modèle

## En bref

- Avant d'envoyer un texte au modèle, PIIGhost y repère les valeurs sensibles et les remplace par des jetons comme `<<PERSON:1>>`.
- Une même valeur reçoit un seul jeton dans tout le texte, même écrite avec une autre casse ou d'autres espaces.
- La réponse du modèle est ensuite restaurée : chaque jeton redevient la vraie valeur.
- Une valeur que le détecteur ne voit pas part en clair, sauf si un contrôle final est activé : il bloque alors l'envoi.
- Les motifs ne vérifient pas les clés de contrôle (carte, IBAN). Une valeur mal recopiée reste masquée.

Besoins couverts : DPO-1, DPO-2, DPO-4 et DEV-1, décrits dans [Besoins par profil](../besoins-par-profil.md). Les termes sont définis dans le [glossaire](../glossaire.md). Pour une conversation en plusieurs messages, lisez ensuite [Suivre une conversation et restaurer la réponse](suivre-une-conversation.md).

## Pour le métier

PIIGhost n'a pas d'écran. Ce que vous pouvez constater, c'est le texte reçu par le modèle et la réponse rendue à l'utilisateur. Pour essayer sur une phrase, l'équipe technique lance `piighost anonymize "votre phrase"`.

### Qui intervient

| Acteur | Rôle |
|---|---|
| L'utilisateur final | écrit son message en clair |
| L'application | reçoit le message et le fait passer par PIIGhost avant d'appeler le modèle |
| PIIGhost | repère les valeurs, les remplace par des jetons, garde la correspondance |
| Le modèle | reçoit le texte protégé, et seulement lui |

Avant tout envoi, au moins un détecteur doit être configuré. PIIGhost n'embarque aucun motif : les types protégés sont ceux des détecteurs et des groupes de motifs que la configuration charge.

### Le trajet d'un message

```mermaid
flowchart TD
    A["Texte de l'utilisateur"] --> B["Repérage des valeurs sensibles"]
    B --> C["Liste blanche et liste noire"]
    C --> D["Arbitrage des chevauchements"]
    D --> E["Recherche des occurrences oubliées"]
    E --> F["Regroupement d'une même valeur"]
    F --> G["Remplacement par des jetons"]
    G --> H["Contrôle final"]
    H --> I["Texte envoyé au modèle"]
```

Exemple suivi d'un bout à l'autre : l'utilisateur écrit « Écrivez à Jean Dupont, jean.dupont@exemple.fr ».

1. **Repérage.** Un ou plusieurs détecteurs cherchent les valeurs : par forme (e-mail, téléphone), par modèle d'IA (noms, lieux) ou par grand modèle de langage. Ici, « Jean Dupont » est repéré comme personne et « jean.dupont@exemple.fr » comme e-mail.
2. **Liste blanche et liste noire.** Les valeurs à toujours masquer ou à ne jamais masquer, écrites dans la configuration, sont appliquées. Voir [Imposer une liste blanche et une liste noire](imposer-une-liste-blanche-et-noire.md).
3. **Chevauchements.** Quand deux repérages se recouvrent, un seul passage est gardé. Ici, rien ne se recouvre.
4. **Occurrences oubliées** (étape facultative). Chaque valeur trouvée est recherchée ailleurs dans le texte.
5. **Regroupement.** Les occurrences d'une même valeur et d'un même type forment un seul groupe.
6. **Remplacement.** Chaque groupe reçoit un jeton : « Jean Dupont » devient `<<PERSON:1>>`, l'adresse devient `<<EMAIL:1>>`.
7. **Contrôle final** (facultatif). Le texte protégé est relu pour y chercher un reste de valeur sensible.

Le modèle reçoit « Écrivez à `<<PERSON:1>>`, `<<EMAIL:1>>` ». PIIGhost garde la correspondance entre chaque jeton et sa valeur, pour restaurer la réponse.

**Comment vérifier** : faites protéger la phrase d'exemple par l'équipe technique. La sortie ne doit contenir ni « Jean Dupont » ni l'adresse.

### Règles à connaître

**BR-MSG-01.** Quand une valeur est repérée, alors elle reçoit un jeton qui nomme son type et un numéro, compté par type dans l'ordre d'apparition. Exemple : « Jean Dupont écrit à Marie Curie » devient « `<<PERSON:1>>` écrit à `<<PERSON:2>>` ».

**BR-MSG-02.** Quand une valeur revient sous une autre casse ou avec d'autres espaces, alors elle reçoit le même jeton. Exemple : « Patrick a appelé. Rappelez patrick demain. » devient « `<<PERSON:1>>` a appelé. Rappelez `<<PERSON:1>>` demain. »

**BR-MSG-03.** Quand une valeur a plusieurs graphies, alors la restauration remet partout la première graphie rencontrée. Dans l'exemple précédent, la réponse restaurée affiche « Patrick » aux deux endroits.

**BR-MSG-04.** Quand un nom est collé à un autre par un trait d'union, alors il n'est pas reconnu comme le même mot. Exemple : « Patrick » repéré ne masque pas « Jean-Patrick ». Pourquoi : un prénom court ne doit pas être relié à un prénom composé différent.

**BR-MSG-05.** Quand deux repérages se recouvrent, alors un seul passage est toujours gardé, et le plus sûr gagne (réglage par défaut). Le reste du plus long passage peut alors partir en clair. Un second réglage masque toute la zone couverte :

| Réglage | « Contrat signé par Loni M. Wirth le 12/03/2026. » devient |
|---|---|
| Le plus sûr gagne (par défaut) | Contrat signé par Loni M. `<<NAME:1>>` le 12/03/2026. |
| Union des passages | Contrat signé par `<<NAME:1>>` le 12/03/2026. |

Ici, un motif sûr à 100 % a trouvé « Wirth » et un modèle sûr à 70 % a trouvé « Loni M. Wirth ». À égalité parfaite de confiance et de position, le premier détecteur déclaré gagne. Avec l'union, la zone prend le type du repérage le plus sûr, et à confiance égale celui du plus long.

**BR-MSG-06.** Quand une valeur est écrite avec une espace insécable ou fine, alors un motif écrit avec une espace normale la trouve quand même. Exemple : « 06 12 34 56 78 » tapé dans un traitement de texte, avec des espaces insécables, devient `<<PHONE:1>>`.

**BR-MSG-07.** Quand un motif reconnaît la forme d'une carte ou d'un IBAN, alors la valeur est masquée sans vérifier sa clé de contrôle. Pourquoi : une valeur abîmée par une reconnaissance de caractères aurait une clé fausse, et la rejeter la laisserait partir en clair.

**BR-MSG-08.** Quand un message contient une clé d'API, alors elle n'est masquée que si la configuration charge un groupe de motifs de secrets, comme le groupe `piighost/logs` du hub, ou un modèle qui les cherche. Exemple : avec ce groupe, une clé OpenAI part sous la forme `<<OPENAI_API_KEY:1>>`.

**BR-MSG-09.** Quand l'utilisateur tape lui-même un texte qui a la forme d'un jeton, alors ce texte est neutralisé par un caractère invisible. Exemple : « Claire écrit `<<PERSON:2>>` ici » ne pourra pas se faire passer pour un vrai jeton à la restauration. Pourquoi : sinon, un jeton tapé à la main pourrait récupérer la valeur d'une autre personne.

**BR-MSG-10.** Quand le détecteur ne voit pas une valeur et qu'aucun contrôle final n'est activé, alors la valeur part en clair. Exemple : « Écrivez à `<<PERSON:1>>`, jean.dupont@exemple.fr » si les e-mails ne sont pas reconnus.

**BR-MSG-11.** Quand le contrôle final trouve une valeur sensible dans le texte protégé, alors l'envoi est bloqué avec `Anonymized text still contains PII: ['EMAIL']`. Le message nomme les types restants, jamais les valeurs.

**BR-MSG-12.** Quand la recherche des occurrences oubliées est active, alors elle ignore la casse. Elle trouve « patrick » après « Patrick », au prix de faux positifs sur des mots courants.

### Ce que voit l'utilisateur final

Rien : il écrit en clair et lit une réponse en clair. Seul le modèle voit les jetons. Si le contrôle final bloque un message, l'application reçoit une erreur. Le message affiché à l'utilisateur dépend alors de l'application.

### Questions fréquentes

**Une adresse e-mail est partie en clair.** Le détecteur ne connaît pas ce type et aucun contrôle final n'est activé (BR-MSG-10). Faites ajouter le type au détecteur, ou activez un contrôle final qui le reconnaît.

**Une partie d'un nom est partie en clair (« Loni M. »).** Deux repérages se chevauchaient, et le plus sûr ne couvrait qu'une partie du nom (BR-MSG-05). Demandez le réglage « Union des passages ».

**Le nom de l'entreprise est remplacé par `<<PERSON:2>>`.** Le détecteur le prend pour une personne, et le modèle perd une information utile. Faites-le mettre dans la liste noire, voir [Imposer une liste blanche et une liste noire](imposer-une-liste-blanche-et-noire.md).

**Un numéro de carte faux a été masqué.** C'est voulu : aucune clé de contrôle n'est vérifiée (BR-MSG-07).

**Une clé d'API est partie en clair.** Aucun groupe de motifs de secrets n'est chargé (BR-MSG-08). Faites ajouter le groupe `piighost/logs` à la configuration.

**« Jean-Patrick » est resté en clair alors que « Patrick » est masqué.** Le trait d'union lie les deux prénoms (BR-MSG-04). Il faut que le détecteur repère « Jean-Patrick » lui-même.

**Le traitement s'arrête avec `Anonymized text still contains PII`.** Le contrôle final a trouvé un reste (BR-MSG-11). Faites ajouter le type manquant au détecteur principal.

## Pour les développeurs

### Où vivent les règles

| Règle | Emplacement |
|---|---|
| Ordre des étapes | `src/piighost/pipeline/base.py:352-393` (`AnonymizationPipeline.anonymize`), liste blanche et liste noire ligne 365 |
| BR-MSG-01 | `components/placeholder/label_counter.py`, défaut `pipeline/base.py:172` |
| BR-MSG-02 | `components/linker/exact.py:8-21`, `text/normalization.py:61-71` (`value_key`) |
| BR-MSG-03 | `components/anonymizer/base.py:151` (`deanonymize` remplace par `entity.text`), `models/entity.py` |
| BR-MSG-04 | `text/boundaries.py:38` (`WORD_JOIN_CHARS`) |
| BR-MSG-05 | `components/overlap_resolver/confidence.py:10-21`, `merge.py:7-15` (`_surest`), `overlap_resolver/base.py` (`by_confidence`, `_conflict_groups`) |
| BR-MSG-06 | `text/normalization.py:45-58`, `components/detector/regex.py:65-79` |
| BR-MSG-07 | `components/detector/regex.py:10-30` |
| BR-MSG-08 | `components/detector/regex.py:33-56` (`from_hub`), `config/models/detector.py` (`catalogs`) |
| BR-MSG-09 | `components/anonymizer/span.py:26-40`, `_neutralize` ligne 79 |
| BR-MSG-10, BR-MSG-11 | `pipeline/base.py:313-341` (`_guard`) |
| BR-MSG-12 | `components/expander/word_boundary.py:11-31` |

Valeurs par défaut quand seul le détecteur est fourni : `ExactEntityLinker`, `Anonymizer(LabelCounterPlaceholderFactory())`, `ConfidenceOverlapResolver` (`pipeline/base.py:168-182`). L'expansion, la résolution d'entités, la liste blanche et la liste noire (`override`) et le contrôle final (`guard`) sont désactivés.

```python
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector(
    {"Jean Dupont": "PERSON", "jean.dupont@exemple.fr": "EMAIL"}
)
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("Écrivez à Jean Dupont, jean.dupont@exemple.fr")
    print(result.text)  # Écrivez à <<PERSON:1>>, <<EMAIL:1>>


asyncio.run(main())
```

### Modifier une étape

1. Choisissez le port de l'étape (voir [Ajouter ou remplacer un composant](../architecture/ports-et-extension.md)).
2. Passez votre composant au constructeur : `AnonymizationPipeline(detector, overlap_resolver=MergeOverlapResolver())`, ou en configuration `[overlap_resolver] type = "merge"`.
3. Pour le contrôle final, passez `guard=DetectorGuardRail(un_détecteur)`.

#### Vérifier

```bash
uv run pytest tests/pipeline/test_pipeline.py tests/components tests/acceptance/test_dpo.py
```

Puis `echo "Tél. 06 12 34 56 78" | uv run piighost anonymize --config <fichier>` doit renvoyer un jeton à la place du numéro.

### Pièges

- **Le résolveur de chevauchements ne se désactive pas.** `overlap_resolver=None` installe `ConfidenceOverlapResolver`. `Anonymizer.render` lève `OverlappingSpansError` s'il reste un chevauchement.
- **L'expansion tourne après le résolveur.** Elle saute toute occurrence qui touche un caractère déjà couvert, et cherche les valeurs les plus longues d'abord (`expander/base.py:30-75`).
- **Le caractère de neutralisation reste dans le texte restauré.** Un jeton tapé par l'utilisateur revient avec un U+200B invisible après son premier caractère. Un traitement en aval qui compare des chaînes exactes peut échouer. `Anonymizer(factory, escape_existing_tokens=False)` désactive la neutralisation, au prix de BR-MSG-09.
- **`RegexDetector` compile sous `re.ASCII`.** `\d` ne prend que 0 à 9, et `\w` s'arrête au premier caractère accentué.
- **Un détecteur seul peut rendre des détections qui se chevauchent.** Le port l'autorise. Ne testez jamais un détecteur en sortant de la chaîne avant le résolveur.
- **Un garde-fou à score (modération) ne localise rien.** Les valeurs de la liste noire ne peuvent pas en être exemptées (`pipeline/base.py:318-322`).
- **`LLMDetector` échoue fermé.** Une sortie du modèle illisible, sans champ `entities` ou que le parseur rejette, lève `UnreadableOutputError` et le message est refusé (`components/detector/llm.py:174-181`, `_unreadable` en `:203`). `fail_open=True` la lit comme zéro détection, et le message part alors sans protection. Voir DPO-9 dans [Besoins par profil](../besoins-par-profil.md#points-de-vigilance).

### Écarts doc / code

Aucun écart constaté sur cette page. L'ordre des étapes de `docs/en/architecture.md` correspond au code.

### Tests

| Test | Couvre |
|---|---|
| `tests/pipeline/test_pipeline.py` | Ordre des étapes, valeurs par défaut, contrôle final |
| `tests/components/overlap_resolver/` | Les deux résolveurs, l'égalité gagnée par le premier détecteur, l'union nommée d'après le plus large |
| `tests/components/expander/test_word_boundary.py` | Recherche des occurrences, pas de chevauchement ajouté |
| `tests/components/anonymizer/test_span_anonymizer.py` | Remplacement, neutralisation des jetons tapés, refus d'un chevauchement |
| `tests/text/` | Limites de mots, normalisation des espaces |
| `tests/components/detector/test_contract.py` | Même sortie pour tous les détecteurs |
| `tests/acceptance/test_dpo.py` | AT-DPO-1-2 (une clé d'API part en jeton), AT-DPO-2-2 (un groupe retiré laisse ses valeurs en clair) |

Non couvert : la présence du U+200B dans le texte restauré n'est pas présentée comme un comportement attendu dans les tests. Ce point a été constaté en lançant le pipeline.
