# Remote Thread Pipeline Client Design

Design spec for the HTTP client of the PIIGhost v2 rewrite, a remote stand-in
for the thread pipeline. Internal design document, French prose, English code
identifiers.

## Context

Le middleware et les consommateurs (piighost-chat) tournent aujourd'hui contre
un ThreadAnonymizationPipeline local. En production l'anonymisation vit derrière
piighost-api, un serveur HTTP. Il faut un client qui soit un remplaçant à
distance du pipeline de thread, avec la même surface, pour que le middleware et
tout consommateur passent de local à distant sans changer d'appel. piighost-api
a beaucoup évolué et sera réécrit contre ce contrat ; ce spec fixe donc le port
partagé et le contrat wire.

La v1 avait un PIIGhostClient (client.py) mais sans port partagé avec le
pipeline, et le middleware allait introspecter pipeline.anonymizer.factory pour
connaître la grammaire des tokens, ce qui est impossible en distant.

## Goal

Un port AnyThreadPipeline partagé par le pipeline local et un PIIGhostClient
distant, un client httpx injectable, et le middleware relié au port plutôt qu'à
l'anonymizer local, de sorte qu'un montage chat vers middleware vers api marche
sans que le middleware sache si le pipeline est local ou distant.

## Key decisions

- **Port partagé AnyThreadPipeline.** Un Protocol runtime-checkable avec les
  quatre méthodes du pipeline de thread (anonymize, anonymize_corrected,
  deanonymize, forget_thread) et une propriété recognizer. Le client distant est
  un remplaçant complet, HITL et droit à l'effacement compris.
- **La grammaire des tokens est une propriété du pipeline, pas une fouille du
  middleware.** Inversion de dépendance : le port expose recognizer, le
  BaseDelimitedPlaceholderFactory décrivant la grammaire des tokens émis, ou None
  quand elle n'est pas reconnaissable. Le pipeline local la dérive de son
  anonymizer.factory ; le client la déclare (défaut standard, surchargeable). Le
  middleware lit pipeline.recognizer au lieu de getattr(pipeline.anonymizer,
  "factory"), et garde son fail-fast (recognizer None lève
  UnrecognizableFactoryError).
- **Client httpx injectable ou construit.** __init__ prend client:
  httpx.AsyncClient | str. Un str est une base_url dont le client construit et
  possède l'AsyncClient, fermé par aclose ou le context manager ; un
  AsyncClient injecté n'est jamais fermé par le client, il appartient à
  l'appelant. Même patron que model | str des détecteurs, et cela laisse pool,
  auth, proxy, timeouts sous le contrôle de l'appelant.
- **anonymize distant renvoie des tokens vides.** Le port renvoie
  Anonymization[PreservationT] ; reconstruire le mapping entité vers token depuis
  le wire rouvrirait la friction des tags phantom (le client ignore le tag
  concret du serveur). Le client renvoie Anonymization(text=..., tokens={}). Le
  serveur détient la correspondance, restaurée via deanonymize, qui renvoie un
  str, identique en local et en distant sans aucune reconstruction. Le
  consommateur principal, le middleware, ne lit que .text. Faiblesse assumée et
  documentée : l'introspection locale token par token n'est pas exposée en
  distant.

## Architecture

Port, dans pipeline/base.py à côté de AnyPipeline (qui reste le port du pipeline
simple sans thread) :

- AnyThreadPipeline, Protocol runtime-checkable, générique sur PreservationT_co :
  - async anonymize(text, thread_id, role=MessageRole.USER) ->
    Anonymization[PreservationT_co]
  - async anonymize_corrected(text, thread_id, detections) ->
    Anonymization[PreservationT_co]
  - async deanonymize(text, thread_id) -> str
  - async forget_thread(thread_id) -> Forgotten
  - property recognizer -> BaseDelimitedPlaceholderFactory | None

ThreadAnonymizationPipeline gagne la propriété recognizer : renvoie
self.anonymizer.factory quand c'est un BaseDelimitedPlaceholderFactory, sinon
None. Aucune autre modification de sa logique.

Client, dans integrations/client/, derrière l'extra client (garde
find_spec("httpx") levant un ImportError pointant piighost[client], export lazy
depuis le __init__ du package, idiome des autres modules optionnels) :

Le port vit dans pipeline/base.py, donc pas de base.py dédié ici, et le module
de la classe s'appelle remote.py, pas httpx.py, pour ne pas masquer le paquet
httpx à l'import.

- remote.py : PIIGhostClient.
  - __init__(self, client: httpx.AsyncClient | str, recognizer:
    BaseDelimitedPlaceholderFactory | None = LabelCounterPlaceholderFactory()).
    Un str construit httpx.AsyncClient(base_url=...) et marque le client comme
    possédé ; un AsyncClient est stocké tel quel et non possédé.
  - Les quatre méthodes du port, plus aclose, __aenter__, __aexit__. aclose ne
    ferme le client sous-jacent que s'il est possédé.
  - property recognizer renvoie le recognizer stocké.

Le recognizer par défaut est un LabelCounterPlaceholderFactory, dont la grammaire
délimitée standard est celle qu'un serveur piighost émet par défaut ; seuls ses
délimiteurs comptent pour find_tokens, donc n'importe quelle factory délimitée
aux délimiteurs du serveur convient.

## Wire contract

Le client parle à piighost-api sur ces endpoints ; ce spec en fixe le contrat,
le serveur les implémentera dans son repo.

- POST /v1/anonymize, corps {text, thread_id, role}, réponse {anonymized_text}.
  role sérialisé par sa valeur, "user" ou "assistant". Le client renvoie
  Anonymization(text=anonymized_text, tokens={}).
- POST /v1/anonymize/corrected, corps {text, thread_id, detections}, où
  detections est la liste des Detection.to_dict() de l'ensemble corrigé, réponse
  {anonymized_text}. Le rôle est toujours utilisateur, la méthode n'a pas de
  paramètre role.
- POST /v1/deanonymize, corps {text, thread_id}, réponse {text}. Un thread
  inconnu renvoie le texte tel quel, aucune erreur, comme le deanonymize local.
- DELETE /v1/threads/{thread_id}, thread_id encodé pour l'URL, réponse
  {messages, detections}, reconstruite en Forgotten(messages, detections).

Toute réponse non-2xx lève RemoteError, avec le statut et le corps dans le
message.

## Errors

Ajouts à exceptions.py : ClientError(PIIGhostError), base de la famille du
client, et RemoteError(ClientError), levée sur une réponse HTTP non-2xx. Pas de
CacheMissError, la désanonymisation d'un thread inconnu renvoie le texte
inchangé comme en local.

## Middleware retouche

Le middleware type son pipeline sur AnyThreadPipeline et lit pipeline.recognizer
au lieu d'introspecter pipeline.anonymizer.factory. Son fail-fast est inchangé :
recognizer None lève UnrecognizableFactoryError à la construction. Le reste du
middleware, qui n'utilisait déjà que anonymize (dont .text) et deanonymize (un
str), fonctionne à l'identique contre le client distant.

## Testing

Déterministe, httpx.MockTransport pour simuler le serveur, aucun réseau :

- conformité : isinstance(client, AnyThreadPipeline) ;
- chaque méthode tape le bon endpoint avec le bon payload et parse la réponse :
  anonymize renvoie un Anonymization dont .text est le texte serveur et tokens
  est vide ; anonymize_corrected sérialise les détections et les envoie ;
  deanonymize renvoie le str serveur ; forget_thread reconstruit un Forgotten ;
- role sérialisé par sa valeur ;
- une réponse non-2xx lève RemoteError ;
- un str base_url construit et ferme son client à aclose ; un AsyncClient
  injecté n'est pas fermé par le client ;
- recognizer : défaut standard et surcharge ;
- pipeline local : recognizer renvoie la factory quand elle est délimitée, None
  pour une factory masque ;
- middleware : lit recognizer via le pipeline local et via un objet minimal
  exposant recognizer, et lève UnrecognizableFactoryError quand recognizer est
  None.

Régression PUBLIC_API : AnyThreadPipeline ajouté (eager, dans piighost.pipeline)
plus ClientError et RemoteError dans exceptions. PIIGhostClient n'est pas ajouté,
il est lazy derrière l'extra client et couvert par le walk
test_every_module_imports_cleanly.

## Out of scope

- L'implémentation serveur de piighost-api, autre repo.
- Les méthodes v1 deanonymize_with_ent, get_config, override_detections, à
  rajouter quand un besoin réel émerge (YAGNI).
- Le streaming de la désanonymisation.
- La sérialisation du mapping entité vers token complet dans anonymize (tokens
  vides en distant, décision ci-dessus).
- Le câblage TOML du client (bloc config ultérieur).
- La propagation traceparent, abandonnée côté piighost, pas simplement reportée.
  Relier une trace Langfuse d'agent LangChain et les spans piighost en un seul
  arbre est déjà couvert sans code lib. En local, le middleware tourne dans le
  même process, donc les spans piighost s'imbriquent sous le span ambiant de
  l'agent, une seule trace, c'est le sens du choix de ne poser
  langfuse.trace.name que sur le span racine. En distant, comme l'appelant
  injecte lui-même le httpx.AsyncClient du client, il injecte un client
  instrumenté OTel (opentelemetry-instrumentation-httpx) qui pose traceparent
  sur les requêtes sortantes ; l'api continue la trace et exporte vers le même
  projet Langfuse. La corrélation cross-process est donc une affaire de
  configuration de déploiement et d'instrumentation standard OTel, jamais du
  code piighost.
