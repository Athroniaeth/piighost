---
icon: lucide/shield-check
---

# Protéger un message avant l'envoi au LLM

Un utilisateur écrit un message qui contient des données confidentielles, c'est-à-dire des données personnelles (PII) et des secrets comme les clés d'API. Avant que ce message parte vers le LLM, `piighost` repère chaque valeur et la remplace par un placeholder, le token qui prend la place de la valeur, par exemple `<<PERSON:1>>`{ .placeholder } pour `Jean Dupont`{ .pii }. Le LLM ne reçoit que le texte dé-identifié.

Répond à : DPO-1, DPO-2, DPO-4, DEV-1

## Acteurs

- L'utilisateur final, qui écrit son message en clair
- L'application, qui reçoit le message et appelle le LLM
- `piighost`, placé entre l'application et le LLM
- Le LLM, qui reçoit le texte dé-identifié

## Préconditions

- L'application fait passer chaque message par `piighost` avant d'appeler le LLM, par exemple avec le middleware LangChain.
- Au moins un détecteur est configuré. `piighost` n'embarque aucun motif, donc les types protégés sont ceux des détecteurs et des groupes de motifs que la configuration charge.
- Pour reconnaître les clés d'API, la configuration charge un groupe de motifs de secrets du hub, comme `piighost/secrets`.

## Scénario nominal

1. L'utilisateur écrit ce message:

    ```text
    Écrivez à Jean Dupont, jean.dupont@exemple.fr
    ```

2. L'application transmet le message à `piighost` avant tout appel au LLM.
3. Le détecteur relève deux valeurs, `Jean Dupont`{ .pii } comme personne (`PERSON`) et `jean.dupont@exemple.fr`{ .pii } comme adresse e-mail (`EMAIL`).
4. La liste blanche et la liste noire de la configuration (section `[override]`) s'appliquent, si elles sont configurées. Elles ajoutent ou retirent des valeurs, voir [Imposer une liste blanche et une liste noire](enforce-server-lists.md).
5. Les détections qui se recouvrent sont départagées, pour qu'il n'en reste qu'une par passage du texte. Ici, rien ne se recouvre.
6. Les occurrences d'une même valeur sont regroupées. Chaque valeur reçoit un placeholder qui nomme son type et un numéro.

    - `Jean Dupont`{ .pii } devient `<<PERSON:1>>`{ .placeholder }
    - `jean.dupont@exemple.fr`{ .pii } devient `<<EMAIL:1>>`{ .placeholder }

7. Le garde-fou, s'il est configuré, relit le texte dé-identifié et n'y trouve plus aucune valeur.
8. Le LLM reçoit ce texte:

    ```text
    Écrivez à <<PERSON:1>>, <<EMAIL:1>>
    ```

9. `piighost` garde la correspondance entre chaque placeholder et sa valeur, ce qui permet de restaurer la réponse du LLM. La suite est décrite dans [Suivre une conversation et restaurer la réponse](follow-a-conversation.md).

## Scénarios alternatifs

### A1. Une valeur n'est pas détectée

Le détecteur connaît le nom mais pas l'adresse e-mail. Sans garde-fou, l'adresse part en clair:

```text
Écrivez à <<PERSON:1>>, jean.dupont@exemple.fr
```

Avec un garde-fou qui reconnaît les adresses e-mail, le traitement s'arrête avant l'envoi et l'application reçoit une erreur dont le message est `Anonymized text still contains PII: ['EMAIL']`. Rien ne part vers le LLM. L'utilisateur voit le message que l'application affiche pour ce refus. Pour corriger, ajoutez le type manquant au détecteur, ou forcez la valeur avec la liste blanche du serveur.

### A2. Un terme public est pris pour une donnée personnelle

Le détecteur lit le nom d'entreprise `Acme`{ .pii } comme une personne. "chez Acme" part alors sous la forme "chez `<<PERSON:2>>`{ .placeholder }", et le LLM perd une information dont il avait besoin. La liste noire de la configuration garde ce terme en clair, voir [Imposer une liste blanche et une liste noire](enforce-server-lists.md).

### A3. Deux détections se recouvrent

Un motif sûr à 100 % relève `Dupont`{ .pii } comme `NAME`, un modèle sûr à 70 % relève `Jean Dupont`{ .pii } comme `PERSON`. Le réglage par défaut garde la détection la plus sûre, et le reste du nom part en clair:

```text
Écrivez à Jean <<NAME:1>>, <<EMAIL:1>>
```

Le réglage "fusion" couvre toute la zone, avec le type de la détection la plus sûre:

```text
Écrivez à <<NAME:1>>, <<EMAIL:1>>
```

### A4. La même valeur revient sous une autre forme

Le message "Jean Dupont a appelé. Rappelez jean dupont demain." part sous la forme "`<<PERSON:1>>`{ .placeholder } a appelé. Rappelez `<<PERSON:1>>`{ .placeholder } demain.". La casse et les espaces ne séparent pas deux valeurs. À la restauration, les deux placeholders redeviennent `Jean Dupont`{ .pii }, la graphie de la première occurrence.

### A5. L'utilisateur tape lui-même un placeholder

L'utilisateur écrit un texte qui a la forme d'un placeholder:

```text
Jean Dupont écrit <<PERSON:2>> ici
```

`piighost` insère un caractère invisible (U+200B) après le premier caractère de `<<PERSON:2>>`. Le LLM reçoit "`<<PERSON:1>>`{ .placeholder } écrit `<<PERSON:2>>` ici", identique à l'écran, mais ce faux placeholder ne sera jamais restauré avec la valeur d'une autre personne.

## Règles

| Règle | Énoncé |
|---|---|
| BR-MSG-01 | Seul le détecteur est obligatoire, et par défaut chaque valeur reçoit un placeholder `<<TYPE:n>>` numéroté par type dans l'ordre d'apparition. |
| BR-MSG-02 | Les occurrences d'une même valeur sous un même type reçoivent le même placeholder, quelles que soient leur casse et leurs espaces. |
| BR-MSG-03 | La restauration remet partout la graphie de la première occurrence de la valeur. |
| BR-MSG-04 | Quand deux détections se recouvrent, la plus sûre est gardée, et à confiance égale celle qui commence le plus tôt, puis celle du premier détecteur déclaré. |
| BR-MSG-05 | Le départage des recouvrements est toujours actif, seul son mode change (plus sûre ou fusion). |
| BR-MSG-06 | Un texte tapé par l'utilisateur qui a la forme d'un placeholder est neutralisé par un caractère invisible et ne peut pas être restauré. |
| BR-MSG-07 | Sans garde-fou, une valeur que le détecteur ne voit pas part en clair vers le LLM. |
| BR-MSG-08 | Un garde-fou qui trouve une valeur restante bloque le texte, et son erreur nomme les types restants, jamais les valeurs. |
| BR-MSG-09 | Les motifs regex reconnaissent une forme sans vérifier de clé de contrôle, donc un IBAN ou un numéro de carte mal recopié est quand même dé-identifié. |
| BR-MSG-10 | Les secrets ne sont reconnus que si un groupe de motifs de secrets est chargé, ou par un modèle qui les cherche. |

## Postconditions

- Le LLM a reçu "Écrivez à `<<PERSON:1>>`{ .placeholder }, `<<EMAIL:1>>`{ .placeholder }" et aucune des deux valeurs.
- La correspondance entre chaque placeholder et sa valeur est gardée côté application, jamais transmise au LLM.
- En cas de refus par le garde-fou, aucun texte n'est parti.
- L'utilisateur a écrit `Jean Dupont`{ .pii } en clair, et seul le LLM travaille sur `<<PERSON:1>>`{ .placeholder }.

## Pour le développeur

Le pipeline d'un message isolé est `AnonymizationPipeline`. Seul le détecteur est requis. Les défauts sont `ExactEntityLinker`, `Anonymizer(LabelCounterPlaceholderFactory())` et `ConfidenceOverlapResolver`. L'expansion des occurrences, la résolution d'entités, les listes du serveur (`override`) et le garde-fou (`guard`) restent désactivés tant qu'ils ne sont pas passés.

```python
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector(
    {"Jean Dupont": "PERSON", "jean.dupont@exemple.fr": "EMAIL"}
)
pipeline = AnonymizationPipeline(detector)


async def main():
    result = await pipeline.anonymize("Écrivez à Jean Dupont, jean.dupont@exemple.fr")
    print(result.text)
    # Écrivez à <<PERSON:1>>, <<EMAIL:1>>


asyncio.run(main())
```

- Le mode "fusion" est `MergeOverlapResolver`, ou `type = "merge"` dans la section `[overlap_resolver]` d'une configuration.
- Le garde-fou se passe avec `guard=DetectorGuardRail(un_detecteur)` et lève `PIIRemainingError`. Un garde-fou à score, comme la modération, ne localise rien et son erreur donne le score à la place des types.
- La neutralisation des placeholders tapés se règle avec `Anonymizer(factory, escape_existing_tokens=True)`, actif par défaut. Le U+200B reste dans le texte restauré, ce qui compte si un traitement en aval compare des chaînes exactes.
- Dans une application avec agent, `piighost` passe par le middleware LangChain, qui pilote le pipeline de conversation. Voir [Middleware LangChain](../getting-started/langchain.md).

À lire ensuite.

- [Référence du pipeline](../reference/pipeline.md)
- [Détecteurs](../reference/detectors.md) et les catalogues de motifs du hub
- [Garde-fous](../reference/guard-rails.md)
- [Placeholder factories](../placeholder-factories.md)
- [Tester un pipeline sans modèle](../examples/testing.md)
- [Limites](../limitations.md)
