"""Marker types describing how much information a placeholder preserves.

Placeholder factories differ in what they keep of an entity after
replacement.  Some produce a distinct, reversible token per entity;
others collapse every entity of the same label into the same string;
others leak part of the original value.  The consumers of a factory
(anonymizer, pipeline, middleware) often care about this level of
preservation: for instance, ``PIIAnonymizationMiddleware`` in anything
other than :class:`~piighost.middleware.ToolCallStrategy.PASSTHROUGH`
mode requires placeholders that uniquely identify each entity so
arguments can be deanonymised reliably.

The tags declared here are **phantom** types: they exist only for the
type checker.  They attach a "preservation level" to a factory class
via a generic parameter, so an incompatible combination (e.g. passing
a :class:`~piighost.placeholder.RedactPlaceholderFactory`-based
pipeline to the middleware) becomes a static error instead of a
runtime surprise.

Taxonomy, from most to least information preserved:

* :class:`PreservesIdentity` — the token uniquely identifies an entity.
  Safe for every tool-call strategy.
  Examples: ``<<PERSON_1>>``, ``<PERSON:a1b2c3d4>``.
* :class:`PreservesLabel` — the token only carries the label; two
  different persons collide into ``<PERSON>``.  Unsafe for tool-call
  strategies that deanonymise arguments.
* :class:`PreservesShape` — the token keeps part of the original value
  (e.g. ``p***@mail.com``).  Unsafe for the middleware because two
  different originals can yield the same masked token, and the masked
  token can collide with a real value in a tool response.
* :class:`PreservesNothing` — the token is a constant marker
  (e.g. ``[REDACT]``).  All entities collapse; deanonymisation is
  impossible.

Tags are disjoint: ``PreservesIdentity`` is not a subtype of
``PreservesLabel``.  Factories pick exactly one.
"""


class PlaceholderPreservation:
    """Root marker for placeholder preservation tags.

    Subclasses are used as phantom type parameters on
    :class:`~piighost.placeholder.AnyPlaceholderFactory` and on the
    anonymizer/pipeline types that carry a factory.
    """


class PreservesIdentity(PlaceholderPreservation):
    """The placeholder uniquely identifies each entity.

    Two distinct entities always get distinct tokens, and the same
    entity seen twice gets the same token.  This is the only level
    safe with :class:`~piighost.middleware.ToolCallStrategy.FULL` and
    :class:`~piighost.middleware.ToolCallStrategy.INBOUND_ONLY`.
    """


class PreservesLabel(PlaceholderPreservation):
    """The placeholder preserves only the entity label.

    Different entities sharing a label collide into the same token
    (``<PERSON>``).  Suitable for one-shot redaction but cannot be
    reversed, which rules it out for the middleware's tool-call
    handling outside of
    :class:`~piighost.middleware.ToolCallStrategy.PASSTHROUGH`.
    """


class PreservesShape(PlaceholderPreservation):
    """The placeholder preserves part of the original value.

    The masked form (``p***@mail.com``) can collide with other
    entities and even with real values in a tool response, so it is
    unsafe for deanonymisation and for tool-call strategies that rely
    on token uniqueness.
    """


class PreservesNothing(PlaceholderPreservation):
    """The placeholder is a constant marker carrying no information.

    Every entity collapses to the same token (e.g. ``[REDACT]``).
    Deanonymisation is not possible; only use with
    :class:`~piighost.middleware.ToolCallStrategy.PASSTHROUGH` or
    outside the middleware entirely.
    """


def get_preservation_tag(factory: object) -> type[PlaceholderPreservation] | None:
    """Return the preservation tag a factory class advertises, if any.

    Walks the MRO of ``type(factory)`` looking for a generic base
    ``AnyPlaceholderFactory[<tag>]`` and returns the tag class. Returns
    ``None`` when no tag can be recovered (untyped factory, or a
    factory that does not subclass the generic protocol).

    This utility powers the runtime check performed by
    :class:`~piighost.pipeline.thread.ThreadAnonymizationPipeline`: it
    mirrors the static-typing constraint without duplicating the list
    of rejected factory classes.
    """
    from typing import get_args, get_origin

    # Imported lazily to avoid a cycle with ``piighost.placeholder``.
    from piighost.placeholder import AnyPlaceholderFactory

    for base in type(factory).__mro__:
        for orig in getattr(base, "__orig_bases__", ()):
            if get_origin(orig) is not AnyPlaceholderFactory:
                continue
            args = get_args(orig)
            if (
                args
                and isinstance(args[0], type)
                and issubclass(args[0], PlaceholderPreservation)
            ):
                return args[0]
    return None


__all__ = [
    "PlaceholderPreservation",
    "PreservesIdentity",
    "PreservesLabel",
    "PreservesNothing",
    "PreservesShape",
    "get_preservation_tag",
]
