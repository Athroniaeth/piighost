---
name: langage-clair
description: Rendre un texte facile à comprendre du premier coup, en changeant le moins possible. À utiliser pour relire ou réécrire une réponse, une page de documentation, un README ou un message, en français ou en anglais, quand une phrase est dense, tassée, à relire deux fois, ou quand on demande un texte « plus clair », « plus compréhensible », « moins compliqué ». Reprend les règles de phrase de la norme ISO 24495-1 (langage clair). Pour les tics d'écriture d'IA, voir plutôt custom-humanizer.
---

# Langage clair

Un lecteur doit comprendre chaque phrase **à la première lecture**. Le but est la compréhension, pas le style. On change le moins possible, et seulement ce qui oblige à relire.

## Les règles

1. **Une idée par phrase.** Visez 15 à 20 mots. Deux idées reliées par « , et » ou « , donc » deviennent deux phrases.
2. **L'idée principale d'abord.** Ce que le lecteur doit retenir ouvre la phrase et le paragraphe. Le contexte vient après.
3. **La cause après l'effet, avec « parce que ».** Écrivez « X ne remplace pas Y, parce que Z », pas « Z, donc X ne remplace pas Y ».
4. **Pas de deux-points au milieu d'une phrase.** Les deux-points ne servent qu'à deux endroits, voir la section suivante.
5. **Pas de raccourci qui oblige à relire.** Avec « l'inverse », « ce qui », « cela », « le premier » ou « sans flux », dites de quoi il s'agit.
6. **Définir un terme technique à sa première apparition**, en une demi-phrase. Gardez le terme s'il est le plus juste.
7. **Des mots courants.** « Faire » plutôt qu'« effectuer », « selon » plutôt qu'« à l'aune de ». Pas de calque de l'anglais (« adresser un problème »).
8. **Un terme par concept**, du début à la fin. Pas de synonyme pour varier.
9. **Ne rien inventer, ne rien durcir.** Gardez chaque condition et chaque réserve (« si », « tant que », « par défaut »). Un chiffre mesuré reste ce chiffre. Écrivez « aucune fausse alerte pendant le test », pas « rarement ».
10. **Ne touchez pas à ce qui est déjà clair.** Une phrase longue mais limpide reste telle quelle.

## Où les deux-points sont permis

Seulement à ces deux endroits :

- **Une ligne qui annonce ce qui suit**, un titre, une liste ou un bloc, comme « Les deux options : » suivi de la liste.
- **Le libellé d'un élément de liste**, comme « - Concept : son explication. »

Partout ailleurs, coupez en deux phrases, ou remplacez par « parce que », « donc », « c'est-à-dire » ou une virgule.

| Avant | Après |
|---|---|
| Le but est la compréhension, pas le style : on change le moins possible. | Le but est la compréhension, pas le style. On change le moins possible. |
| C'est ce que fait un garde-fou : il dit oui ou non. | Un garde-fou fait la même chose. Il dit oui ou non. |
| Ce qui manque encore : le prix dans LiteLLM. | Il manque encore le prix dans LiteLLM. |

## Ce qu'on ne modifie jamais

- Le code, les noms de code, les identifiants (`BR-MSG-05`, `DPO-9`), les chemins, les URL.
- Les titres, car leurs ancres servent de liens, et la structure (sections, listes, tableaux).
- Le sens, le ton et la personne grammaticale du texte d'origine.

## Exemples

| Avant | Après |
|---|---|
| Laya ne dit pas où se trouve la valeur, il ne remplace donc pas un détecteur : c'est le second avis qui refuse une sortie que les détecteurs ont laissée passer. | Laya sert de second avis. Il refuse une sortie que les détecteurs ont laissée passer. Il ne remplace pas un détecteur, parce qu'il ne dit pas où se trouve la valeur. |
| Les deux sont complémentaires : Laya rattrape presque tout mais déclenche souvent pour rien, GLiNER2 l'inverse. | Laya et GLiNER2 se complètent. Laya rattrape presque toutes les fuites, mais donne souvent de fausses alertes. GLiNER2 rattrape moins de fuites, mais n'a donné aucune fausse alerte pendant le test. |
| Un modèle de décision répond à une question typée au lieu de générer du texte, ce qui est la forme d'un garde-fou : un oui ou un non sur la sortie dé-identifiée. | Un modèle de décision ne génère pas de texte. Il répond à une question dont les réponses possibles sont fixées à l'avance, ici oui ou non. Un garde-fou fait la même chose sur le texte dé-identifié. |
| Fait mieux : rien de plus à installer dans un agent LangChain, si l'utilisateur n'a pas besoin de relire ses vraies valeurs. La version JS fait le compromis inverse : elle restaure, mais sans flux. | LangChain PII n'ajoute rien à installer dans un agent LangChain. Ça suffit si l'utilisateur n'a pas besoin de relire ses vraies valeurs. Sa version JavaScript fait l'inverse. Elle restaure les vraies valeurs, mais pas pendant le streaming. |
| Ce qui manque encore : le prix dans LiteLLM. Le modèle passe par la règle générique `openai/*`, donc LiteLLM ne lui connaît pas de prix et ne compte pas sa dépense. | Il manque encore le prix de ce modèle dans LiteLLM. LiteLLM le route avec la règle générique `openai/*`, qui n'a pas de prix. LiteLLM ne sait donc pas combien coûte chaque appel, et ne compte pas la dépense. |

## En anglais

Les mêmes règles valent. « Because » pour la cause, une idée par phrase, pas de « the latter » ni de « the former », les termes définis à leur première apparition. Pas de colon au milieu d'une phrase non plus.

## Vérifier

Relisez chaque phrase modifiée. Un lecteur qui arrive sur cette page la comprend-il sans relire ? Comparez ensuite avec l'original. Aucun fait, aucune condition, aucun lien ne doit avoir disparu. Cherchez enfin les deux-points restants, et gardez seulement ceux d'une ligne d'annonce ou d'un libellé de liste.

Sources : ISO 24495-1:2023, et les skills plain-language-iso-24495 (nikdumroese), clarity (addyosmani) et boileau (alxbd).
