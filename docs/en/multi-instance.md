---
icon: lucide/network
---

# Multi-instance deployment

This page explains why the default cache (`SimpleMemoryCache`) silently breaks the consistency of the placeholders as soon as your application runs on more than one worker, and how to configure a shared backend to restore consistency.

!!! abstract "Summary"
    In multi-instance behind a load balancer, each worker maintains its own `SimpleMemoryCache`. The same `thread_id` routed to two workers will see `Patrick` assigned to `<<PERSON:1>>`{ .placeholder } on turn 1 then `<<PERSON:2>>`{ .placeholder } on turn 2, and the LLM can no longer relate the two. The fix is a shared cache (Redis, Memcached) passed explicitly to the pipeline.

---

## The trap

`SimpleMemoryCache` is an excellent default for development and single-instance deployments. It is fast, without external dependency, and requires no configuration. It is also the implicit default when you instantiate `ThreadAnonymizationPipeline` without specifying a backend.

The problem appears as soon as a load balancer routes the same `thread_id` to several workers. Each worker has its own `placeholder ↔ PII` cache, and these caches do not communicate.

```text
Tour 1 (routé vers worker A)
  Mémoire worker A : { Patrick → <<PERSON:1>> }
  Mémoire worker B : {}

Tour 2 (routé vers worker B, "Patrick" toujours dans le contexte)
  Mémoire worker A : { Patrick → <<PERSON:1>> }
  Mémoire worker B : { Patrick → <<PERSON:1>> }   # nouveau compteur, collision possible

Tour 3 (worker B reçoit "Marie")
  Mémoire worker B : { Patrick → <<PERSON:1>>, Marie → <<PERSON:2>> }

Tour 4 (worker A reçoit "Marie", l'ignore de son point de vue)
  Mémoire worker A : { Patrick → <<PERSON:1>>, Marie → <<PERSON:2>> }
  # Sur worker A, Marie aurait pu hériter d'un autre numéro si une autre PII l'avait précédée.
```

The bug is silent. No exception is raised, the pipeline produces valid anonymized text, and the inconsistency only becomes visible in the response quality of the LLM, which loses the thread between turns.

---

## The warning

On the first instantiation of `ThreadAnonymizationPipeline` without an explicit backend, the library emits a `PIIGhostConfigWarning` once per process.

```text
PIIGhostConfigWarning: ThreadAnonymizationPipeline is using a process-local
cache (SimpleMemoryCache). In a multi-instance deployment behind a load
balancer, the placeholder mapping is not shared across workers...
```

The warning is about **correctness**, not performance. The risk is not that the pipeline is slow, it is that it produces inconsistent placeholders without anything signaling it.

If you run single-instance and you want to suppress the noise, add a filter:

```python
import warnings
from piighost import PIIGhostConfigWarning

warnings.filterwarnings("ignore", category=PIIGhostConfigWarning)
```

---

## Configuring a shared backend

The constructor of `ThreadAnonymizationPipeline` accepts any `aiocache.BaseCache` instance. For multi-instance, use `RedisCache` or `MemcachedCache`.

### With Redis

```python
from aiocache import RedisCache
from piighost.anonymizer import Anonymizer
from piighost.detector.gliner2 import Gliner2Detector
from piighost.pipeline.thread import ThreadAnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory

cache = RedisCache(
    endpoint="redis.internal",
    port=6379,
    namespace="piighost",
)

pipeline = ThreadAnonymizationPipeline(
    detector=Gliner2Detector(...),
    anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
    cache=cache,
    cache_ttl=3600,  # purger après 1 h sans usage
)
```

All the workers pointing at the same Redis see the same mappings. The `thread_id` remains the unit of isolation, and conversations stay watertight between users.

### With Memcached

```python
from aiocache import MemcachedCache

cache = MemcachedCache(
    endpoint="memcached.internal",
    port=11211,
    namespace="piighost",
)
```

The semantics are the same as Redis for our use. Memcached automatically evicts the least recently used entries when the memory is saturated, which can be suitable if you accept that a conversation idle long enough loses its mapping.

---

## Consistency with LangGraph

The trap is not specific to `piighost`. LangGraph hits exactly the same problem with its `checkpointer`, and offers `MemorySaver` (process-local, default) or `PostgresSaver` / `RedisSaver` (shared) for multi-instance deployments. If you already use one of these savers, align the `piighost` backend on the same infrastructure.

```python
from langchain.agents import create_agent
from langgraph.checkpoint.redis import RedisSaver
from aiocache import RedisCache

# Réutilisez la même instance Redis pour les deux couches
checkpointer = RedisSaver.from_conn_string("redis://redis.internal:6379")
cache = RedisCache(endpoint="redis.internal", port=6379, namespace="piighost")

pipeline = ThreadAnonymizationPipeline(
    detector=...,
    anonymizer=...,
    cache=cache,
)
agent = create_agent(model="...", tools=[...], middleware=[...], checkpointer=checkpointer)
```

Keeping the two layers on the same Redis guarantees that a `thread_id` that has a checkpointed state also has its `placeholder ↔ PII` mapping accessible, on any worker.

---

## See also

- [Conversational pipeline](getting-started/conversation.md): basic usage of `ThreadAnonymizationPipeline`.
- [Security](security.md): threat model and guarantees offered by the cache mapping.
- [Deployment](deployment.md): wheel caching and strategies for `piighost-api`.
