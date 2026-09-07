---
icon: lucide/arrow-up-circle
---

# Versions and upgrades

`piighost` follows semantic versioning. A patch release changes a behaviour, a minor release adds components or options, and a major release changes the public API. A name marked deprecated keeps working, and keeps resolving to the current implementation, until the next major release.

Check the installed release, then upgrade:

```bash
python -c "import piighost; print(piighost.__version__)"

pip install -U piighost
# or, with uv
uv lock --upgrade-package piighost
```

Every release has an entry in [CHANGELOG.md](https://github.com/Athroniaeth/piighost/blob/master/CHANGELOG.md), with its features, its fixes and its breaking changes.

## Deprecated names

Three names from earlier releases are still importable. They resolve to the current implementation, so nothing breaks today, and they will be removed in a future major release.

| Deprecated | Use instead | Since | On use |
|---|---|---|---|
| `piighost.integrations.middleware` | `piighost.integrations.langchain` | 1.4.0 | `DeprecationWarning` on import |
| `AssistantEntityStrategy` | `EntityCreateByAssistantStrategy` | 1.5.0 | `DeprecationWarning` on access |
| the `piighost[middleware]` extra | `piighost[langchain]` | 1.4.0 | no warning, both install `langchain` |

The old module and the old strategy name reach the same objects as the current ones, so the update is a rewritten import line:

```python
# deprecated, still works
from piighost.integrations.middleware import AssistantEntityStrategy, PIIAnonymizationMiddleware

# current
from piighost.integrations.langchain import EntityCreateByAssistantStrategy, PIIAnonymizationMiddleware
```

Run your test suite with `python -W error::DeprecationWarning` to fail on any deprecated name left in a code base. The current surface is listed in the [LangChain reference](../reference/langchain.md).

## Coming from 0.x

Every release before 1.0.0 exposed a different API, so a 0.x code base is ported by rewriting its setup rather than by renaming imports. What changed:

- imports live under `piighost.components`, `piighost.pipeline`, `piighost.config` and `piighost.integrations`
- a pipeline takes a detector and nothing else, since the linker and the anonymizer have defaults
- the `faker`, `cache`, `langfuse` and `opik` extras are gone, and no stage caches detection results
- the `sqlalchemy` extra came back in 1.2.0, as a conversation memory backend

Restart from the [Quickstart](../getting-started/quickstart.md), then read [First pipeline](../getting-started/first-pipeline.md) for the stages and the [TOML reference](../configuration/toml.md) to move the setup into a config file.
