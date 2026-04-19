---
icon: lucide/container
---

# Deploying `piighost-api`

[`piighost-api`](https://github.com/Athroniaeth/piighost-api) ships as a Docker image on `ghcr.io/athroniaeth/piighost-api`. The base image (~218 MB) only bundles regex detectors. To use NER-based detectors (GLiNER2, spaCy, transformers) or integration extras (Faker, etc.), you install them through one of the two extras channels:

- **`EXTRA_PACKAGES`** (runtime): read at container startup, `uv` installs the listed extras before the server boots.
- **`PIIGHOST_EXTRAS`** (build time): baked into a custom image via `docker build --build-arg PIIGHOST_EXTRAS="gliner2"`.

The runtime channel is convenient for prototyping but pulls hundreds of MB of wheels (`torch`, `nvidia-*`, `triton`, `transformers`, …) every time the container starts. The strategies below let you amortise that cost.

---

## Caching optional packages

### Strategy 1 — Cache the `uv` download directory (recommended quick win)

Add a named volume on `/root/.cache/uv`. `uv` keeps every wheel it has ever downloaded there; on the next start, it skips the network and only re-links the files into the container's venv. Typical cold-start time drops from several minutes to a handful of seconds, without touching the image.

```yaml
services:
  api:
    image: ghcr.io/athroniaeth/piighost-api:latest
    environment:
      - EXTRA_PACKAGES=piighost[gliner2]
    volumes:
      - ./pipeline.py:/app/pipeline.py
      - huggingface-cache:/root/.cache/huggingface  # model weights
      - uv-cache:/root/.cache/uv                    # Python wheels

volumes:
  huggingface-cache:
  uv-cache:
```

!!! note
    The `huggingface-cache` volume caches downloaded model weights (GLiNER2, transformers models). It is independent from the wheel cache and should be kept.

### Strategy 2 — Bake the extras into a custom image (zero runtime install)

For environments where startup time matters (CI, production, serverless), build your own image on top of `piighost-api`. The `uv sync` runs once at `docker build`, the extras are baked into an image layer, and every subsequent container start is instant.

```dockerfile
# Dockerfile
FROM ghcr.io/athroniaeth/piighost-api:latest
RUN uv pip install --system "piighost[gliner2]"
```

```yaml
# compose.yml
services:
  api:
    build: ./piighost-api
    volumes:
      - ./pipeline.py:/app/pipeline.py
      - huggingface-cache:/root/.cache/huggingface
    # EXTRA_PACKAGES is no longer needed
```

This is the most reproducible option: the image is self-contained, Docker's layer cache handles rebuilds, and there is no runtime dependency on PyPI availability.

### Strategy 3 — Mount the whole venv (fastest startup, more fragile)

Mount a named volume on the image's venv path so the installed files themselves persist across runs. Startup is effectively instantaneous after the first boot, at the cost of a cache that can silently desync if the upstream image changes Python version or venv layout.

```yaml
services:
  api:
    image: ghcr.io/athroniaeth/piighost-api:latest
    environment:
      - EXTRA_PACKAGES=piighost[gliner2]
    volumes:
      - piighost-venv:/app/.venv

volumes:
  piighost-venv:
```

!!! warning
    If you upgrade `ghcr.io/athroniaeth/piighost-api:latest`, purge the venv volume (`docker compose down -v`) before the next start — otherwise the old venv shadows the new one and you will debug mysterious version mismatches.

---

## Which one should I pick?

| Scenario                               | Recommended strategy               |
| -------------------------------------- | ---------------------------------- |
| Local development, occasional restarts | Strategy 1 (`uv` cache volume)     |
| CI / production / fixed versions       | Strategy 2 (custom image)          |
| Fast dev loop on a pinned base image   | Strategy 3 (venv volume)           |

Strategies 1 and 2 compose well: keep the `uv` cache on your dev machine to speed up `docker build`, and bake the extras into the image for deployment.
