---
icon: lucide/radio
---

# Afficher une réponse streamée

Le LLM envoie sa réponse en morceaux, que l'application affiche au fil de l'eau. Un placeholder peut arriver coupé entre deux morceaux, `<<PER` puis `SON:1>>`. Le décodeur de flux de `piighost` retient le début du placeholder jusqu'à ce qu'il soit entier, puis le restaure une seule fois. Tant que le flux va jusqu'au bout, l'écran ne montre aucun placeholder cassé.

Répond à : DEV-9, UTI-4, UTI-1, DEV-8

## Acteurs

- L'utilisateur final, qui lit la réponse pendant qu'elle s'écrit
- L'application, qui lit le flux du LLM et l'affiche
- `piighost`, dont le décodeur de flux restaure les placeholders morceau par morceau
- Le LLM, qui envoie sa réponse en morceaux

## Préconditions

- La conversation `conv-1` associe `<<PERSON:1>>`{ .placeholder } à `Jean Dupont`{ .pii } et `<<EMAIL:1>>`{ .placeholder } à `jean.dupont@exemple.fr`{ .pii }.
- L'application fait passer chaque morceau par le décodeur de flux, en lui donnant l'identifiant de la conversation.
- Les placeholders ont des délimiteurs reconnaissables, `<<` et `>>` par défaut.

## Scénario nominal

1. L'utilisateur a demandé une réponse, et le LLM commence à l'envoyer.
2. Chaque morceau reçu passe par le décodeur, qui rend aussitôt ce qui peut être affiché.

    | Morceau reçu | Texte affiché |
    |---|---|
    | `"Bonjour <<PER"` | `"Bonjour "` |
    | `"SON:1>>, je vous"` | `"Jean Dupont, je vous"` |
    | `" écris à <<EMA"` | `" écris à "` |
    | `"IL:1>>."` | `"jean.dupont@exemple.fr."` |

3. Au premier morceau, le décodeur affiche "Bonjour " et retient `<<PER`, qui peut encore devenir un placeholder.
4. Au deuxième morceau, `<<PERSON:1>>`{ .placeholder } est complet. Il est restauré en `Jean Dupont`{ .pii } et affiché avec la suite du morceau.
5. Les morceaux trois et quatre suivent le même chemin pour `<<EMAIL:1>>`{ .placeholder }.
6. Le flux se termine. Le décodeur ne retient plus rien, et l'utilisateur a lu:

    ```text
    Bonjour Jean Dupont, je vous écris à jean.dupont@exemple.fr.
    ```

## Scénarios alternatifs

### A1. L'application restaure chaque morceau séparément

Sans le décodeur, chaque morceau est restauré seul. Ni `"Bonjour <<PER"` ni `"SON:1>>."` ne contient de placeholder entier, donc rien n'est remplacé, et l'utilisateur lit `Bonjour <<PERSON:1>>.` à l'écran.

### A2. Le flux s'arrête au milieu d'un placeholder

Le LLM envoie `"Bonjour <<PER"`, `"SON:1>>, à bientôt <<EMA"`, puis la connexion se coupe. À la fin du flux, le décodeur rend ce qu'il retenait tel quel. L'utilisateur lit `Bonjour Jean Dupont, à bientôt <<EMA`, avec un morceau de placeholder à l'écran.

### A3. Le LLM écrit un placeholder qui n'a jamais été émis

Le LLM envoie `"Bonjour <<PERSON:"` puis `"9>>."`. Le réglage des placeholders inventés s'applique dès que `<<PERSON:9>>`{ .placeholder } est complet.

| Réglage | Ce que voit l'utilisateur |
|---|---|
| Refuser (par défaut) | "Bonjour ", puis le flux s'interrompt sur une erreur |
| Retirer | "Bonjour ." |
| Garder | "Bonjour `<<PERSON:9>>`{ .placeholder }." |

### A4. La réponse contient `<<` sans placeholder

Le LLM écrit du code, `"Utilisez cout << x pour "` puis `"afficher, merci <<PERSON:1>>."`. Le décodeur retient `"<< x pour "` jusqu'au morceau suivant, puis rend `"<< x pour afficher, merci Jean Dupont."`. L'affichage prend un léger retard, sans perte de texte.

### A5. La réponse passe par un proxy du serveur `piighost-api`

Les proxys OpenAI et Anthropic du serveur `piighost-api` restaurent eux aussi les réponses streamées avec ce décodeur. Le proxy OpenAI ne restaure que le texte de la réponse, et laisse les placeholders dans les arguments d'appel d'outil streamés. Ni l'un ni l'autre n'applique de réglage aux placeholders inventés, qui passent tels quels. Voir [Dé-identifier un client OpenAI avec le proxy](../examples/openai-proxy.md) et [Dé-identifier Claude Code avec le proxy Anthropic](../examples/anthropic-proxy.md).

## Règles

| Règle | Énoncé |
|---|---|
| RG-FLUX-01 | Le texte qui ne peut pas appartenir à un placeholder est rendu dès son arrivée. |
| RG-FLUX-02 | À partir d'une ouverture `<<` non fermée, tout est retenu jusqu'à la fermeture, puis le placeholder entier est restauré une seule fois. |
| RG-FLUX-03 | Un `<` seul en fin de morceau est retenu, pour qu'un délimiteur coupé en deux se recolle. |
| RG-FLUX-04 | Une ouverture vieille de plus de 128 caractères est relâchée telle quelle, aucun placeholder n'étant aussi long. |
| RG-FLUX-05 | En fin de flux, le reste retenu est rendu tel quel, sans restauration. |
| RG-FLUX-06 | Le réglage des placeholders inventés s'applique à chaque placeholder complété, et le refus interrompt le flux. |
| RG-FLUX-07 | Les hooks du middleware LangChain ne voient que le message entier, donc l'affichage en direct demande d'envelopper la boucle de streaming avec le décodeur. |
| RG-FLUX-08 | Le décodeur demande l'identifiant de conversation explicitement, une boucle de streaming manuelle étant hors de la configuration de l'agent. |

## Postconditions

- L'utilisateur a lu "Bonjour Jean Dupont, je vous écris à jean.dupont@exemple.fr." au fil de l'eau.
- Chaque placeholder a été restauré une seule fois, au morceau qui le complétait.
- Le décodeur ne retient plus rien.
- L'écran n'a jamais montré `<<PER`, et la réponse s'est affichée sans attendre la fin du flux.

## Pour le développeur

Avec le middleware LangChain, `deanonymize_stream(source, thread_id)` prend un itérateur asynchrone de morceaux de texte et rend un itérateur asynchrone de texte restauré. Il applique `invented_strategy` à chaque placeholder complété et lève `InventedPlaceholderError` sous `RAISE`.

```python
config = {"configurable": {"thread_id": "conv-1"}}


async def model_text():
    async for chunk, _meta in agent.astream(
        {"messages": [{"role": "user", "content": "Écrivez à Jean Dupont"}]},
        config,
        stream_mode="messages",
    ):
        if isinstance(chunk.content, str):
            yield chunk.content


async for restored in middleware.deanonymize_stream(model_text(), "conv-1"):
    print(restored, end="", flush=True)
```

- Hors LangChain, `pipeline.recognizer.async_stream_decoder(replace)` construit le même décodeur, avec `replace` une coroutine qui restaure un placeholder, par exemple `lambda token: pipeline.deanonymize(token, thread_id)`. `feed(chunk)` rend le texte sûr, `flush()` rend le reste en fin de flux. Ce chemin n'applique aucun réglage aux placeholders inventés, sauf si `replace` le fait.
- `PlaceholderStreamDecoder` est la version synchrone, construite par `factory.stream_decoder(replace)`.
- Le décodeur suit les délimiteurs et la forme interne de la factory, donc une factory aux délimiteurs personnalisés garde le même comportement.
- La capacité Pydantic AI ne fournit pas de décodeur de flux.

À lire ensuite.

- [Référence de l'intégration LangChain](../reference/langchain.md), section Streaming
- [Placeholder factories](../placeholder-factories.md)
- [Suivre une conversation et restaurer la réponse](follow-a-conversation.md)
