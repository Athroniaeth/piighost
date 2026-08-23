"""Deprecated alias for piighost.integrations.langchain.middleware.

Kept so existing imports keep working; importing the parent package emits the
DeprecationWarning. Prefer piighost.integrations.langchain.
"""

from piighost.integrations.langchain.middleware import PIIAnonymizationMiddleware

__all__ = ["PIIAnonymizationMiddleware"]
