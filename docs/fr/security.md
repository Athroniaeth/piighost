---
icon: lucide/shield-check
---

# Sécurité

Cette page complète [`SECURITY.md`](https://github.com/Athroniaeth/piighost/blob/master/SECURITY.md) à la racine du dépôt avec un modèle de menaces. Elle décrit ce contre quoi `piighost` protège, ce contre quoi il ne protège pas, et pourquoi.

!!! note "Dé-identification réversible"
    `piighost` dé-identifie par défaut. Il remplace chaque PII par un placeholder et **garde le lien** entre le placeholder et la valeur d'origine, pour restaurer la vraie valeur ensuite. Ce lien est un mapping de PII en clair. Le protéger est au coeur de ce modèle de menaces.

## Le trajet d'une valeur

Prenons un message qui contient `jean@mail.com`{ .pii }. `piighost` détecte la PII, la remplace par `<<EMAIL:1>>`{ .placeholder }, et envoie le texte dé-identifié au LLM. Le LLM ne voit que `<<EMAIL:1>>`{ .placeholder }. Quand la réponse revient, `piighost` réinjecte `jean@mail.com`{ .pii } à la place du placeholder, et l'utilisateur voit la vraie valeur.

Deux choses coexistent donc à tout moment. Le texte dé-identifié, qui peut circuler vers le LLM sans danger, et le mapping `<<EMAIL:1>>`{ .placeholder } vers `jean@mail.com`{ .pii }, qui ne doit jamais sortir de votre périmètre. Le modèle de menaces tient dans cette séparation.

## Ce contre quoi `piighost` protège

!!! success "Dans le périmètre de protection"
    - **Exfiltration vers les LLM tiers** : le LLM ne voit jamais que des placeholders (`<<PERSON:1>>`{ .placeholder }, etc.), jamais les vraies PII. Même si le provider journalise la requête, aucune donnée sensible ne fuit vers lui.
    - **Fuite via les appels d'outils** : le middleware désanonymise les arguments d'outil juste avant l'exécution, puis réanonymise les résultats avant qu'ils ne repartent vers le LLM. Les vraies valeurs ne transitent jamais par le contexte visible du LLM.
    - **Dérive inter-messages** : la `ConversationMemory` lie les variantes (`Patrick`{ .pii } et `patrick`{ .pii } sont regroupés par `(text.casefold(), label)`), pour que la même entité garde le même placeholder sur toute la conversation. Le LLM ne voit jamais la même PII sous deux masques différents.
    - **Fuite d'un store persistant volé** : un backend persistant (Redis ou SQL) peut chiffrer chaque valeur stockée et hacher la clé, donc un vol du store ne révèle ni le message ni la PII. Voir plus bas.

## Ce contre quoi `piighost` ne protège pas

!!! danger "Hors du périmètre de protection"
    - **Compromission de la mémoire du processus** : le mapping `placeholder` vers valeur d'origine vit en RAM le temps du traitement. Un attaquant qui lit la mémoire du processus récupère la PII en clair, quel que soit le backend.
    - **Store persistant non chiffré** : la mémoire en RAM (`InMemoryConversationMemory`) ne chiffre rien, elle sert au développement et au mono-processus. Un backend persistant construit sans crypto stocke ses valeurs en clair, donc un vol disque expose la PII. Configurez un hasher et un cipher sur le backend Redis ou SQL pour chiffrer au repos.
    - **Placeholders inventés par le LLM** : si le LLM fabrique un placeholder qui n'a jamais été émis, `piighost` ne peut pas le rattacher à une valeur puisqu'il n'est dans aucun mapping. Le middleware refuse par défaut ces jetons (`InventedPlaceholderError`). Voir [Limites](limitations.md).
    - **Ré-identification par le contexte** : un placeholder préserve la structure autour de lui. Une valeur dé-identifiée peut rester identifiable par ce qui l'entoure. « Le patient `<<PERSON:1>>`{ .placeholder }, seul cardiologue de la commune de 300 habitants » désigne une personne sans nommer sa PII. Le détecteur ne voit que des tokens, pas cette inférence.
    - **Détecteurs faillibles** : un détecteur est au mieux. Une PII qu'il ne reconnaît pas passe en clair vers le LLM. Voir [Limites](limitations.md) pour le garde-fou.
    - **Valeurs introduites par l'assistant sous PRESERVE** : avec le défaut `AssistantEntityStrategy.PRESERVE`, une valeur que le modèle a lui-même introduite reste en clair pour tout le fil, puisque le modèle la connaît déjà, et elle reste en clair même quand un message utilisateur ultérieur la reprend, car le fil date la valeur à sa première occurrence. Utilisez `ANONYMIZE` pour tokeniser aussi les valeurs introduites par l'assistant.
    - **Journaux applicatifs en amont** : `piighost` ne journalise jamais de PII brute, mais votre application peut le faire. Auditez vos propres journaux, traces et rapports d'erreurs avant de revendiquer une conformité.

## L'état LangGraph après le tour du modèle

Le middleware restaure la PII pour l'affichage. Après `aafter_model`, le contenu de chaque message porte à nouveau les vraies valeurs, l'utilisateur voit `jean@mail.com`{ .pii } et non `<<EMAIL:1>>`{ .placeholder }. Ce contenu restauré vit dans l'état LangGraph, et un checkpointer qui persiste l'état persiste de la PII en clair dans le contenu des messages. C'est voulu, l'état est votre surface d'affichage, mais cela signifie que le store du checkpointer contient des données sensibles et doit être protégé comme le mapping lui-même.

Les appels d'outils sont traités différemment. Les `tool_calls` d'un `AIMessage` restent tokenisés dans l'état. Le middleware ne dé-anonymise un argument d'outil que pour l'exécution de l'outil, sur une requête neuve, et ne réécrit jamais la valeur dé-anonymisée dans l'état, si bien que le checkpointer ne persiste jamais de valeur en clair dans un appel d'outil. Un résultat d'outil conservé comme `ToolMessage` reste lui aussi tokenisé dans l'état, une UI qui affiche les sorties d'outils depuis l'état voit donc des tokens, pas de la PII.

## Injection de token dans l'entrée utilisateur

Un token est restauré en une valeur parce qu'il ressemble à un token émis par le
pipeline. Un utilisateur qui tape `<<PERSON:2>>`{ .placeholder } dans l'entrée
pourrait sinon le voir restauré en la valeur de la deuxième entité, et lire une
valeur qui n'est pas la sienne. L'anonymiseur neutralise tout token tapé par
l'utilisateur avant le rendu, en insérant un caractère invisible dans le
délimiteur pour que la chaîne ne corresponde plus à la grammaire des tokens.
Seules les portions littérales entre les entités détectées sont neutralisées,
jamais les tokens que le pipeline insère, si bien qu'un vrai token est toujours
restauré et un token injecté ne l'est pas. Le comportement est actif par défaut
et se désactive avec `escape_existing_tokens=False` sur l'`Anonymizer`.

## Le mapping est de la PII en clair

La réversibilité a un prix. Pour restaurer `jean@mail.com`{ .pii } à partir de `<<EMAIL:1>>`{ .placeholder }, `piighost` garde le lien entre les deux. Ce lien, porté par la `ConversationMemory`, contient de la PII en clair. C'est l'actif le plus sensible du système, et il faut le protéger comme tel.

Trois backends existent, avec trois profils de sécurité.

`InMemoryConversationMemory` garde le mapping dans un dictionnaire du processus. Rien n'est chiffré, rien ne survit à un redémarrage, rien n'est partagé entre processus. C'est le bon choix pour le développement, les tests et un déploiement mono-processus. Ce n'est pas un stockage sécurisé.

`RedisConversationMemory` persiste chaque message dans Redis, un store en réseau partagé entre workers. `SqlAlchemyConversationMemory` persiste chaque message dans une table SQL, durable pour les conversations longues qui survivent à un processus, sur sqlite pour le développement et PostgreSQL pour la production. Les deux backends persistants offrent deux protections combinées.

- La **clé est hachée**. Le hasher tire une empreinte du message avec un poivre (*pepper*) secret. Le défaut est `Sha256Hasher` (HMAC-SHA256, rapide, adapté au chemin chaud). `Argon2Hasher` (Argon2id, lent et à mémoire dure) est l'alternative si le poivre lui-même risque de fuiter. Les deux sont déterministes, donc le même message retombe sur la même clé.
- La **valeur est chiffrée**. Le cipher chiffre le JSON des détections avant l'écriture. `AesGcmCipher` (AES-GCM) est le chiffrement authentifié fourni. Un nonce aléatoire est tiré par message, et le chiffrement échoue à déchiffrer un texte altéré.

Le poivre et la clé de chiffrement ne vivent **jamais dans le fichier de config**. Ils sont lus dans l'environnement, `PIIGHOST_HASH_PEPPER` pour le hasher et `PIIGHOST_CIPHER_KEY` (base64) pour le cipher. La sécurité repose sur ce secret qui vit hors du store. Un vol du disque du store seul ne révèle ni le message ni la PII, parce que la clé est hachée et la valeur chiffrée sous un secret que le disque ne contient pas.

!!! warning "Le secret vit dans l'environnement, pas dans la config"
    Un poivre ou une clé écrits dans un fichier de config versionné annulent la protection. Gardez-les dans l'environnement du processus ou dans un gestionnaire de secrets, et faites-les tourner comme n'importe quel secret de production.

### La crypto au repos est optionnelle sur chaque backend persistant

Le hasher et le cipher sont optionnels sur `RedisConversationMemory` comme sur `SqlAlchemyConversationMemory`. Passez les deux pour stocker de façon sécurisée, ou aucun pour stocker en clair. Passer exactement un seul lève `ValueError`, car une clé hachée avec une valeur en clair, ou l'inverse, ne protège rien de cohérent.

Un backend en réseau construit sans crypto émet un `PIIGhostSecurityWarning` à la construction, qui pointe vers cette page. Cet avertissement se déclenche pour Redis, toujours en réseau, et pour le backend SQL sur un dialecte autre que sqlite comme PostgreSQL. Il ne se déclenche pas pour la mémoire en RAM, qui est éphémère, ni pour le backend SQL sur sqlite, qui relève du développement local. L'avertissement pousse à configurer la crypto plutôt qu'à échouer, pour qu'une configuration en clair assumée puisse tout de même tourner.

Le backend SQL prend un moteur asynchrone injecté dont l'appelant possède le cycle de vie. Appelez `await memory.create_schema()` une fois au démarrage pour créer la table. Via la config, `SqlAlchemyMemoryConfig` (type `"sqlalchemy"`) lit l'URL de la base dans une variable d'environnement, `PIIGHOST_DATABASE_URL` par défaut, pour que l'URL et son mot de passe restent hors du fichier de config.

### Gradient confidentialité / restauration selon le backend

<table class="security-table" markdown="1">
<thead>
<tr><th>Backend</th><th>Mapping chiffré au repos ?</th><th>Clé du store lisible ?</th><th>Survit à un redémarrage ?</th><th>Partagé multi-worker ?</th></tr>
</thead>
<tbody>
<tr><td>InMemory (défaut)</td><td class="c-red">non (RAM en clair)</td><td class="c-red">oui (dict du processus)</td><td class="c-red">non</td><td class="c-red">non</td></tr>
<tr><td>SQL (sqlite, sans crypto)</td><td class="c-red">non (colonne en clair)</td><td class="c-red">oui (SHA-256 simple)</td><td class="c-blue">oui</td><td class="c-yellow">fichier local</td></tr>
<tr><td>SQL (PostgreSQL) + Sha256Hasher + AesGcm</td><td class="c-blue">oui (AES-GCM)</td><td class="c-green">non (HMAC-SHA256)</td><td class="c-blue">oui</td><td class="c-blue">oui</td></tr>
<tr><td>Redis + Sha256Hasher + AesGcm</td><td class="c-blue">oui (AES-GCM)</td><td class="c-green">non (HMAC-SHA256)</td><td class="c-blue">oui</td><td class="c-blue">oui</td></tr>
<tr><td>Redis + Argon2Hasher + AesGcm</td><td class="c-blue">oui (AES-GCM)</td><td class="c-blue">non (Argon2id, mémoire dure)</td><td class="c-blue">oui</td><td class="c-blue">oui</td></tr>
</tbody>
</table>

<small>
Légende :
<span class="sec-legend c-blue">meilleur</span>
<span class="sec-legend c-green">correct</span>
<span class="sec-legend c-yellow">partiel</span>
<span class="sec-legend c-red">problématique</span>
</small>

La colonne rouge de la mémoire en RAM n'est pas un défaut, c'est un choix de périmètre. Ce backend ne prétend pas être un stockage sécurisé. La ligne sqlite montre le même rouge sur la confidentialité quand elle est construite sans crypto, réservée au développement local. Dès que le mapping doit survivre à un redémarrage ou être partagé entre workers, passez à un backend persistant chiffré, Redis ou PostgreSQL avec un hasher et un cipher.

## Discipline de journalisation pour les dataclasses porteuses de PII

La dataclass `Detection` porte la forme brute de la PII dans son champ `text`. Le `__repr__` généré par dataclass affiche cette valeur en clair, ce qui rend l'API prévisible pour l'inspection, le debug et les tests.

```python
>>> from piighost.models import Detection, Span
>>> d = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=0.9)
>>> repr(d)
"Detection(span=Span(start=0, end=7), text='Patrick', label='PERSON', confidence=0.9)"
```

La librairie ne masque délibérément pas ce champ. Si vous transférez des instances `Detection` ou `Entity` vers des logs, des traces ou un reporter d'erreurs, faites le scrub vous-même. Deux recettes simples.

- Filtrer `to_dict()` avant sérialisation (retirer la clé `text`).
- Encapsuler votre logger structuré dans un redactor qui reconnaît les `Detection` et remplace `text` par un marqueur de longueur.

`piighost` lui-même n'écrit jamais de PII dans aucun logger. La discipline ci-dessus est nécessaire dans votre propre code.

## Redaction des payloads d'observation

Le pipeline trace ses étapes via OpenTelemetry. Chaque étape produit un span avec son propre payload d'entrée et de sortie, poussé vers le backend de trace que vous avez branché. Par défaut ces payloads contiennent le texte en clair et les valeurs des détections, ce qui rend les traces utilisables comme jeux d'annotation, mais dangereuses sur un backend qui n'a pas le droit de voir de la PII.

Le paramètre `observation_redactor` du pipeline contrôle ce comportement. Il prend une placeholder factory qui remplace chaque valeur détectée avant que le payload ne parte vers le backend. Avec `RedactPlaceholderFactory()`, toute entité retombe sur `<<REDACT>>`{ .placeholder }.

```text
texte utilisateur     : "Patrick habite à Paris."
payload d'observation : "<<REDACT>> habite à <<REDACT>>."
```

Concrètement :

- les payloads de texte voient chaque span de détection remplacé par le token de la factory. L'union des spans est fusionnée avant remplacement, donc aucun fragment en clair d'une détection ne survit au remplacement d'une autre,
- les `Detection` et `Entity` sérialisées portent le token de la factory à la place de leur champ `text`. Le label, la position et le nombre d'occurrences restent visibles pour le débogage,
- les payloads déjà dé-identifiés passent inchangés puisqu'ils ne contiennent que des placeholders.

Pour surfacer plus de structure (par exemple une numérotation distincte par PII en environnement de dev), passer une autre factory.

```python
from piighost.components.placeholder import LabelCounterPlaceholderFactory

redactor = LabelCounterPlaceholderFactory()
pipeline = AnonymizationPipeline(
    detector=detector,
    linker=linker,
    anonymizer=anonymizer,
    observation_redactor=redactor,  # <<PERSON:1>>, <<EMAIL:2>>, ...
)
```

N'importe quelle implémentation de `AnyPlaceholderFactory` est acceptée. Le redactor d'observation est indépendant de la factory qui sert à la dé-identification réelle, donc on peut afficher du `<<PERSON:1>>`{ .placeholder } côté trace tout en envoyant un autre schéma de placeholder au LLM. Laisser `observation_redactor` à `None` trace le texte en clair, à réserver à un backend de confiance. Ce défaut est traité comme un choix explicite. Avec un tracer provider réellement configuré et sans redactor, le pipeline avertit une fois que ses traces portent de la PII en clair, et `trace_clear_text=True` l'assume et tait l'avertissement.

## Décisions de conception qui soutiennent le modèle de menaces

- **La dé-identification est locale** : les PII sont remplacées avant que la requête HTTP n'atteigne le provider du LLM.
- **Le mapping est reconnu comme sensible** : le store de mapping contient de la PII en clair. Un backend persistant (Redis ou SQL) peut le chiffrer au repos (AES-GCM) et hacher ses clés (HMAC-SHA256 ou Argon2id), le secret vivant hors du store. La crypto est optionnelle et tout-ou-rien, et un backend en réseau construit sans elle avertit.
- **Aucune journalisation des PII brutes par la librairie** : `piighost` lui-même n'écrit jamais de PII dans un logger. Votre propre code doit suivre la même discipline.
- **Dataclasses gelées** : `Entity`, `Detection`, `Span` sont immuables, ce qui empêche la mutation accidentelle après que la dé-identification a été appliquée.
- **Garde-fou optionnel** : un garde-fou (`DetectorGuardRail`, `LLMGuardRail`, `ModerationGuardRail`) re-vérifie la sortie dé-identifiée et signale une PII résiduelle, à charge pour l'appelant de lever `PIIRemainingError`. Voir [Limites](limitations.md).

## Signaler une vulnérabilité

Voir [`SECURITY.md`](https://github.com/Athroniaeth/piighost/blob/master/SECURITY.md) pour le canal privé de signalement de vulnérabilités et la matrice des versions supportées.
