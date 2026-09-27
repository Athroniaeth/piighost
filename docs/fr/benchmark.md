---
icon: lucide/gauge
---

# La détection, mesurée

Combien de valeurs confidentielles un pipeline `piighost` configuré cache, et ce que chaque étape ajoute par rapport à un modèle NER appelé directement. Les chiffres viennent d'un banc d'essai lancé le 2026-09-27 sur cinq jeux de données, en anglais et en français.

!!! note "Un décompte strict"
    Une valeur ne compte comme cachée que si chacun de ses caractères est masqué. Un masquage partiel est une fuite. `Paul <<PERSON:1>>`{ .placeholder } laisse `Paul`{ .pii } en clair, donc compte comme un raté pour `Paul Lemoine`{ .pii }. C'est plus strict que le recouvrement que retiennent les articles sur le NER, et les chiffres sont plus bas pour cette raison.

## La question

Un modèle NER trouve les noms, les lieux et les organisations. `piighost` l'insère dans un pipeline qui ajoute le découpage du texte, des règles regex, la recherche des répétitions et le regroupement des entités. Ce pipeline cache-t-il plus que le modèle seul, et quelle étape fait le travail ?

Pour le savoir, le banc d'essai ajoute une étape à la fois, avec le même modèle sur les mêmes documents.

| Marche | Système |
|---|---|
| A | le modèle appelé directement sur tout le texte, comme le ferait un développeur, coupé à sa fenêtre |
| B | A, avec le découpage de `piighost` |
| C | les règles regex de la config, sans modèle |
| D | B et C ensemble, chevauchements résolus |
| E | D, plus l'expander par mot entier |
| F | E, plus le résolveur d'entités, la config complète |

Deux modèles montent l'échelle. GLiNER2 (`fastino/gliner2-multi-v1`, le modèle de la config `fr-notarial` du hub), et `onnx-community/gliner_multi_pii-v1` en ONNX via `BridgeDetector`, le moteur qui tourne dans le navigateur.

## Les données

| Jeu | Langue | Documents | Ce que c'est | Précaution |
|---|---|---|---|---|
| Actes générés | français | 200 | actes, baux, contrats de travail, e-mails, comptes rendus médicaux, construits sur des modèles avec des valeurs fictives | un texte généré flatte, les valeurs sont là où un emplacement les attend |
| Actes générés longs | français | 12 | les mêmes, de 2 à 60 pages | trois documents par longueur, intervalles larges |
| TAB | anglais | 127 | arrêts de la CEDH annotés pour l'anonymisation (Pilán et al., 2022) | des arrêts publics, qu'un modèle a pu voir à l'entraînement |
| PARHAF | français | 101 | comptes rendus médicaux écrits à la main par des internes pour des patients fictifs | presque aucun identifiant à forme fixe, il teste donc le modèle |
| Gretel finance | français | 443 | documents financiers synthétiques | écrits par un LLM |

Aucun jeu ne contient les données d'une vraie personne privée. Seuls les identifiants directs comptent dans le résultat principal. TAB et PARHAF marquent aussi des quasi-identifiants (une date, une profession, une situation familiale), rapportés à part et jamais mêlés à la moyenne.

## Résultats

Identifiants directs cachés, modèle seul (A) puis pipeline complet (F), en %.

| Jeu | GLiNER2 A → F | ONNX A → F |
|---|---|---|
| Actes générés | 36 → 76 | 19 → 70 |
| Actes générés longs | 2 → 79 | 1 → 86 |
| TAB | 27 → 46 | 31 → 61 |
| PARHAF | 15 → 34 | 11 → 32 |
| Gretel finance | 66 → 77 | 55 → 73 |

Sur chaque jeu et pour les deux modèles, les intervalles à 95 % de A et de F ne se recoupent pas.

## D'où vient le gain

Sur les actes générés avec GLiNER2, marche par marche : 36 % pour A, 66 % pour B, 74 % pour D, 76 % pour E et F.

- **Le découpage** fait l'essentiel, 31 à 33 points sur les actes générés et 53 à 64 sur les longs. Un modèle lit une fenêtre fixe, et sans découpage il ne voit jamais au-delà. Sur les actes longs, la marche A ne lit que la première page et rate toutes les valeurs qui suivent.
- **Les règles regex** ajoutent 8 à 14 points, et elles portent toutes les valeurs à forme fixe. E-mails, IBAN, numéros de sécurité sociale, numéros d'entreprise et téléphones atteignent 100 %, là où le modèle seul en trouve au plus un cinquième.
- **L'expander par mot entier** ajoute 2 à 4 points sur les actes générés et 10 à 11 sur les longs, où un nom revient des pages plus loin.
- **Le résolveur d'entités** n'ajoute pas de rappel. Il regroupe les graphies d'une même personne sous un seul jeton, ce qui réduit la part de personnes réparties sur plusieurs jetons, au prix de quelques personnes fusionnées à tort.

Le pipeline coûte un peu de précision, la part du texte masqué qui était vraiment une valeur. Sur les actes générés, elle passe de 87 % pour A à 77 % pour F. Une partie du coût vient des titres en capitales que le motif `SWIFT_BIC` prend pour des codes bancaires. Sur les actes longs, l'expander la fait descendre à 53 % avec ONNX, car un mot de titre masqué une fois l'est ensuite partout.

## Ce qui fuit encore

Sur les actes générés, pipeline GLiNER2 complet :

| Catégorie | Cachée | Documents où il n'en reste aucune en clair |
|---|---|---|
| E-mail, IBAN, numéro de sécurité sociale, numéro d'entreprise, téléphone | 100 % | 100 % |
| Organisation | 86 % | 77 % |
| Personne | 83 % | 13 % |
| Adresse | 57 % | 27 % |
| Parcelle cadastrale | 0 % | 0 % |
| Date de naissance | 0 % | 0 % |

Aucun acte généré ne sort sans rien en clair, et un seul nom oublié suffit. Les valeurs à forme fixe sont réglées par les règles. Les dates de naissance et les parcelles cadastrales n'étaient visées par aucun détecteur des configs mesurées. Les noms et les adresses dépendent du modèle.

## Ce que le banc d'essai a changé

Un premier passage a trouvé des défauts que `piighost` 1.9.0 corrige.

- L'expander par mot entier pouvait ajouter une occurrence à l'intérieur d'une détection retenue, et le rendu levait alors `OverlappingSpansError`. C'était le cas sur 163 des 200 actes générés.
- Les téléphones français composés avec des espaces insécables n'étaient jamais reconnus, ce qui bloquait le rappel du téléphone entre 50 et 72 %. Il est maintenant de 100 %.
- Une adresse e-mail accentuée était reconnue à partir de sa première suite ASCII, et son début restait en clair.
- Une config de détecteur ne pouvait pas fixer `max_chars`, donc un modèle construit depuis une config lisait un acte entier d'un coup. La config `fr-notarial` publiée y perdait 13 points de rappel, et manquait de mémoire au-delà de 13 000 caractères.

Combler le manque sur les dates de naissance oblige à masquer toutes les dates, car un motif ne distingue pas une date de naissance de la date de l'acte. Une config pour des actes peut se le permettre, une config pour une conversation non. Les configs mesurées ci-dessus ne portent aucun motif de date.

## Limites de ces chiffres

- Les documents français sont surtout générés. Un jeu médical écrit à la main (PARHAF) obtient moins que le jeu généré, et aucun acte notarié ouvert n'existe pour vérifier les actes générés.
- Chaque chiffre vient d'un seul passage sur CPU. Les intervalles tiennent compte du choix des documents, pas d'une autre version du modèle.
- La librairie mesurée est la version candidate de la 1.9.0 (commit `eb1a963`). La version publiée ajoute une recherche par mot entier plus rapide, aux correspondances identiques, et la clé de config `max_chars`.

## Voir aussi

- [Limites](limitations.md) : ce que la détection ne peut pas promettre, quel que soit son score.
- [Détecteurs prêts à l'emploi](examples/detectors.md) : les catalogues regex et les modèles.
- [Référence TOML](configuration/toml.md) : `max_chars` et les clés des détecteurs.
