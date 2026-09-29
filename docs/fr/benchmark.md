---
icon: lucide/gauge
---

# La détection, mesurée

Combien de valeurs confidentielles un pipeline `piighost` configuré cache, et ce que chaque étape ajoute par rapport à un modèle NER appelé directement. Les chiffres viennent d'un banc d'essai lancé le 2026-09-29 sur cinq jeux de données, en anglais et en français, avec `piighost` 1.9.0.

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
| Actes générés | 36 → 82 | 19 → 76 |
| Actes générés longs | 2 → 80 | 1 → 87 |
| TAB | 27 → 46 | 31 → 61 |
| PARHAF | 15 → 60 | 11 → 58 |
| Gretel finance | 66 → 78 | 55 → 74 |

Les jeux français tournent avec la config `fr-notarial`, TAB avec `support-en`. La config `fr-notarial` publiée obtient ce qu'obtient sa marche F, maintenant qu'elle découpe le texte pour son modèle.

Sur chaque jeu et pour les deux modèles, les intervalles à 95 % de A et de F ne se recoupent pas.

## D'où vient le gain

Sur les actes générés avec GLiNER2, marche par marche : 36 % pour A, 66 % pour B, 80 % pour D, 82 % pour E et F.

- **Le découpage** fait l'essentiel, 31 à 33 points sur les actes générés et 53 à 64 sur les longs. Un modèle lit une fenêtre fixe, et sans découpage il ne voit jamais au-delà. Sur les actes longs, la marche A ne lit que la première page et rate toutes les valeurs qui suivent.
- **Les règles regex** ajoutent 11 à 19 points, et elles portent toutes les valeurs à forme fixe. E-mails, IBAN, numéros de sécurité sociale, numéros d'entreprise et téléphones atteignent 100 %, là où le modèle seul en trouve au plus un cinquième.
- **L'expander par mot entier** ajoute 2 à 4 points sur les actes générés et 10 à 11 sur les longs, où un nom revient des pages plus loin.
- **Le résolveur d'entités** n'ajoute pas de rappel. Il regroupe les graphies d'une même personne sous un seul jeton, ce qui réduit la part de personnes réparties sur plusieurs jetons, au prix de quelques personnes fusionnées à tort.

Le pipeline coûte un peu de précision, la part du texte masqué qui était vraiment une valeur. Sur les actes générés, elle passe de 87 % pour A à 78 % pour F. Une partie du coût vient des titres en capitales que le motif `SWIFT_BIC` prend pour des codes bancaires. Sur les actes longs, l'expander la fait descendre à 54 % avec ONNX, car un mot de titre masqué une fois l'est ensuite partout.

## Ce qui fuit encore

Sur les actes générés, pipeline GLiNER2 complet :

| Catégorie | Cachée | Documents où il n'en reste aucune en clair |
|---|---|---|
| E-mail, IBAN, numéro de sécurité sociale, numéro d'entreprise, téléphone, date de naissance | 100 % | 100 % |
| Organisation | 86 % | 77 % |
| Personne | 83 % | 13 % |
| Adresse | 57 % | 27 % |
| Parcelle cadastrale | 0 % | 0 % |

Seuls 2,5 % des actes générés sortent sans rien en clair, car un seul nom oublié suffit. Les valeurs à forme fixe et les dates sont réglées par les règles. Aucun détecteur ne vise encore les parcelles cadastrales. Les noms et les adresses dépendent du modèle.

## Ce que le banc d'essai a changé

Les premiers passages ont trouvé des défauts que `piighost` 1.9.0 corrige.

- L'expander par mot entier pouvait ajouter une occurrence à l'intérieur d'une détection retenue, et le rendu levait alors `OverlappingSpansError`. C'était le cas sur 163 des 200 actes générés.
- Les téléphones français composés avec des espaces insécables n'étaient jamais reconnus, ce qui bloquait le rappel du téléphone entre 50 et 72 %. Il est maintenant de 100 %.
- Une adresse e-mail accentuée était reconnue à partir de sa première suite ASCII, et son début restait en clair.
- Une config de détecteur ne pouvait pas fixer `max_chars`, donc un modèle construit depuis une config lisait un acte entier d'un coup. La config `fr-notarial` publiée y perdait 13 points de rappel, et manquait de mémoire au-delà de 13 000 caractères.

Une date de naissance est un identifiant direct qu'aucun modèle NER ne relève, et aucune config mesurée n'en masquait. La config `fr-notarial` du hub masque désormais toutes les dates françaises, car un motif ne distingue pas une date de naissance de la date de l'acte, et découpe le texte pour son modèle avec `max_chars = 1000`. Par rapport au passage précédent :

| Actes générés, GLiNER2 | Avant | Après |
|---|---|---|
| Identifiants directs cachés, pipeline complet | 76 % | 82 % |
| La config telle que publiée | 63 % | 82 % |
| Dates de naissance cachées | 0 % | 100 % |
| Actes sans rien en clair | 0 % | 2,5 % |
| Précision | 77 % | 78 % |

Sur PARHAF, où les dates identifiantes sont des identifiants directs, le pipeline complet passe de 34 à 60 %. Le coût se voit dans les pièges. Les dates contenues dans les références juridiques sont masquées aussi, donc "loi du 10 juillet 1965" perd sa date, dans 239 des 452 références plantées contre 3 avant. Une config pour la conversation ne devrait pas porter ces motifs.

## Limites de ces chiffres

- Les documents français sont surtout générés. Un jeu médical écrit à la main (PARHAF) obtient moins que le jeu généré, et aucun acte notarié ouvert n'existe pour vérifier les actes générés.
- Chaque chiffre vient d'un seul passage sur CPU. Les intervalles tiennent compte du choix des documents, pas d'une autre version du modèle.
- Les appels au modèle sont les mêmes d'un passage à l'autre, rejoués depuis un cache indexé par leur entrée exacte. Un chiffre qui change vient du pipeline ou de la config, jamais d'une autre inférence.

## Voir aussi

- [Limites](limitations.md) : ce que la détection ne peut pas promettre, quel que soit son score.
- [Détecteurs prêts à l'emploi](examples/detectors.md) : les catalogues regex et les modèles.
- [Référence TOML](configuration/toml.md) : `max_chars` et les clés des détecteurs.
