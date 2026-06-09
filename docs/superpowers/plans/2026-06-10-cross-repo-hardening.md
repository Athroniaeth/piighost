# Cross-Repo PII Chain Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deployed PII chain real: a shared cache backend actually wired end-to-end, a complete right-to-be-forgotten chain (lib → api → chat), fail-fast auth and request limits on piighost-api, and the chat-side correctness fixes (prompt format, log redaction, SSE).

**Architecture:** Phase A extends the piighost lib (TOML `[cache]` section resolved through env-var indirection, public APIs replacing the three private accesses piighost-api makes, `PIIGhostClient.forget_thread`). A release gate follows (cz bump; the human pushes/publishes). Phase B hardens piighost-api against the new lib (tested via the editable install). Phase C closes the chat-side chain. Each repo works on its own feature branch.

**Tech Stack:** Python 3.12, uv, pytest (asyncio auto), Litestar 2.21, aiocache 0.12 (`Cache.from_url`), msgspec, LangChain/LangGraph, React 19 + Vite (front), Conventional Commits.

**Repos and branches:**
- `~/PycharmProjects/piighost` → branch `feat/cache-config` (off master)
- `~/PycharmProjects/piighost-api` → branch `feat/hardening` (off master)
- `~/PycharmProjects/piighost-chat` → branch `feat/pii-chain` (off master/main, check default)

**Out of scope (explicitly deferred):** chat auth/ownership, psycopg pooling + list_threads N+1, model selector wiring, chat full test suite beyond the new code, docs EN/FR passes, rebuilding/publishing the piighost-api docker image.

---

## Phase A — piighost lib (branch `feat/cache-config`)

### Task A1: TOML `[cache]` section with env-var indirection

**Files:**
- Create: `src/piighost/config/models/cache.py`
- Modify: `src/piighost/config/models/pipeline.py` (add `cache` field to `PipelineConfig`)
- Modify: `src/piighost/config/builders.py` (add `build_cache`)
- Modify: `src/piighost/config/loader.py` (`build_pipeline` passes `cache=`)
- Modify: `pyproject.toml` (new `redis` extra)
- Test: `tests/config/test_cache_config.py` (create)

- [ ] **Step 1: Write the failing tests** — create `tests/config/test_cache_config.py`:

```python
"""TOML [cache] section: backend selection with env-var URL indirection."""

import pytest
from aiocache import SimpleMemoryCache

from piighost.config import load_config
from piighost.config.builders import build_cache
from piighost.config.errors import ConfigError
from piighost.config.models.cache import (
    MemoryCacheConfig,
    RedisCacheConfig,
    SqlAlchemyCacheConfig,
)

MINIMAL_DETECTOR = r"""
[[detectors]]
type = "regex"
[detectors.patterns]
EMAIL = '\S+@\S+'
"""


def _write_toml(tmp_path, body: str):
    path = tmp_path / "pipeline.toml"
    path.write_text(body)
    return path


def test_cache_section_defaults_to_memory(tmp_path):
    cfg = load_config(_write_toml(tmp_path, MINIMAL_DETECTOR))
    assert isinstance(cfg.cache, MemoryCacheConfig)
    assert isinstance(build_cache(cfg.cache), SimpleMemoryCache)


def test_redis_cache_reads_url_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_REDIS", "redis://localhost:1/0")
    cfg = load_config(
        _write_toml(
            tmp_path,
            '[cache]\ntype = "redis"\nurl_env = "MY_REDIS"\n' + MINIMAL_DETECTOR,
        )
    )
    assert isinstance(cfg.cache, RedisCacheConfig)
    cache = build_cache(cfg.cache)
    # No connection happens at construction; just check the backend type.
    assert type(cache).__name__ == "RedisCache"


def test_redis_cache_missing_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_REDIS", raising=False)
    cfg = load_config(
        _write_toml(
            tmp_path,
            '[cache]\ntype = "redis"\nurl_env = "MY_REDIS"\n' + MINIMAL_DETECTOR,
        )
    )
    with pytest.raises(ConfigError, match="MY_REDIS"):
        build_cache(cfg.cache)


def test_sqlalchemy_cache_reads_url_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_DB", "sqlite+aiosqlite:///:memory:")
    cfg = load_config(
        _write_toml(
            tmp_path,
            '[cache]\ntype = "sqlalchemy"\nurl_env = "MY_DB"\ntable_name = "pii"\n'
            + MINIMAL_DETECTOR,
        )
    )
    assert isinstance(cfg.cache, SqlAlchemyCacheConfig)
    cache = build_cache(cfg.cache)
    assert type(cache).__name__ == "SQLAlchemyCache"


async def test_load_pipeline_wires_the_cache(tmp_path, monkeypatch):
    from piighost.config import load_pipeline

    pipeline, _ = load_pipeline(_write_toml(tmp_path, MINIMAL_DETECTOR))
    assert isinstance(pipeline._cache, SimpleMemoryCache)
```

- [ ] **Step 2: Run** `uv run pytest tests/config/test_cache_config.py -v` — FAIL (`ModuleNotFoundError: piighost.config.models.cache`).

- [ ] **Step 3: Create `src/piighost/config/models/cache.py`:**

```python
"""Cache backend configuration models.

Connection URLs are NEVER stored in the TOML: each backend names an
environment variable (``url_env``) holding the URL, so one config file
works across environments and secrets stay out of version control
(same philosophy as the hash pepper).
"""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class MemoryCacheConfig(_ComponentConfig):
    """Process-local in-memory cache (the default).

    Suitable for single-process deployments only: mappings are lost on
    restart and not shared across workers.
    """

    type: Literal["memory"] = "memory"


class RedisCacheConfig(_ComponentConfig):
    """Redis backend via aiocache. Requires the ``redis`` extra."""

    type: Literal["redis"]
    url_env: str = "REDIS_URL"
    """Environment variable holding the redis:// connection URL."""
    namespace: str = Field(default="piighost", min_length=1)


class SqlAlchemyCacheConfig(_ComponentConfig):
    """SQL backend via piighost.cache.SQLAlchemyCache. Requires the ``sqlalchemy`` extra."""

    type: Literal["sqlalchemy"]
    url_env: str = "DATABASE_URL"
    """Environment variable holding the SQLAlchemy async URL."""
    table_name: str = Field(default="piighost_cache", min_length=1)


CacheConfig = Annotated[
    MemoryCacheConfig | RedisCacheConfig | SqlAlchemyCacheConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Add the field to `PipelineConfig`** in `src/piighost/config/models/pipeline.py`:

```python
from piighost.config.models.cache import CacheConfig, MemoryCacheConfig
```
```python
    cache: CacheConfig = Field(default_factory=MemoryCacheConfig)
```

- [ ] **Step 5: Add `build_cache` to `src/piighost/config/builders.py`:**

```python
def build_cache(cfg: BaseModel) -> "BaseCache":
    """Build the cache backend from its validated configuration.

    URL-bearing backends read their connection URL from the environment
    variable named by ``url_env`` and raise ``ConfigError`` when it is
    unset, so a misconfigured deployment fails at startup instead of
    silently degrading to a process-local cache.
    """
    import os

    from piighost.config.errors import ConfigError

    if isinstance(cfg, MemoryCacheConfig):
        from aiocache import SimpleMemoryCache

        return SimpleMemoryCache()

    url = os.environ.get(cfg.url_env)  # type: ignore[union-attr]
    if not url:
        raise ConfigError(
            f"[cache] type={cfg.type!r} requires the {cfg.url_env!r} "
            f"environment variable to hold the connection URL"
        )
    if isinstance(cfg, RedisCacheConfig):
        from aiocache import Cache

        return Cache.from_url(url)  # type: ignore[return-value]
    if isinstance(cfg, SqlAlchemyCacheConfig):
        from piighost.cache.sqlalchemy import SQLAlchemyCache

        return SQLAlchemyCache(url=url, table_name=cfg.table_name)
    raise ConfigError(f"unknown cache type: {cfg.type!r}")
```

Add the model imports at the top (`from piighost.config.models.cache import MemoryCacheConfig, RedisCacheConfig, SqlAlchemyCacheConfig`) and a `TYPE_CHECKING` import for `BaseCache` (`from aiocache import BaseCache`). For the redis namespace: `Cache.from_url` accepts query params in the URL; pass `namespace` by appending it via the constructor instead if `from_url` does not expose it — check `aiocache.Cache.from_url` signature and use `Cache.from_url(url)` then set `cache.namespace = cfg.namespace` if supported, otherwise drop the namespace field from the config model (verify before finalizing; keep the model and builder consistent with what aiocache 0.12.3 actually supports).

- [ ] **Step 6: Wire into `build_pipeline`** in `src/piighost/config/loader.py` (after the anonymizer build):

```python
    cache = build_cache(cfg.cache)
```
and pass `cache=cache,` to the `ThreadAnonymizationPipeline(...)` call. Import `build_cache` alongside the other builders.

- [ ] **Step 7: New extra in `pyproject.toml`** (`[project.optional-dependencies]`):

```toml
redis = [
    "aiocache[redis]>=0.12",
]
```
and append `redis` inside the `all` extra list. Add `redis` to the dev dependency-groups as well (`redis = ["aiocache[redis]>=0.12"]`) and run `uv sync --group redis` so the test importing `RedisCache` passes.

- [ ] **Step 8: Run** `uv run pytest tests/config/ -v` then the full suite `uv run pytest`. Also `uv run pytest tests/test_core_no_extras.py -v` (cache models are config-side; core must stay clean).

- [ ] **Step 9: Commit**

```bash
git add src/piighost/config pyproject.toml uv.lock tests/config/test_cache_config.py
git commit -m "feat(config): [cache] TOML section (memory/redis/sqlalchemy) with env-var URL indirection"
```

---

### Task A2: public APIs replacing piighost-api's private accesses + `PIIGhostClient.forget_thread`

**Files:**
- Modify: `src/piighost/pipeline/thread.py` (`detect_entities` thread_id override, `get_resolved_tokens`)
- Modify: `src/piighost/pipeline/base.py` (`observation` property)
- Modify: `src/piighost/client.py` (`forget_thread`)
- Test: `tests/pipeline/test_public_surface.py` (create), `tests/test_client.py` (extend)

- [ ] **Step 1: Write the failing tests** — create `tests/pipeline/test_public_surface.py`:

```python
"""Public APIs consumed by piighost-api (replacing private-attribute access)."""

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.observation.base import NoOpObservationService
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline:
    return ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
    )


async def test_detect_entities_accepts_thread_id():
    pipe = _pipeline()
    entities = await pipe.detect_entities("Bonjour Patrick", thread_id="t1")
    assert len(entities) == 1
    # The detection result must be cached under the t1 bucket, not "default":
    # override the detection for t1 and re-detect.
    await pipe.override_detections("Bonjour Patrick", [], thread_id="t1")
    assert await pipe.detect_entities("Bonjour Patrick", thread_id="t1") == []
    # Another thread is unaffected (fresh detector run).
    assert len(await pipe.detect_entities("Bonjour Patrick", thread_id="t2")) == 1


async def test_get_resolved_tokens_matches_anonymized_output():
    pipe = _pipeline()
    anonymized, entities = await pipe.anonymize("Bonjour Patrick", thread_id="t")
    tokens = pipe.get_resolved_tokens("t")
    assert list(tokens.values()) == ["<<PERSON:1>>"]
    entity = next(iter(tokens))
    assert entity.canonical == "patrick"


def test_observation_property_is_settable():
    pipe = _pipeline()
    svc = NoOpObservationService()
    pipe.observation = svc
    assert pipe.observation is svc
```

And append to `tests/test_client.py` (mirror the file's existing mock-transport style for other endpoints):

```python
async def test_forget_thread_calls_delete_endpoint():
    # Reuse the file's httpx.MockTransport pattern: assert the client
    # sends DELETE /v1/threads/{thread_id} and accepts a 204.
    ...
```
(Write it concretely against the file's existing fixtures: read `tests/test_client.py` first and copy the established transport-mock idiom; the assertion is method == "DELETE" and path == "/v1/threads/t1".)

- [ ] **Step 2: Run** both test files — FAIL (unexpected kwarg `thread_id`, missing attributes).

- [ ] **Step 3: Implement in `src/piighost/pipeline/thread.py`:**

```python
    async def detect_entities(
        self, text: str, thread_id: str = "default"
    ) -> list[Entity]:
        """Run the detection pipeline with thread-scoped caching.

        Same stages as the base implementation; the ``thread_id`` scopes
        the detection cache so ``override_detections`` corrections apply.
        """
        token = _current_thread_id.set(thread_id)
        try:
            return await super().detect_entities(text)
        finally:
            _current_thread_id.reset(token)

    def get_resolved_tokens(self, thread_id: str = "default") -> dict[Entity, str]:
        """Placeholder token per resolved entity for *thread_id*.

        The same mapping the pipeline uses when rendering, exposed for
        API consumers that serialize entities with their placeholders.
        """
        token_map, _ = self._resolved_token_pairs(thread_id)
        return token_map
```

- [ ] **Step 4: Implement the `observation` property in `src/piighost/pipeline/base.py`:**

```python
    @property
    def observation(self) -> AbstractObservationService:
        """The observation backend emitting per-stage trace spans."""
        return self._observation

    @observation.setter
    def observation(self, service: AbstractObservationService) -> None:
        self._observation = service
```

- [ ] **Step 5: Implement `forget_thread` in `src/piighost/client.py`** (after `deanonymize_with_ent`):

```python
    async def forget_thread(self, thread_id: str) -> None:
        """Erase every server-side trace of *thread_id* (memory + cache).

        Maps to ``DELETE /v1/threads/{thread_id}`` on piighost-api.
        Idempotent server-side; any non-2xx response raises.
        """
        response = await self._client.delete(f"/v1/threads/{thread_id}")
        response.raise_for_status()
```

- [ ] **Step 6: Run** `uv run pytest tests/pipeline/test_public_surface.py tests/test_client.py -v` then the full suite; ruff + pyrefly on touched files.

- [ ] **Step 7: Commit**

```bash
git add src/piighost tests
git commit -m "feat(pipeline): public detect_entities(thread_id)/get_resolved_tokens/observation; client forget_thread"
```

---

### Task A3: merge phase A and prepare (not push) the release

- [ ] **Step 1:** `uv run pytest && make lint` on the branch — green (lint: only the known pre-existing noise).
- [ ] **Step 2:** `git checkout master && git merge feat/cache-config && uv run pytest` — green; `git branch -d feat/cache-config`.
- [ ] **Step 3:** Read `.github/workflows/release.yml` to confirm the publish trigger (expected: tag push). Run `uv run cz bump --dry-run` and report the computed version (expected: minor bump with the BREAKING CHANGE footers from the core overhaul producing what commitizen decides under major_version_zero).
- [ ] **Step 4: STOP — release gate.** Do NOT run `cz bump`, do NOT push. Report to the controller: master state, dry-run version, and what the human must run (`uv run cz bump && git push && git push --tags`). Phases B and C proceed against the local editable lib regardless.

---

## Phase B — piighost-api (branch `feat/hardening`, created off master)

Setup for every task in this phase: `cd ~/PycharmProjects/piighost-api`, create/stay on `feat/hardening`, and run `make dev-local` once so piighost resolves to the local editable checkout. ALWAYS run tests with `uv run --no-sync pytest` (a plain `uv run` re-syncs piighost back to PyPI and invalidates the editable install).

### Task B1: consume the new public lib surface; dynamic version; manifest-based health

**Files:**
- Modify: `src/piighost_api/app.py`
- Modify: `pyproject.toml` (pin `piighost[config]>=0.14`)
- Test: `tests/test_app.py` (adapt mocks)

- [ ] **Step 1: Write/adapt the failing tests.** In `tests/test_app.py` add:

```python
def test_index_reports_package_version(client):
    body = client.get("/").json()
    from importlib.metadata import version
    assert body["version"] == version("piighost-api")


def test_health_reports_manifest_detectors(client):
    body = client.get("/health").json()
    # Manifest-based, not pipeline._detector: the mock manifest declares
    # its detector types (see conftest mock_manifest).
    assert body["detector"]
```

Then check `tests/conftest.py`: the `mock_pipeline` must now also provide `detect_entities = AsyncMock(...)` accepting `thread_id`, and `get_resolved_tokens = MagicMock(return_value={...})`; adapt the existing fixtures accordingly (read the file first).

- [ ] **Step 2:** Run `uv run --no-sync pytest tests/test_app.py -v` — new tests FAIL (version "0.1.0", detector from `_detector`).

- [ ] **Step 3: Implement in `src/piighost_api/app.py`:**

1. Delete `from piighost.pipeline.thread import ThreadAnonymizationPipeline, _current_thread_id` → `from piighost.pipeline.thread import ThreadAnonymizationPipeline`.
2. `/v1/detect` body becomes:
```python
        entities = await pipeline.detect_entities(data.text, thread_id=data.thread_id)
        return DetectResponse(entities=_serialize_entities_plain(entities))
```
3. Observation wiring: `pipeline.observation = observation` instead of `pipeline._observation = ...`.
4. `_serialize_entities` uses the public token API:
```python
def _serialize_entities(
    entities: list[Entity],
    pipeline: ThreadAnonymizationPipeline,
    thread_id: str,
) -> list[EntitySchema]:
    """Serialize piighost entities with their placeholder tokens."""
    tokens = pipeline.get_resolved_tokens(thread_id)
    token_lookup = {ent.canonical_key: tok for ent, tok in tokens.items()}
    result: list[EntitySchema] = []
    for entity in entities:
        placeholder = token_lookup.get(entity.canonical_key, "")
        ...
```
(keep the rest of the body identical).
5. Version: module-level
```python
from importlib.metadata import version as _pkg_version

API_VERSION = _pkg_version("piighost-api")
```
used in `IndexResponse(version=API_VERSION, ...)` and `OpenAPIConfig(version=API_VERSION, ...)`.
6. Health from the manifest:
```python
        return HealthResponse(
            status="ok",
            detector=", ".join(d.type for d in manifest.detectors) or "none",
        )
```
7. `pyproject.toml`: `piighost[config]>=0.14` (note in the commit body: lock refresh happens after the lib is published; local tests run against the editable install).

- [ ] **Step 4:** `uv run --no-sync pytest -v` — all green. Confirm `grep -rn "_current_thread_id\|_observation\|_detector" src/` returns nothing (the `_detector` health access must be gone).

- [ ] **Step 5: Commit**

```bash
git add src tests pyproject.toml
git commit -m "refactor(api)!: consume public piighost surface; dynamic version; manifest health" -m "BREAKING CHANGE: requires piighost >= 0.14."
```

---

### Task B2: forget endpoint

**Files:**
- Modify: `src/piighost_api/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Failing tests:**

```python
def test_forget_thread_returns_204(client, mock_pipeline):
    res = client.delete("/v1/threads/t1")
    assert res.status_code == 204
    mock_pipeline.forget_thread.assert_awaited_once_with("t1")
```
(Add `forget_thread = AsyncMock()` to the conftest mock pipeline.)

- [ ] **Step 2:** Run — FAIL (404, no route).

- [ ] **Step 3: Implement** in `app.py` (next to the other handlers; `delete` imported from litestar):

```python
    @delete("/v1/threads/{thread_id:str}")
    async def forget_thread(thread_id: str) -> None:
        """Erase every trace of a conversation: memory and cached mappings.

        Backed by ``ThreadAnonymizationPipeline.forget_thread`` (right to
        be forgotten). Idempotent.
        """
        await pipeline.forget_thread(thread_id)
```
Register `forget_thread` in `route_handlers`. The route is auth-guarded by default (no `exclude_from_auth`).

- [ ] **Step 4:** `uv run --no-sync pytest -v` — green.

- [ ] **Step 5: Commit:** `git add -A src tests && git commit -m "feat(api): DELETE /v1/threads/{thread_id} purge endpoint (right to be forgotten)"`

---

### Task B3: fail-fast auth + request limits

**Files:**
- Modify: `src/piighost_api/app.py`
- Modify: `tests/conftest.py` (anonymous mode for existing tests)
- Test: `tests/test_auth.py`, `tests/test_app.py`

- [ ] **Step 1: Failing tests** (append to `tests/test_auth.py`):

```python
def test_startup_fails_without_keys_by_default(monkeypatch, mock_pipeline, mock_manifest, tmp_path):
    """No API keys and no explicit anonymous opt-in: the app must refuse to start."""
    monkeypatch.delenv("PIIGHOST_ALLOW_ANONYMOUS", raising=False)
    # Build the app with the standard patching used by the app fixture,
    # then entering TestClient (which runs the lifespan) must raise.
    ...


def test_startup_allows_anonymous_with_explicit_opt_in(monkeypatch, ...):
    monkeypatch.setenv("PIIGHOST_ALLOW_ANONYMOUS", "true")
    # TestClient enters cleanly, routes respond without Authorization.
    ...
```
Write these concretely against the existing fixture style (read `tests/conftest.py` and `tests/test_auth.py` first; the app fixture patches `load_pipeline`). Then update `tests/conftest.py` so the default `app`/`client` fixtures set `PIIGHOST_ALLOW_ANONYMOUS=true` (preserving the behavior every existing route test relies on).

And in `tests/test_app.py`:

```python
def test_oversized_body_is_rejected(client):
    res = client.post("/v1/anonymize", json={"text": "x" * 2_000_000})
    assert res.status_code == 413
```

- [ ] **Step 2:** Run — FAIL.

- [ ] **Step 3: Implement in `app.py`:**

In `lifespan`, replace the fail-open except:

```python
        try:
            await svc_api_keys.load_dotenv()
            guards.append(create_auth_guard(svc_api_keys))
            logger.info("API keys loaded — auth enabled")
        except Exception as exc:
            if os.getenv("PIIGHOST_ALLOW_ANONYMOUS", "").strip().lower() not in (
                "1",
                "true",
                "yes",
                "on",
            ):
                raise RuntimeError(
                    "No valid API keys found and PIIGHOST_ALLOW_ANONYMOUS is not "
                    "set. Refusing to serve PII endpoints unauthenticated; set "
                    "API_KEY_<name> entries or explicitly opt in to anonymous "
                    "mode with PIIGHOST_ALLOW_ANONYMOUS=true."
                ) from exc
            logger.warning("Anonymous mode enabled (%s) — auth disabled", exc)
```

Body limit + opt-in rate limit on the app constructor:

```python
    max_body = int(os.getenv("PIIGHOST_MAX_BODY_BYTES", "1000000"))

    rate_limit_config = None
    rate_limit_env = os.getenv("PIIGHOST_RATE_LIMIT", "")
    if rate_limit_env:
        # Format: "<unit>:<count>", e.g. "minute:300".
        unit, _, count = rate_limit_env.partition(":")
        from litestar.middleware.rate_limit import RateLimitConfig

        rate_limit_config = RateLimitConfig(
            rate_limit=(unit, int(count)),  # type: ignore[arg-type]
            exclude=["/health", "/"],
        )

    return Litestar(
        ...,
        request_max_body_size=max_body,
        middleware=[rate_limit_config.middleware] if rate_limit_config else [],
    )
```
(Verify the exact Litestar 2.21 kwarg spellings: `request_max_body_size` on `Litestar`, `RateLimitConfig(rate_limit=("minute", 300))`, and that the oversized-body status is 413; adjust the test to the actual status code Litestar emits if different, e.g. 400 — the contract is "rejected, not processed".)

Document the three env vars in the README configuration table if one exists (check `README.md`).

- [ ] **Step 4:** `uv run --no-sync pytest -v` — green.

- [ ] **Step 5: Commit:** `git add -A src tests README.md && git commit -m "feat(api)!: fail-fast auth with PIIGHOST_ALLOW_ANONYMOUS opt-out; body size and rate limits" -m "BREAKING CHANGE: the server now refuses to start without API keys unless PIIGHOST_ALLOW_ANONYMOUS=true."`

---

### Task B4: wire Redis through the TOML; align compose

**Files:**
- Modify: `pipeline.toml`
- Modify: `docker-compose.yml` (only if env wiring is missing)
- Modify: `README.md` (cache documentation)
- Test: manual verification commands (no docker build)

- [ ] **Step 1:** Append to `pipeline.toml`:

```toml
[cache]
type = "redis"
url_env = "REDIS_URL"
```

- [ ] **Step 2:** Verify the compose already passes `REDIS_URL` to the api service (it does: `REDIS_URL=${REDIS_URL:-redis://redis:6379}`); nothing to change unless missing.

- [ ] **Step 3:** Validation without Redis must now fail loudly at serve time and pass at validate time: run `uv run --no-sync piighost validate pipeline.toml` (schema-valid) and a startup probe:

```bash
REDIS_URL= uv run --no-sync python -c "
from pathlib import Path
from piighost.config import load_pipeline
try:
    load_pipeline(Path('pipeline.toml'))
    print('UNEXPECTED: loaded without REDIS_URL')
except Exception as e:
    print('ok, fails loudly:', type(e).__name__, e)
"
REDIS_URL=redis://localhost:6399 uv run --no-sync python -c "
from pathlib import Path
from piighost.config import load_pipeline
p, _ = load_pipeline(Path('pipeline.toml'))
print('cache backend:', type(p._cache).__name__)
"
```
Expected: first prints the ConfigError mentioning REDIS_URL; second prints `RedisCache` (no connection is made at construction).

- [ ] **Step 4:** README: document that the API now genuinely uses Redis when `[cache] type = "redis"` is present, that `REDIS_URL` is mandatory in that case, and that bare-local runs can simply omit the `[cache]` section (memory).

- [ ] **Step 5: Commit:** `git add pipeline.toml README.md && git commit -m "feat(api): wire the Redis cache for real via the [cache] TOML section"`

---

### Task B5: phase B review checkpoint

- [ ] Run `uv run --no-sync pytest` (full), `make lint`. Report counts. Leave the branch UNMERGED (merge decision belongs to the human along with the release gate, since CI cannot resolve `piighost>=0.14` until publication).

---

## Phase C — piighost-chat (branch `feat/pii-chain`)

Setup: `cd ~/PycharmProjects/piighost-chat`, check the default branch name, create `feat/pii-chain`. The backend resolves piighost editable from `../../piighost` by default (`[tool.uv.sources]`), so the new client method is available. Backend commands run from `backend/`.

### Task C1: forget chain on thread deletion and TTL cleanup

**Files:**
- Modify: `backend/src/piighost_chat/app.py` (delete_thread)
- Modify: `backend/src/piighost_chat/worker.py` (cleanup task)
- Test: `backend/tests/test_forget_chain.py` (create; first test file of the repo, create `backend/tests/__init__.py` if pytest needs it — it should not with rootdir config)

- [ ] **Step 1: Failing tests** — create `backend/tests/test_forget_chain.py`:

```python
"""Thread deletion must purge PII mappings in piighost-api, not just checkpoints."""

from unittest.mock import AsyncMock

from piighost_chat import worker


async def test_cleanup_calls_forget_for_each_stale_thread(monkeypatch):
    fake_client = AsyncMock()
    monkeypatch.setattr(worker, "_build_pii_client", lambda: fake_client)
    monkeypatch.setattr(worker, "list_stale_thread_ids", AsyncMock(return_value=["a", "b"]))
    monkeypatch.setattr(worker, "delete_thread_data", AsyncMock())

    class FakeConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    async def fake_connect(url):
        return FakeConn()

    monkeypatch.setattr(worker.psycopg.AsyncConnection, "connect", fake_connect)

    await worker.cleanup_stale_threads()

    assert fake_client.forget_thread.await_count == 2
    fake_client.forget_thread.assert_any_await("a")
    fake_client.forget_thread.assert_any_await("b")
    fake_client.close.assert_awaited()
```

(Adapt the monkeypatching to the real call shape after reading `worker.py`; the contract under test: every deleted stale thread also gets `forget_thread`, and the client is closed.)

- [ ] **Step 2:** Run `cd backend && uv run pytest tests/ -v` — FAIL (`_build_pii_client` missing).

- [ ] **Step 3: Implement.**

`worker.py` gains:

```python
from piighost.client import PIIGhostClient


def _build_pii_client() -> PIIGhostClient:
    """Client for the forget-thread purge calls, built per cleanup run."""
    return PIIGhostClient(
        os.getenv("PIIGHOST_API_URL", "http://piighost-api:8000"),
        api_key=os.getenv("PIIGHOST_API_KEY", ""),
    )
```

and in `cleanup_stale_threads`, after deleting checkpoint rows for each thread, purge the PII side (client built once per run, closed in a finally; a failing forget logs a warning with the thread id and continues, so PostgreSQL cleanup still completes):

```python
        client = _build_pii_client()
        try:
            for tid in stale_ids:
                await delete_thread_data(conn, tid)
                try:
                    await client.forget_thread(tid)
                except Exception:
                    logger.warning(
                        "cleanup_stale_threads: piighost forget failed for %s "
                        "(mappings expire via the API cache TTL)",
                        tid,
                        exc_info=True,
                    )
                logger.info("cleanup_stale_threads: deleted thread %s", tid)
        finally:
            await client.close()
```

`app.py` `delete_thread` becomes:

```python
    @delete("/api/threads/{thread_id:str}")
    async def delete_thread(thread_id: str) -> None:
        async with await psycopg.AsyncConnection.connect(pg_url) as conn:
            await delete_thread_data(conn, thread_id)
        try:
            await pii_client.forget_thread(thread_id)
        except Exception:
            logger.warning(
                "piighost forget failed for thread %s (mappings expire via TTL)",
                thread_id,
                exc_info=True,
            )
```

- [ ] **Step 4:** `uv run pytest tests/ -v` — green.

- [ ] **Step 5: Commit:** `git add backend && git commit -m "feat(chat): purge piighost mappings on thread deletion and TTL cleanup"`

---

### Task C2: prompt format, log redaction, generic error responses, CORS env

**Files:**
- Modify: `backend/src/piighost_chat/app.py`
- Test: `backend/tests/test_app_hardening.py` (create)

- [ ] **Step 1: Failing tests:**

```python
"""Prompt format, error-response redaction and CORS configuration."""

from piighost_chat.app import SYSTEM_PROMPT, _cors_origins


def test_system_prompt_uses_real_placeholder_format():
    assert "<<PERSON:1>>" in SYSTEM_PROMPT
    assert "<<PERSON_1>>" not in SYSTEM_PROMPT


def test_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.example, https://b.example")
    assert _cors_origins() == ["https://a.example", "https://b.example"]
    monkeypatch.delenv("CORS_ALLOW_ORIGINS")
    assert _cors_origins() == ["*"]
```

Plus an exception-handler test if feasible without the full lifespan (the handler is defined inside `create_app`; extract it to module level as `handle_exception(request, exc)` so it can be unit-tested):

```python
def test_internal_errors_are_not_echoed_to_the_client():
    from piighost_chat.app import handle_exception
    from unittest.mock import MagicMock

    request = MagicMock()
    request.method, request.url.path = "GET", "/x"
    resp = handle_exception(request, RuntimeError("secret connection string"))
    assert resp.status_code == 500
    assert b"secret" not in resp.render_bytes() if hasattr(resp, "render_bytes") else True
    assert resp.content["detail"] == "Internal Server Error"
```
(Adapt the response-content assertion to Litestar's `Response` object shape; the contract: a non-HTTPException yields `detail == "Internal Server Error"` and never `str(exc)`.)

- [ ] **Step 2:** Run — FAIL.

- [ ] **Step 3: Implement in `app.py`:**

1. `SYSTEM_PROMPT`: replace `<<PERSON_1>>, <<CITY_1>>` with `<<PERSON:1>>, <<LOCATION:1>>` (and re-read the whole prompt for other underscore-format mentions).
2. `send_email` log line becomes PII-free:
```python
    logging.info(
        "[EMAIL SENT] to=<redacted> subject_len=%d body_len=%d", len(subject), len(body)
    )
```
3. Extract and harden the exception handler at module level:
```python
def handle_exception(request: Request, exc: Exception) -> Response:
    """Log the full exception server-side; never echo internals to the client."""
    if isinstance(exc, HTTPException):
        status, detail = exc.status_code, exc.detail
    else:
        status, detail = HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error"
    logger.exception(
        "Unhandled error on %s %s -> %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return Response(
        media_type="application/json",
        status_code=status,
        content={"status_code": status, "detail": detail},
    )
```
4. CORS from env:
```python
def _cors_origins() -> list[str]:
    """Comma-separated CORS_ALLOW_ORIGINS, defaulting to * for local dev."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
```
used in `CORSConfig(allow_origins=_cors_origins(), ...)`. Document `CORS_ALLOW_ORIGINS` in `.env.example`.

- [ ] **Step 4:** `uv run pytest tests/ -v` — green.

- [ ] **Step 5: Commit:** `git add backend .env.example && git commit -m "fix(chat): correct placeholder format in prompt; redact logs and error responses; CORS from env"`

---

### Task C3: SSE correctness (multi-line content end to end)

**Files:**
- Modify: `backend/src/piighost_chat/app.py` (chunk content normalization)
- Modify: `frontend/src/services/api.ts` (spec-compliant SSE event parsing)
- Test: `backend/tests/test_sse_content.py` (create); frontend verified by a scratch node script (no test infra exists; do not add one)

- [ ] **Step 1: Backend failing test** — create `backend/tests/test_sse_content.py`:

```python
"""LLM chunk content must be normalized to text before SSE emission."""

from piighost_chat.app import _chunk_text


def test_string_content_passthrough():
    assert _chunk_text("hello") == "hello"


def test_block_list_content_is_joined():
    blocks = [{"type": "text", "text": "hel"}, {"type": "text", "text": "lo"}]
    assert _chunk_text(blocks) == "hello"


def test_non_text_blocks_are_skipped():
    blocks = [{"type": "tool_use", "id": "x"}, {"type": "text", "text": "ok"}]
    assert _chunk_text(blocks) == "ok"
```

- [ ] **Step 2:** Run — FAIL (no `_chunk_text`).

- [ ] **Step 3: Implement in `app.py`:**

```python
def _chunk_text(content: object) -> str:
    """Normalize an AIMessageChunk content to plain text.

    LangChain chunk content is either a string or a list of content
    blocks; only text blocks carry displayable output.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""
```

and in the `chat` route generator:

```python
                if isinstance(chunk, AIMessageChunk):
                    text = _chunk_text(chunk.content)
                    if text:
                        yield ServerSentEventMessage(data=text)
```

- [ ] **Step 4: Frontend parser fix** in `frontend/src/services/api.ts`, replace the line loop of `streamChat` with a spec-compliant event accumulator (SSE encodes a newline inside `data` as multiple `data:` lines within one event, terminated by a blank line; the old code yielded each `data:` line separately and dropped the newlines):

```typescript
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventData: string[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, "");
      if (line === "") {
        // Blank line terminates the event; data lines join with \n per SSE spec.
        if (eventData.length > 0) {
          yield eventData.join("\n");
          eventData = [];
        }
      } else if (line.startsWith("data:")) {
        eventData.push(line.slice(5).replace(/^ /, ""));
      }
    }
  }
  if (eventData.length > 0) {
    yield eventData.join("\n");
  }
```

- [ ] **Step 5: Verify the parser logic** with a scratch node script (then delete it): feed it `"data: line1\ndata: line2\n\ndata: solo\n\n"` chunked at awkward boundaries and assert the yields are `["line1\nline2", "solo"]`. Use `node --experimental-strip-types` or plain JS transliteration of the loop.

- [ ] **Step 6:** Backend: `uv run pytest tests/ -v` green. Frontend: `cd frontend && npm run build` (type-checks the change).

- [ ] **Step 7: Commit:** `git add backend frontend && git commit -m "fix(chat): preserve newlines and block content through the SSE stream"`

---

### Task C4: phase C checkpoint

- [ ] `cd backend && uv run pytest && uv run ruff check src tests && uv run pyrefly check` — report counts (first tests of this repo: expect a small green suite). `cd ../frontend && npm run build` green. Leave `feat/pii-chain` UNMERGED (same gate as phase B: the human merges after the lib release lands and locks refresh).

---

## Post-release follow-ups (for the human, after `cz bump` + push + publish)

1. piighost-api: `uv lock --upgrade-package piighost && uv run pytest` on `feat/hardening`, merge, rebuild/push the ghcr image.
2. piighost-chat: `uv lock` refresh in `backend/` (PyPI mode via `--no-sources` is what CI/docker use), merge `feat/pii-chain`.
3. Update the chat compose images once the new piighost-api image exists.
