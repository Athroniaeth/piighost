"""Phantom tags describing how much information a placeholder preserves.

Placeholder factories differ in what survives a replacement. Some emit a
distinct reversible token per entity, some collapse every entity of one label
into the same string, some leak part of the original value. The consumers of a
factory, the anonymizer, the pipeline, and the middleware, care about this
level. The middleware, outside its passthrough mode, needs tokens that uniquely
identify each entity so it can deanonymize arguments reliably.

These tags are phantom types: they exist only for the type checker. Attached to
a factory through a generic parameter, they turn an incompatible combination,
such as handing a label-only factory to the middleware, into a static error
rather than a runtime surprise.

Two independent axes organize the taxonomy:

- Label: does the token reveal the entity type? <PERSON> does, [REDACT] does not.
- Identity: does the token uniquely identify the entity? <<PERSON:1>> does,
  <PERSON> collapses every person into one token.

The four base combinations are four sibling tags under the root
PlaceholderPreservation: PreservesNothing (neither axis), PreservesLabel (label
only), PreservesIdentity (identity only), and PreservesLabeledIdentity (both).
PlaceholderPreservation is the root that accepts any factory; PreservesNothing
is the concrete tag for a token that keeps nothing, such as [REDACT], a sibling
of the other three rather than their parent.

PreservesLabeledIdentity inherits from both PreservesLabel and PreservesIdentity,
so through covariance a consumer typed against either base accepts a
labeled-identity factory. Every PreservesLabeledIdentity is a PreservesLabel and
a PreservesIdentity, but not the reverse.

A realism sub-axis refines PreservesLabeledIdentity, from clearly synthetic
(<<PERSON:1>>) to hashed realistic (a1b2c3d4@anonymized.local) to Faker output
that can collide with real data (john.doe@example.com).

PreservesShape is a special label-extending case: the masked token keeps a
fragment of the original (j***@mail.com), so it implies the label through its
format but does not guarantee uniqueness, which makes it a sibling of identity.

Each tag is a str subclass, so a factory's tokens are instances of its tag: the
token is a real string and carries its preservation level in its own type. That
lets create() return the tag through its covariant type parameter, threading the
level from the factory down to each token it emits.

The full hierarchy:

- PlaceholderPreservation
  - PreservesNothing
  - PreservesLabel
    - PreservesShape
  - PreservesIdentity
    - PreservesIdentityOnly
  - PreservesLabeledIdentity (PreservesLabel, PreservesIdentity)
    - PreservesLabeledIdentityOpaque
    - PreservesLabeledIdentityRealistic
      - PreservesLabeledIdentityHashed
      - PreservesLabeledIdentityFaker
"""


class PlaceholderPreservation(str):
    """Root type for placeholder preservation tags, and for tokens themselves.

    It subclasses str so a token is a real string tagged with what it preserves.
    Subclasses serve both as type parameters on AnyPlaceholderFactory and as the
    concrete type of the tokens a factory emits.
    """


class PreservesNothing(PlaceholderPreservation):
    """The token is a constant marker carrying no information.

    Every entity collapses to the same string, such as [REDACT]. The mapping
    cannot be reversed, so this fits one-shot redaction or the middleware's
    passthrough mode, never its deanonymizing modes.
    """


class PreservesLabel(PlaceholderPreservation):
    """The token preserves the entity label.

    Distinct entities sharing a label collide into the same token, such as
    <PERSON>. This suits one-shot redaction but cannot be reversed, which rules
    it out for the middleware's tool-call handling outside passthrough mode.
    """


class PreservesIdentity(PlaceholderPreservation):
    """The token uniquely identifies each entity.

    Two distinct entities always get distinct tokens, and the same entity seen
    twice gets the same token. This is the abstract base for any
    identity-preserving tag, whether or not the label is also revealed. The
    middleware narrows on this base, accepting every concrete sub-tag through
    covariance.
    """


class PreservesIdentityOnly(PreservesIdentity):
    """The token is a unique reversible id that hides the entity type.

    A token like [a1b2c3d4] carries a per-entity hash but no label, so a reader
    can tell two entities apart while learning nothing about whether they are
    persons, emails, or credit cards. No built-in factory ships this scheme; it
    is the tag for a user factory that hashes without a label prefix.
    """


class PreservesShape(PreservesLabel):
    """The token preserves part of the original value.

    A masked form such as j***@mail.com implies the label through its format,
    but two entities with similar shapes can collide on one token, and a masked
    token can also collide with a real value in a tool response. This makes it
    unsafe for deanonymization that relies on token uniqueness.
    """


class PreservesLabeledIdentity(PreservesLabel, PreservesIdentity):
    """The token reveals both the label and a unique identity.

    It inherits PreservesLabel and PreservesIdentity, so a consumer typed
    against either base accepts a labeled-identity factory. The realism sub-axis
    refines it further, from opaque to realistic.
    """


class PreservesLabeledIdentityOpaque(PreservesLabeledIdentity):
    """Labeled, unique, and clearly synthetic.

    A token like <<PERSON:1>> cannot be confused with real data, reads easily in
    logs, and never coincidentally collides with a real value.
    """


class PreservesLabeledIdentityRealistic(PreservesLabeledIdentity):
    """Labeled, unique, and visually plausible.

    A realistic token passes downstream format validation, an email regex or a
    name pattern, at the cost of looking indistinguishable from a genuine value.
    It is refined by PreservesLabeledIdentityHashed, which is collision-proof,
    and PreservesLabeledIdentityFaker, which can collide with real data.
    """


class PreservesLabeledIdentityHashed(PreservesLabeledIdentityRealistic):
    """A realistic-format token whose content is a hash.

    The token mimics the original format, such as a1b2c3d4@anonymized.local, but
    its content derives from a hash, so it is unique and cannot coincidentally
    match a real-world value.
    """


class PreservesLabeledIdentityFaker(PreservesLabeledIdentityRealistic):
    """A plausible token produced by Faker.

    A token like john.doe@example.com is indistinguishable from genuine data.
    Each entity still maps to a unique token, but a Faker value can land on a
    real person's actual data, which the middleware cannot detect during string
    replacement.
    """


__all__ = [
    "PlaceholderPreservation",
    "PreservesIdentity",
    "PreservesIdentityOnly",
    "PreservesLabel",
    "PreservesLabeledIdentity",
    "PreservesLabeledIdentityFaker",
    "PreservesLabeledIdentityHashed",
    "PreservesLabeledIdentityOpaque",
    "PreservesLabeledIdentityRealistic",
    "PreservesNothing",
    "PreservesShape",
]
