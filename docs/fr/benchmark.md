---
icon: lucide/gauge
seo_title: Benchmark de détection des PII, un NER seul face à piighost
description: Combien d'identifiants directs un pipeline piighost cache face à un modèle NER seul. GLiNER2 passe de 36 à 95 % sur des actes français générés.
---

# La détection, mesurée

Cette page mesure combien de valeurs confidentielles un pipeline `piighost` configuré cache, et ce que chaque étape ajoute par rapport à un modèle NER appelé directement. Les chiffres viennent d'un banc d'essai lancé le 2026-09-29 sur cinq jeux de données, en anglais et en français, avec `piighost` 1.10.0.

!!! note "Un décompte strict"
    Une valeur ne compte comme cachée que si chacun de ses caractères est masqué. Un masquage partiel est une fuite. `Paul <<PERSON:1>>`{ .placeholder } laisse `Paul`{ .pii } en clair, donc compte comme un raté pour `Paul Lemoine`{ .pii }. Les articles sur le NER retiennent le recouvrement, c'est-à-dire qu'une valeur en partie masquée y compte comme trouvée. Ce décompte-ci est plus strict, et ses chiffres sont plus bas pour cette raison.

## La question

Un modèle NER trouve les noms, les lieux et les organisations. `piighost` l'insère dans un pipeline qui ajoute le découpage du texte, des règles regex, la recherche des répétitions et le regroupement des entités. Ce pipeline cache-t-il plus que le modèle seul, et quelle étape fait le travail ?

Pour le savoir, le banc d'essai ajoute une étape à la fois, avec le même modèle sur les mêmes documents.

| Marche | Système |
|---|---|
| A | le modèle appelé directement sur tout le texte, comme le ferait un développeur, le texte étant tronqué à la fenêtre du modèle |
| B | A, avec le découpage de `piighost` |
| C | les règles regex de la config, sans modèle |
| D | B et C ensemble, chevauchements résolus |
| E | D, plus l'expander par mot entier |
| F | E, plus le résolveur d'entités, la config complète |

Chaque marche est mesurée avec deux modèles. L'un est GLiNER2 (`fastino/gliner2-multi-v1`, le modèle de la config `fr-notarial` du catalogue). L'autre est `onnx-community/gliner_multi_pii-v1` en ONNX, appelé via `BridgeDetector`, le moteur qui tourne dans le navigateur.

## Les données

| Jeu | Langue | Documents | Ce que c'est | Précaution |
|---|---|---|---|---|
| Actes générés | français | 200 | actes, baux, contrats de travail, e-mails, comptes rendus médicaux, construits sur des modèles avec des valeurs fictives | un texte généré flatte les scores, parce que chaque valeur est à un emplacement prévu pour elle |
| Actes générés longs | français | 12 | les mêmes, de 2 à 60 pages | trois documents par longueur, intervalles larges |
| TAB | anglais | 127 | arrêts de la CEDH annotés pour le Text Anonymization Benchmark (Pilán et al., 2022) | des arrêts publics, qu'un modèle a pu voir à l'entraînement |
| PARHAF | français | 101 | comptes rendus médicaux écrits à la main par des internes pour des patients fictifs | presque aucun identifiant à forme fixe, il teste donc le modèle |
| Gretel finance | français | 443 | documents financiers synthétiques | écrits par un LLM |

Aucun jeu ne contient les données d'une vraie personne privée. Seuls les identifiants directs comptent dans le résultat principal. TAB et PARHAF marquent aussi des quasi-identifiants (une date, une profession, une situation familiale), rapportés à part et jamais mêlés à la moyenne.

## Résultats

Identifiants directs cachés, modèle seul (A) puis pipeline complet (F), en %.

| Jeu | GLiNER2 A → F | ONNX A → F |
|---|---|---|
| Actes générés | 36 → 95 | 19 → 90 |
| Actes générés longs | 2 → 96 | 1 → 95 |
| TAB | 27 → 46 | 31 → 61 |
| PARHAF | 15 → 61 | 11 → 61 |
| Gretel finance | 66 → 79 | 55 → 75 |

Les jeux français tournent avec la config `fr-notarial`, TAB avec `support-en`. La config `fr-notarial` publiée obtient le même score que sa marche F. Sur chaque jeu et pour les deux modèles, les intervalles de confiance à 95 % de A et de F ne se recoupent pas.

!!! warning "Les formules d'acte ont été réglées sur des actes générés, puis vérifiées sur des modèles officiels"
    Les règles qui reconnaissent un nom après "Monsieur" ou une adresse après "demeurant" ont été écrites sur le jeu de dev des actes générés. Une partie de leur gain peut donc venir des tournures du générateur. Un jeu de contrôle mesure cet effet. Il compte 112 documents officiels, tirés de douze modèles du Code du travail numérique et des deux baux du décret n° 2015-587, dont les blancs sont remplis de valeurs fictives. Le pipeline complet y cache 91 % des identifiants directs avec GLiNER2 et 86 % avec ONNX, 3 à 4 points sous les actes générés. Les règles seules perdent 18 points, de 70 à 53 %. La précision tombe à 43 %, car le modèle relève les noms de rôle de la prose officielle ("salarié", "entreprise") et l'expander les répète.

## D'où vient le gain

Sur les actes générés avec GLiNER2, marche par marche, les scores sont de 36 % pour A, 66 % pour B, 94 % pour D, 95 % pour E et F.

- **Le découpage** apporte 31 à 33 points sur les actes générés et 53 à 64 sur les longs. Un modèle lit une fenêtre fixe, et sans découpage il ne voit jamais au-delà. Sur les actes longs, la marche A ne lit que la première page et rate toutes les valeurs qui suivent.
- **Les règles regex** apportent 28 à 40 points. Elles prennent en charge toutes les valeurs à forme fixe. Les e-mails, IBAN, numéros de sécurité sociale, numéros d'entreprise, téléphones et dates atteignent 100 %, là où le modèle seul en trouve au plus un cinquième. Les formules d'un acte ("Monsieur", "Maître", "née", "demeurant", "section") rattrapent les noms et les adresses que le modèle rate.
- **L'expander par mot entier** ajoute 1 à 3 points, moins qu'avant, car les règles trouvent maintenant elles-mêmes la plupart des répétitions.
- **Le résolveur d'entités** n'ajoute pas de rappel. Il regroupe les graphies d'une même personne sous un seul jeton.

Les règles et le modèle relèvent souvent la même valeur avec des longueurs différentes. `fr-notarial` garde leur union avec le résolveur de chevauchements `merge`. Avec le résolveur `confidence` par défaut, le span court d'une règle, de confiance 1.0, l'emportait sur le span plus long du modèle. Sur le jeu financier, la part des noms cachés tombait alors de 89 à 77 %.

La précision, la part du texte masqué qui était vraiment une valeur, reste proche de 86 % sur les actes générés. Sur les actes longs, l'expander la fait descendre à 59 % avec ONNX, car un mot de titre masqué une fois l'est ensuite partout.

## Ce qui fuit encore

Sur les actes générés, pipeline GLiNER2 complet :

| Catégorie | Cachée | Documents où il n'en reste aucune en clair |
|---|---|---|
| E-mail, IBAN, numéro de sécurité sociale, numéro d'entreprise, téléphone, date de naissance | 100 % | 100 % |
| Personne | 95 % | 59 % |
| Organisation | 94 % | 88 % |
| Adresse | 94 % | 81 % |
| Parcelle cadastrale | 43 % | 75 % |

43 % des actes générés sortent sans rien en clair, contre aucun avant les règles de dates et d'actes. Un seul nom oublié suffit encore à gâcher un acte. Les parcelles qu'un tableau liste sans le mot "section" sont manquées.

## Ce que le banc d'essai a changé

Chaque passage du banc d'essai a trouvé un défaut. Ce défaut a été corrigé dans la librairie ou dans la config `fr-notarial` du catalogue avant le passage suivant.

- **`piighost` 1.9.0.** L'expander par mot entier pouvait ajouter une occurrence à l'intérieur d'une détection retenue. Le rendu levait alors `OverlappingSpansError`, sur 163 des 200 actes générés. Les téléphones français composés avec des espaces insécables n'étaient jamais reconnus. Une adresse e-mail accentuée était reconnue à partir de sa première suite ASCII. Une config de détecteur ne pouvait pas fixer `max_chars`. Un modèle construit depuis une config lisait donc un acte entier d'un coup, et manquait de mémoire au-delà de 13 000 caractères.
- **Les dates.** Une date de naissance est un identifiant direct. Aucun des deux modèles du banc d'essai n'a été interrogé dessus, donc ce sont les règles qui la trouvent. `fr-notarial` masque toutes les dates françaises, parce qu'un motif ne distingue pas une date de naissance de la date de l'acte. Elle épargne la date d'un texte de loi numéroté ("loi n° 89-462 du 6 juillet 1989").
- **Les formules d'acte.** Un nom après une civilité ou "Maître", un nom de naissance après "née", une adresse après "demeurant" ou "situé", une adresse de rue, un lieu-dit et une référence cadastrale après "section".
- **`SWIFT_BIC`.** Il reconnaissait n'importe quelle suite de huit ou onze capitales. Il demande maintenant un mot-clé ou un chiffre, donc un titre comme "DESIGNATION" reste en clair.
- **`piighost` 1.10.0.** Ajout du résolveur de chevauchements `merge`. Le span court d'une règle ne découvre plus une partie du span du modèle.

Sur les actes générés, GLiNER2, passage après passage :

| | Candidate 1.9.0 | Dates, découpage | Formules, merge |
|---|---|---|---|
| Identifiants directs cachés, pipeline complet | 76 % | 82 % | 95 % |
| La config telle que publiée | 63 % | 82 % | 95 % |
| Actes sans rien en clair | 0 % | 2,5 % | 43 % |
| Précision | 77 % | 78 % | 86 % |
| Titres en capitales masqués, sur 1 437 | 411 | 411 | 30 |
| Références juridiques masquées, sur 452 | 14 | 250 | 14 |

Ces motifs sont faits pour une config de documents. Une config de conversation ne devrait ni masquer toutes les dates ni lire "Monsieur" comme le début d'un nom à cacher.

## Limites de ces chiffres

- Les documents français sont surtout générés. Un jeu médical écrit à la main (PARHAF) obtient moins que le jeu généré, et aucun acte notarié ouvert n'existe pour vérifier les actes générés.
- Chaque chiffre vient d'un seul passage sur CPU. Les intervalles tiennent compte du choix des documents, pas d'une autre version du modèle.
- Les appels au modèle sont les mêmes d'un passage à l'autre, rejoués depuis un cache indexé par leur entrée exacte. Un chiffre qui change vient du pipeline ou de la config, jamais d'une autre inférence.

## Voir aussi

- [Limites](limitations.md) : ce que la détection ne peut pas promettre, quel que soit son score.
- [Détecteurs prêts à l'emploi](examples/detectors.md) : les groupes regex du catalogue et les modèles.
- [Référence TOML](configuration/toml.md) : `max_chars` et les clés des détecteurs.
