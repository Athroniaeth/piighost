---
title: Architecture & Flux d'anonymisation
---

# Architecture & Flux d'anonymisation

Cette page décrit en détail le pipeline d'anonymisation d'Aegra — comment les entités sont détectées, couvertes, remplacées et restituées sans biaiser les offsets de caractères.

---

## Diagramme 1 — Vue globale du flux conversation

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant A as Anonymizer
    participant NER as GLiNER2 (NER)
    participant LLM as Modèle LLM
    participant Tool as Outil (ex: get_weather)

    U->>A: "Donne moi la météo de Lyon"
    A->>NER: Détection entités PII
    NER-->>A: "Lyon" → LOCATION (conf: 0.92)
    A->>A: expand_placeholders → couvre toutes les occurrences
    A->>A: Assigne <LOCATION_1>, remplace en ordre inverse
    A->>LLM: "Donne moi la météo de <LOCATION_1>"

    LLM->>A: call get_weather(<LOCATION_1>)
    A->>A: deanonymize args → "Lyon"
    A->>Tool: call get_weather("Lyon")
    Tool-->>A: "Weather in Lyon: 22°C sunny"
    A-->>LLM: ToolMessage (sera ré-anonymisé au prochain tour)

    LLM->>A: "Pour <LOCATION_1>, il fait 22°C"
    A->>A: deanonymize réponse finale
    A->>U: "Pour Lyon, il fait 22°C"
```

---

## Diagramme 2 — Pipeline Anonymizer (bas niveau)

```mermaid
flowchart TD
    A[Texte brut] --> B[detect_entities via GLiNER2]
    B --> C{confidence >= min_confidence ?}
    C -- Non --> D[Ignoré]
    C -- Oui --> E[assign_placeholders]
    E --> F{Texte déjà dans\nthread_store ?}
    F -- Oui --> G[Réutilise placeholder existant]
    F -- Non --> H[Crée nouveau placeholder\nindex = max existant + 1]
    G & H --> I[expand_placeholders\nre.finditer — exact match sur le texte original\nAjoute toutes les occurrences manquantes]
    I --> J[replace_with_placeholders\ntri greedy + remplacement en ordre inverse]
    J --> K[Texte anonymisé]
    K --> L[compute_anonymized_spans\nre-scan du texte anonymisé final]
    L --> M[Mise à jour thread_store]
```

!!! note "Point d'extension — aliases"
    Le diagramme ci-dessus montre le comportement par défaut : `expand_placeholders` effectue un match exact sur la surface textuelle. Pour couvrir des variantes (`"Pari"` → même placeholder que `"Paris"`), il faudrait construire un pattern OR à partir d'un dictionnaire d'aliases (plus long en premier pour éviter la capture partielle). Ce mécanisme n'est pas intégré nativement — voir la section [Variantes et aliases](#variantes-et-aliases) pour le détail.

---

## Mécanismes de robustesse

### Occurrences manquantes — `expand_placeholders`

GLiNER2 ne détecte souvent que la **première occurrence** d'une entité dans un texte.
`expand_placeholders` compense cela en balayant le texte original via `re.finditer` pour trouver toutes les occurrences supplémentaires.

```
Texte   : "Pierre habite à Lyon. Pierre travaille à Lyon."
GLiNER  : "Pierre" @0  "Lyon" @16               ← première occurrence seulement
expand  : "Pierre" @0 @22   "Lyon" @16 @38       ← toutes les occurrences
```

Le matching est **exact** (`re.escape`). Les spans déjà connus (détectés par GLiNER) sont dédupliqués avant l'ajout. Les nouvelles occurrences reçoivent `confidence=1.0`.

---

### Variantes et aliases

Par défaut, `expand_placeholders` ne matche que la surface textuelle exacte.
Pour couvrir des variantes (`"Pari"` → `<LOCATION_1>` comme `"Paris"`), il faut construire un pattern qui couvre **toutes les formes** d'une même entité.

Le principe : construire un `pattern OR` à partir d'un dictionnaire d'aliases, avec le plus long en premier pour éviter qu'une forme courte avale une forme longue :

```python
aliases = {"Pari": "Paris", "Tim": "Tim Cook"}

# Pour l'entité dont la surface canonique est "Paris" :
surfaces = {"Paris"} | {k for k, v in aliases.items() if v == "Paris"}
# → {"Paris", "Pari"}

pattern = "|".join(re.escape(s) for s in sorted(surfaces, key=len, reverse=True))
# → "Paris|Pari"  (plus long en premier)
```

Chaque match crée un `NamedEntity` avec son texte **brut** (pas la forme canonique),
ce qui permet à `deanonymize` de restituer la vraie surface d'origine :

```
"Pari est belle"  →  <LOCATION_1> est belle
deanonymize       →  "Pari est belle"   ← surface brute préservée
```

!!! warning
    Ce mécanisme n'est pas intégré nativement dans `expand_placeholders` — il s'agit d'un point d'extension. Un dictionnaire d'aliases doit être fourni explicitement et appliqué lors de la construction du pattern regex.

---

### Cohérence des offsets — remplacement en ordre inverse

Quand plusieurs entités sont remplacées dans un même texte, chaque remplacement change la longueur du texte et décale les offsets des entités qui suivent. Par exemple :

```
Texte original : "Pierre habite à Lyon, Lyon est belle"
                  0123456789...        16  20 22  26
```

Si on remplace dans l'ordre naturel (gauche → droite) :

```
① "Pierre" (0–6) → <PERSON_1> (10 chars, +4)
   → les offsets de "Lyon" @16 et @22 sont maintenant @20 et @26 — invalides
```

La solution est de trier les remplacements par **position décroissante** et de les appliquer de droite à gauche :

```mermaid
sequenceDiagram
    participant T as Texte (mutable)
    participant R as Remplacements triés desc

    R->>T: ① offset 22→26 : "Lyon" → <LOCATION_1>
    Note over T: "Pierre habite à Lyon, <LOCATION_1> est belle"
    R->>T: ② offset 16→20 : "Lyon" → <LOCATION_1>
    Note over T: "Pierre habite à <LOCATION_1>, <LOCATION_1> est belle"
    R->>T: ③ offset 0→6 : "Pierre" → <PERSON_1>
    Note over T: "<PERSON_1> habite à <LOCATION_1>, <LOCATION_1> est belle"
```

Chaque remplacement ne modifie que le texte **à sa droite** — or les remplacements restants à traiter sont à des offsets **plus petits**, donc non affectés. Les offsets de `NamedEntity.start/end` restent valides jusqu'à leur tour.

#### Biais des offsets avec N placeholders

| Étape | Remplacement | Décalage introduit | Offsets suivants affectés ? |
|-------|-------------|-------------------|-----------------------------|
| ① droite→gauche | `"Lyon"` @38→42 → `<LOCATION_1>` (+8) | +8 | aucun (rien à droite) |
| ② | `"Lyon"` @16→20 → `<LOCATION_1>` (+8) | +8 | aucun (positions 0–15 inchangées) |
| ③ | `"Pierre"` @0→6 → `<PERSON_1>` (+4) | +4 | aucun (c'est le dernier) |

Conclusion : chaque remplacement de droite à gauche ne perturbe que les offsets à sa gauche — or on a déjà traité tout ce qui était à droite.

---

### `compute_anonymized_spans` — pourquoi après coup

Les offsets `anon_start/anon_end` (position du placeholder dans le texte **anonymisé**) ne peuvent pas être calculés à l'avance : ils dépendent du nombre et de la taille de tous les remplacements précédents. La solution est de re-scanner le texte anonymisé final via `re.finditer` une fois tous les remplacements effectués.

L'association occurrence ↔ entité repose sur l'ordre d'apparition : les occurrences de `re.finditer` sont en ordre gauche-droite, et les entités dans `placeholders[placeholder]` sont aussi dans cet ordre (GLiNER d'abord, puis `expand_placeholders` en ordre croissant). Le zip est donc stable.

---

## Diagramme 3 — Cohérence multi-tours (thread memory)

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant A as Anonymizer
    participant TS as Thread Store

    U->>A: Tour 1: "Je m'appelle Pierre"
    A->>TS: Lecture vocab (vide)
    A->>A: GLiNER détecte "Pierre" → <PERSON_1>
    A->>TS: Écriture {"Pierre": <PERSON_1>}

    U->>A: Tour 2: "Pierre est-il présent ?"
    A->>TS: Lecture vocab {"Pierre": <PERSON_1>}
    A->>A: "Pierre" → <PERSON_1> (réutilisé, sans appel GLiNER)
    Note over A: Même placeholder garanti<br/>sur toute la conversation

    U->>A: Tour 3: "Rappelle-moi le nom de cet utilisateur"
    A->>TS: Lecture vocab {"Pierre": <PERSON_1>}
    A->>A: Aucune nouvelle entité détectée
    Note over A: thread_store inchangé
```

### Pourquoi c'est nécessaire

Sans persistance du vocabulaire entre les tours :

- Tour 1 : `"Pierre"` → `<PERSON_1>` — assigné
- Tour 3 : GLiNER détecte `"Pierre"` à nouveau, `existing_vocab` est vide → `<PERSON_1>` serait réassigné par chance si aucune autre entité n'a été vue, ou `<PERSON_2>` si le slot 1 est occupé

Le `thread_store` (dict `{surface → Placeholder}` indexé par `thread_id`) garantit l'unicité et la stabilité des jetons pour toute la durée d'une conversation.

---

## Format des jetons

```
<TYPE_N>
```

- `TYPE` : label de l'entité en majuscules (`PERSON`, `LOCATION`, `COMPANY`, `PRODUCT`)
- `N` : index 1-based dans ce type, incrémenté par `assign_placeholders`

```
"Tim Cook"   → <PERSON_1>
"Steve Jobs" → <PERSON_2>
"Apple"      → <COMPANY_1>
"Cupertino"  → <LOCATION_1>
```

Un même texte reçoit toujours le même index au sein d'un thread — c'est `assign_placeholders` + `thread_store` qui le garantissent.
