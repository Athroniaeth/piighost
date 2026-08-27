---
icon: lucide/cloud
---

# Client distant

Vous allez utiliser `PIIGhostClient` comme un pipeline de fil distant, interchangeable avec un pipeline local. Il implémente le même port qu'un `ThreadAnonymizationPipeline` local, mais chaque appel s'exécute contre un serveur `piighost-api` en HTTP. Vous le pointez sur une URL de base, dé-identifiez un message, le restaurez, puis glissez ce même client dans le middleware LangChain là où irait un pipeline local. Cela garde le modèle NER hors de l'hôte applicatif, sur un serveur partagé, un nœud GPU ou un pod d'inférence dédié.

!!! note "Prérequis"
    `piighost` installé avec l'extra client, `pip install piighost[client]`, et un serveur `piighost-api` joignable. On en suppose ici un sur `http://localhost:8000`.

## 1. Ouvrir un client

Passez une URL de base sous forme de chaîne et le client construit et possède son `httpx.AsyncClient`, fermé à la sortie du gestionnaire de contexte. La grammaire de jetons par défaut correspond à la `LabelCounterPlaceholderFactory` standard qu'émet un serveur `piighost`, si bien que `<<PERSON:1>>`{ .placeholder } est reconnu comme un jeton.

```python
import asyncio

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    async with PIIGhostClient("http://localhost:8000") as client:
        ...


asyncio.run(main())
```

## 2. Dé-identifier et restaurer un message

`anonymize` prend le texte et un `thread_id`, exactement comme le pipeline local. Le serveur possède la table des jetons, donc l'`Anonymization` renvoyée porte le texte mais un `.tokens` vide. Pour récupérer la valeur, appelez `deanonymize` avec le même `thread_id`, ce qui restaure via la table de fil du serveur.

```python
    async with PIIGhostClient("http://localhost:8000") as client:
        result = await client.anonymize("Patrick habite à Paris.", "thread-42")
        print(result.text)

        restored = await client.deanonymize(result.text, "thread-42")
        print(restored)
```

La sortie doit être :

```text
<<PERSON:1>> habite à <<LOCATION:1>>.
Patrick habite à Paris.
```

`Patrick`{ .pii } devient `<<PERSON:1>>`{ .placeholder } sur le serveur, et `deanonymize` renvoie le texte à jetons pour restauration. Rien de la table ne vit dans votre processus.

## 3. Oublier un fil

`forget_thread` efface le fil sur le serveur et renvoie le compte de ce qui a été supprimé, comme le pipeline local.

```python
    async with PIIGhostClient("http://localhost:8000") as client:
        forgotten = await client.forget_thread("thread-42")
        print(forgotten)
        # Forgotten(messages=1, detections=2)
```

## 4. Le glisser dans le middleware

Comme `PIIGhostClient` implémente le port du pipeline de fil, il va partout où va un `ThreadAnonymizationPipeline` local, y compris dans `PIIAnonymizationMiddleware`. Le middleware le pilote avec les mêmes appels `anonymize` et `deanonymize`, sans savoir que le travail a lieu sur un serveur.

```python
from langchain.agents import create_agent
from piighost.integrations.client import PIIGhostClient
from piighost.integrations.langchain import PIIAnonymizationMiddleware

client = PIIGhostClient("http://localhost:8000")

agent = create_agent(
    model="openai:gpt-5.6-terra",
    tools=[...],
    middleware=[PIIAnonymizationMiddleware(pipeline=client)],
)
```

## Comment ça marche

`PIIGhostClient` est un substitut distant d'un `ThreadAnonymizationPipeline`. Il expose les mêmes méthodes, `anonymize`, `anonymize_corrected`, `deanonymize`, `forget_thread`, et une propriété `recognizer`, et transforme chacune en un appel HTTP vers `piighost-api`. Le serveur détient le détecteur, la mémoire de conversation et la table des jetons, donc le client reste petit et sans état. `anonymize` renvoie un `.tokens` vide pour cette raison. Vous restaurez via `deanonymize`, pas en lisant une table locale.

La propriété `recognizer` laisse le middleware retrouver une grammaire de jetons même sur un pipeline distant, si bien que sa vérification des jetons inventés fonctionne encore. Si votre serveur est configuré avec une grammaire non standard, passez une fabrique correspondante en `recognizer=` à la construction du client.

Si vous gérez votre propre `httpx.AsyncClient`, pour un pool de connexions partagé ou des en-têtes personnalisés, passez-le à la place d'une URL. Le client l'utilise tel quel et ne le ferme jamais, puisqu'il vous appartient. Sinon appelez `await client.aclose()`, ou utilisez la forme `async with` qui le ferme pour vous.

## Et ensuite

- Pour exécuter le même pipeline en local plutôt qu'en HTTP, voir [Pipeline conversationnel](conversation.md).
- Pour brancher le client dans un agent LangChain de bout en bout, voir [Middleware LangChain](langchain.md).
- Pour monter le serveur `piighost-api` auquel le client parle, voir [Déploiement](../deployment.md).
