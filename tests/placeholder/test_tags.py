"""Tests for the placeholder preservation tag hierarchy.

The tags are phantom types whose only behavior is their inheritance graph, so
the covariance relied on by the middleware holds. These tests pin that graph:
renaming a tag or breaking an edge fails here.
"""

import pytest

from piighost.placeholder import tags

# Each pair is (tag, ancestor it must inherit from). Breaking an edge, so a
# consumer typed against the ancestor would no longer accept the tag, fails.
SUBCLASS_EDGES: list[tuple[type, type]] = [
    (tags.PreservesNothing, tags.PlaceholderPreservation),
    (tags.PreservesLabel, tags.PlaceholderPreservation),
    (tags.PreservesIdentity, tags.PlaceholderPreservation),
    (tags.PreservesShape, tags.PreservesLabel),
    (tags.PreservesIdentityOnly, tags.PreservesIdentity),
    (tags.PreservesLabeledIdentity, tags.PreservesLabel),
    (tags.PreservesLabeledIdentity, tags.PreservesIdentity),
    (tags.PreservesLabeledIdentityOpaque, tags.PreservesLabeledIdentity),
    (tags.PreservesLabeledIdentityRealistic, tags.PreservesLabeledIdentity),
    (tags.PreservesLabeledIdentityHashed, tags.PreservesLabeledIdentityRealistic),
]

# Pairs that must stay unrelated, so an axis is not accidentally widened. The
# label and identity tags are siblings, and neither descends from Nothing.
NON_SUBCLASS_PAIRS: list[tuple[type, type]] = [
    (tags.PreservesLabel, tags.PreservesIdentity),
    (tags.PreservesIdentity, tags.PreservesLabel),
    (tags.PreservesShape, tags.PreservesIdentity),
    (tags.PreservesIdentityOnly, tags.PreservesLabel),
    (tags.PreservesLabel, tags.PreservesNothing),
    (tags.PreservesIdentity, tags.PreservesNothing),
    (tags.PreservesLabeledIdentity, tags.PreservesNothing),
]


@pytest.mark.parametrize(("tag", "ancestor"), SUBCLASS_EDGES)
def test_tag_inherits_from_ancestor(tag: type, ancestor: type) -> None:
    """Each tag keeps the ancestry the covariance depends on."""
    assert issubclass(tag, ancestor)


@pytest.mark.parametrize(("tag", "other"), NON_SUBCLASS_PAIRS)
def test_axes_stay_independent(tag: type, other: type) -> None:
    """The label and identity axes do not leak into each other."""
    assert not issubclass(tag, other)


def test_labeled_identity_satisfies_both_axes() -> None:
    """A labeled-identity tag is accepted wherever either base is required."""
    assert issubclass(tags.PreservesLabeledIdentity, tags.PreservesLabel)
    assert issubclass(tags.PreservesLabeledIdentity, tags.PreservesIdentity)
