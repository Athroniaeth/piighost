---
icon: lucide/spell-check
description: Anonymisation, pseudonymisation, caviardage et masquage comparés. Lesquels sont réversibles, ce que dit le RGPD, et pourquoi piighost pseudonymise les PII.
seo_title: Anonymisation ou pseudonymisation, caviardage et masquage
---

# Anonymisation, pseudonymisation, caviardage, masquage : les différences

L'anonymisation supprime les données personnelles pour de bon, alors que la pseudonymisation les remplace par un placeholder qu'une correspondance gardée à part permet d'inverser. Le caviardage efface une valeur d'un texte, et le masquage en cache une partie. Seule la pseudonymisation garde un moyen de revenir en arrière, et c'est ce que fait `piighost` par défaut.

Les exemples ci-dessous partent de la même phrase, "`Patrick`{ .pii } habite à Paris."

## Quatre termes

Anonymisation
:   Des données personnelles transformées en informations qui ne concernent plus une personne identifiable, par quiconque, avec tout moyen raisonnablement susceptible d'être utilisé. Elle est irréversible. Remplacer `Patrick`{ .pii } ne suffit pas si le reste du texte le désigne encore, comme dans "le maire qui a démissionné en mars".

Pseudonymisation
:   La valeur est remplacée, et l'information qui permet de la retrouver est conservée séparément. `Patrick`{ .pii } devient `<<PERSON:1>>`{ .placeholder }, et une correspondance gardée à part retransforme `<<PERSON:1>>`{ .placeholder } en `Patrick`{ .pii }. Elle est réversible pour qui détient la correspondance.

Caviardage
:   La valeur est effacée ou remplacée par un marqueur fixe, comme un trait noir sur une feuille. `Patrick`{ .pii } devient `<<REDACT>>`{ .placeholder }, et tout autre nom devient le même marqueur. Rien ne garde la trace de ce qui était là, on ne peut donc pas restaurer la valeur.

Masquage
:   Une partie de la valeur est cachée, et l'autre reste visible. `Patrick`{ .pii } devient `P******`{ .placeholder }. Un fragment fuit, et deux valeurs de même initiale et de même longueur se confondent, on ne peut donc pas non plus restaurer la valeur.

Tokenisation
:   La valeur est remplacée par un jeton, et un coffre garde le lien entre les deux. C'est une forme de pseudonymisation sous un autre nom. Un placeholder de `piighost` est un jeton en ce sens.

## Synthèse

| Terme | `Patrick`{ .pii } devient | Réversible | Au sens du RGPD |
|---|---|---|---|
| Anonymisation | rien qui ramène à lui | non | hors du règlement (considérant 26) |
| Pseudonymisation | `<<PERSON:1>>`{ .placeholder }, correspondance gardée à part | oui, avec la correspondance | toujours des données personnelles (article 4, point 5, considérant 26) |
| Caviardage | `<<REDACT>>`{ .placeholder } | non | non défini, données personnelles tant que la personne reste identifiable |
| Masquage | `P******`{ .placeholder } | non | non défini, données personnelles tant que la personne reste identifiable |
| Tokenisation | un jeton, lien gardé dans un coffre | oui, avec le coffre | une forme de pseudonymisation |

Le caviardage et le masquage n'aboutissent à une anonymisation que si plus rien dans les données, contexte compris, n'identifie la personne.

## Ce que dit le RGPD

Le RGPD définit la pseudonymisation et laisse les informations anonymes hors de son champ.

- L'[article 4, point 5](https://eur-lex.europa.eu/eli/reg/2016/679/oj/fra#art_4) définit la pseudonymisation comme "le traitement de données à caractère personnel de telle façon que celles-ci ne puissent plus être attribuées à une personne concernée précise sans avoir recours à des informations supplémentaires, pour autant que ces informations supplémentaires soient conservées séparément" et protégées par des mesures techniques et organisationnelles.
- Le [considérant 26](https://eur-lex.europa.eu/eli/reg/2016/679/oj/fra#rct_26) précise que les données pseudonymisées qui pourraient être attribuées à une personne par le recours à des informations supplémentaires "devraient être considérées comme des informations concernant une personne physique identifiable". Le même considérant indique qu'il n'y a "pas lieu d'appliquer les principes relatifs à la protection des données aux informations anonymes".

Les lignes directrices du Comité européen de la protection des données, la jurisprudence et ce qu'elles impliquent pour un déploiement sont sur la page [Conformité](compliance.md).

## Ce que fait piighost

Par défaut, `piighost` pseudonymise. Chaque valeur devient un placeholder comme `<<PERSON:1>>`{ .placeholder }, et la mémoire de conversation garde la correspondance qui restaure `Patrick`{ .pii } dans la réponse. Pour vous, le responsable du traitement qui détient cette correspondance, le texte dé-identifié reste une donnée personnelle.

Une placeholder factory de caviardage ou de masquage utilisée sans mémoire ne garde aucune correspondance, le texte tend donc vers l'anonymisation. Qu'il soit vraiment anonyme dépend encore de ce que révèle le reste du texte. Voir [Fabriques de placeholders](placeholder-factories.md) pour savoir quelles factories sont réversibles.

Dans une mention d'information ou une AIPD, appelez le traitement par défaut pseudonymisation, son nom juridique.

## Voir aussi

- [Conformité](compliance.md) : le RGPD et HIPAA en détail, avec les lignes directrices du Comité européen et la jurisprudence.
- [Glossaire](glossary.md) : les autres termes de ces pages.
- [Comment piighost se compare](comparison.md) : quels outils restaurent les valeurs et lesquels se contentent de les masquer.
