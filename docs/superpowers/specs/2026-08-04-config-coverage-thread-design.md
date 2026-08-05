# Config Coverage C1: Thread Pipeline and In-Memory Backend Design

Design spec for the third sub-brick of the config coverage brick of the PIIGhost
v2 rewrite, the thread pipeline wiring and the in-memory conversation backend.
Internal design document, French prose, English code identifiers.

## Context

La couverture se découpe en A étapes optionnelles (fait), B détecteurs à modèle
(fait), C thread plus mémoire, D client plus JSON. La brique C s'est révélée trop
vaste, le backend Redis tirant une couche crypto, hasher et cipher. Elle est donc
scindée en C1, pipeline de thread plus mémoire in_memory, ce document, et C2,
backend Redis plus crypto.

Le core et les couvertures A et B bâtissent un AnonymizationPipeline simple, sans
état. Le pipeline de production, celui du middleware et de piighost-chat, est un
ThreadAnonymizationPipeline, qui garde une mémoire de conversation par thread. C1
permet de le décrire en TOML.

Les deux pipelines partagent la base BaseAnonymizationPipeline mais satisfont des
ports différents, AnyPipeline avec anonymize(text) pour le simple,
AnyThreadPipeline avec anonymize(text, thread_id, role), forget_thread et
recognizer pour le thread. Ce fait dicte la forme des points d'entrée.

## Goal

Un champ memory optionnel sur PipelineConfig, un modèle InMemoryConfig le
remplissant, un build() polymorphe assemblant l'un ou l'autre pipeline, et deux
points d'entrée typés, load_pipeline pour le simple et load_thread_pipeline pour
le thread, chacun refusant le TOML de l'autre.

## Key decisions

- **Un champ memory sur PipelineConfig, pas de sous-classe.** PipelineConfig gagne
  memory, un MemoryConfig ou None. build() assemble les étapes une fois puis
  branche, memory présent construit un ThreadAnonymizationPipeline, absent un
  AnonymizationPipeline. Son type de retour s'élargit à la base commune
  BaseAnonymizationPipeline.
- **Deux points d'entrée typés qui refusent le mauvais TOML.** load_pipeline rend
  un AnonymizationPipeline et lève ConfigError si le TOML déclare une mémoire,
  car perdre la mémoire silencieusement serait un piège. load_thread_pipeline rend
  un ThreadAnonymizationPipeline et lève ConfigError si le TOML n'en déclare pas.
  Chacun fait un isinstance sur le résultat de build().
- **MemoryConfig est un alias tant qu'un backend existe.** InMemoryConfig, type
  in_memory, build() renvoyant InMemoryConversationMemory(), sans argument ni
  extra. MemoryConfig est un alias d'InMemoryConfig, il devient une union
  discriminée quand le backend redis arrive en C2, comme LinkerConfig.
- **La mémoire est bâtie en import différé.** Le port AnyConversationMemory est
  importé en tête, InMemoryConversationMemory dans build(), pour que le module
  memory.py reste uniforme quand C2 ajoutera le backend redis à extra.

## Architecture

config/models/memory.py (nouveau) :

- InMemoryConfig, _ComponentConfig, type Literal in_memory, build() renvoyant
  InMemoryConversationMemory() importé en différé, type de retour
  AnyConversationMemory.
- MemoryConfig, alias d'InMemoryConfig, avec un docstring attaché disant qu'il
  devient une union quand redis arrive.

config/settings.py (modifié) :

- Import de BaseAnonymizationPipeline et ThreadAnonymizationPipeline depuis
  piighost.pipeline, de ConfigError depuis piighost.exceptions, de MemoryConfig
  depuis config.models.memory.
- PipelineConfig gagne memory, MemoryConfig ou None, défaut None.
- build() renvoie BaseAnonymizationPipeline. Il construit detector, linker,
  anonymizer et les six étapes optionnelles une fois, puis, si memory n'est pas
  None, renvoie un ThreadAnonymizationPipeline avec memory construite et les
  étapes, sinon un AnonymizationPipeline avec les étapes. ThreadAnonymizationPipeline
  prend memory en mot-clé, son constructeur étant detector, linker, anonymizer,
  memory, puis les optionnelles.
- load_pipeline(path), type de retour AnonymizationPipeline, appelle
  load_config(path).build() et, si le résultat n'est pas un AnonymizationPipeline,
  lève ConfigError invitant à load_thread_pipeline, sinon le renvoie.
- load_thread_pipeline(path), type de retour ThreadAnonymizationPipeline, appelle
  build() et, si le résultat n'est pas un ThreadAnonymizationPipeline, lève
  ConfigError invitant à load_pipeline, sinon le renvoie.

config/__init__.py (modifié) : ajoute load_thread_pipeline aux exports, derrière
l'extra config.

AnonymizationPipeline et ThreadAnonymizationPipeline sont des frères sous
BaseAnonymizationPipeline, aucun n'est sous-classe de l'autre, donc un isinstance
sur l'un exclut l'autre, et les deux points d'entrée se distinguent proprement.

## Errors

Aucune nouvelle exception. load_pipeline et load_thread_pipeline lèvent la
ConfigError existante, base de la famille config, quand le TOML et le point
d'entrée ne s'accordent pas sur la présence d'une mémoire.

## Testing

Déterministe, TOML écrit dans un fichier temporaire, détecteur exact et
anonymizer label_counter, pour voir l'identité partagée :

- load_thread_pipeline bâtit un ThreadAnonymizationPipeline. Sur deux messages du
  même thread, hi Patrick puis bye Patrick, Patrick garde le même token
  PERSON deux-points un, la mémoire partage le placeholder entre messages ;
- InMemoryConfig.build() rend un InMemoryConversationMemory ;
- load_pipeline sur un TOML qui déclare une mémoire lève ConfigError ;
- load_thread_pipeline sur un TOML sans mémoire lève ConfigError ;
- load_pipeline sur un TOML sans mémoire reste inchangé, il anonymise un texte
  connu de bout en bout, non-régression ;
- le couplage à sens unique tient, le core n'importe pas config.

Packaging et régression PUBLIC_API : rien à ajouter. In_memory est sans extra, et
load_thread_pipeline vit derrière l'extra config, couvert par le walk
test_every_module_imports_cleanly. Aucune exception nouvelle.

## Out of scope

- Le backend Redis et la crypto, hasher et cipher, sous-lot C2.
- Le client distant et le format JSON, sous-lot D.
- Le forget_thread et anonymize_corrected en config, ce sont des méthodes du
  pipeline construit, pas des options de config.
- La surcharge env du thread_id ou d'un thread par défaut, le thread_id est un
  argument d'appel, pas de config.
