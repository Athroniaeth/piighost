"""Configuration models: one discriminated-union model family per component.

Each model carries a build() that constructs its core component, so the
composition root is the config models themselves, not a separate builder
registry.
"""
