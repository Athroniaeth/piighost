---
icon: lucide/cloud
seo_title: Appeler un serveur de dé-identification distant en Python
description: PIIGhostClient sert de pipeline de thread distant. Dé-identifiez et restaurez en HTTP, branchez-le dans le middleware LangChain, sortez le NER de l'hôte.
---

# Client distant

Vous allez utiliser `PIIGhostClient` comme un pipeline de conversation distant, interchangeable avec un pipeline local. Il implémente le même port qu'un `ThreadAnonymizationPipeline` local, mais chaque appel s'exécute contre un serveur `piighost-api` en HTTP. Vous le pointez sur une URL de base, dé-identifiez un message, le restaurez, puis glissez ce même client dans le middleware LangChain là où irait un pipeline local. Le modèle NER tourne ainsi hors de l'hôte applicatif, sur un serveur partagé, un nœud GPU ou un pod d'inférence dédié.

!!! note "Prérequis"
    `piighost` installé avec l'extra client, `pip install "piighost[client]"`, et un serveur `piighost-api` joignable, voir [Serveur d'API](api-server.md). On en suppose ici un sur `http://127.0.0.1:8000`.

## 1. Ouvrir un client

Passez une URL de base sous forme de chaîne. Le client construit alors son propre `httpx.AsyncClient`, et le ferme à la sortie du gestionnaire de contexte. Vous pouvez borner chaque requête avec `timeout`, joindre des en-têtes statiques via `headers` comme un jeton Authorization, et relancer une erreur de connexion `retries` fois, sans construire votre propre client. La grammaire de jetons, c'est-à-dire la forme que le client reconnaît comme un jeton, correspond par défaut à la `LabelCounterPlaceholderFactory` standard qu'émet un serveur `piighost`. `<<PERSON:1>>`{ .placeholder } est donc reconnu comme un jeton.

```python
--8<-- "snippets/server_connect.py"
```

## 2. Dé-identifier et restaurer un message

`anonymize` prend le texte et un `thread_id`, exactement comme le pipeline local. L'`Anonymization` renvoyée porte le texte mais un `.tokens` vide, parce que le serveur possède la table des jetons. Pour récupérer la valeur, appelez `deanonymize` avec le même `thread_id`. Le serveur la restaure alors à partir de sa table de conversation.

```python
--8<-- "snippets/server_client.fr.py:example"
```

La sortie doit être :

```text
--8<-- "snippets/server_client.fr.out"
```

`Patrick`{ .pii } devient `<<PERSON:1>>`{ .placeholder } sur le serveur, et `deanonymize` envoie le texte à jetons au serveur, qui le restaure. Rien de la table ne vit dans votre processus.

## 3. Oublier une conversation

`forget_thread` efface la conversation sur le serveur et renvoie le compte de ce qui a été supprimé, comme le pipeline local.

```python
--8<-- "snippets/server_forget.py:example"
```

La sortie doit être :

```text
--8<-- "snippets/server_forget.out"
```

## 4. Le glisser dans le middleware

Comme `PIIGhostClient` implémente le port du pipeline de conversation, il va partout où va un `ThreadAnonymizationPipeline` local, y compris dans `PIIAnonymizationMiddleware`. Le middleware le pilote avec les mêmes appels `anonymize` et `deanonymize`, sans savoir que le travail a lieu sur un serveur.

```python
--8<-- "snippets/server_middleware.py:example"
```

## Comment ça marche

`PIIGhostClient` est un substitut distant d'un `ThreadAnonymizationPipeline`. Il expose les mêmes méthodes, `anonymize`, `anonymize_corrected`, `deanonymize`, `forget_thread`, et une propriété `recognizer`, et transforme chacune en un appel HTTP vers `piighost-api`. `anonymize_corrected` dé-identifie à nouveau un message à partir d'un jeu de détections corrigé, par exemple après une relecture humaine. Le serveur détient le détecteur, la mémoire de conversation et la table des jetons, donc le client reste petit et sans état. `anonymize` renvoie un `.tokens` vide pour cette raison. Vous restaurez via `deanonymize`, pas en lisant une table locale.

La propriété `recognizer` laisse le middleware retrouver une grammaire de jetons même sur un pipeline distant, si bien que sa vérification des jetons inventés fonctionne encore. Si votre serveur est configuré avec une grammaire non standard, passez une fabrique correspondante en `recognizer=` à la construction du client.

Si vous gérez votre propre `httpx.AsyncClient`, pour un pool de connexions partagé, passez-le à la place d'une URL. Le client utilise l'instance injectée telle quelle et ne la ferme jamais, puisqu'elle vous appartient. Quand le client a construit le sien à partir d'une URL, appelez `await client.aclose()`, ou utilisez la forme `async with` qui le ferme pour vous.

## Voir aussi

- Pour exécuter le même pipeline en local plutôt qu'en HTTP, voir [Pipeline conversationnel](conversation.md).
- Pour brancher le client dans un agent LangChain de bout en bout, voir [Middleware LangChain](langchain.md).
- Pour monter le serveur `piighost-api` auquel le client parle, voir [Serveur d'API](api-server.md), et [Endpoints de l'API](../reference/api-endpoints.md) pour les routes qu'il appelle.
