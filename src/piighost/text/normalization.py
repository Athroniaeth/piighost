r"""Space normalization: what counts as a space, and when two values are the same.

A value is often written with a space that is not U+0020. Word and LibreOffice
put a no-break space inside a phone number or before a colon, PDF extraction
yields thin and figure spaces, and East Asian text uses the ideographic space.
A pattern written with " " or with \s under re.ASCII misses all of them, and a
value typed once with each kind of space would get two tokens. This module
holds the one definition every stage shares, so no pattern and no component has
to list those characters itself.
"""

SPACE_SEPARATORS = (
    "\u00a0"  # no-break space
    "\u1680"  # ogham space mark
    "\u2000"  # en quad
    "\u2001"  # em quad
    "\u2002"  # en space
    "\u2003"  # em space
    "\u2004"  # three-per-em space
    "\u2005"  # four-per-em space
    "\u2006"  # six-per-em space
    "\u2007"  # figure space
    "\u2008"  # punctuation space
    "\u2009"  # thin space
    "\u200a"  # hair space
    "\u202f"  # narrow no-break space
    "\u205f"  # medium mathematical space
    "\u3000"  # ideographic space
)
"""Every Unicode space separator other than the ASCII space, each read as one.

The Unicode space separators (category Zs) but U+0020. Written as escapes, since
the characters themselves are invisible in source.
"""

LINE_SEPARATORS = (
    "\u0085"  # next line, a C1 control
    "\u2028"  # line separator
    "\u2029"  # paragraph separator
)
"""Every Unicode line separator other than the ASCII newline, each read as one."""

_TO_ASCII = str.maketrans(
    SPACE_SEPARATORS + LINE_SEPARATORS,
    " " * len(SPACE_SEPARATORS) + "\n" * len(LINE_SEPARATORS),
)
"""Translation table mapping each separator to its ASCII counterpart."""


def normalize_spaces(text: str) -> str:
    r"""Return the text with every Unicode space and line separator made ASCII.

    Each space separator becomes U+0020 and each line separator a newline, one
    character for one, so the result has the length of the text and an offset
    in one is the same offset in the other. A detector matches on the result
    and slices its detections from the original.

    >>> normalize_spaces("06\u00a012\u202f34")
    '06 12 34'
    >>> len(normalize_spaces("a\u3000b")) == len("a\u3000b")
    True
    """
    return text.translate(_TO_ASCII)


def value_key(text: str) -> str:
    r"""Return the identity of a value: its words, one space apart, casefolded.

    Two detected values are the same when they have the same key, whatever
    space separates their words, how many there are, and their case. The key
    only compares values. It is never shown, and never used as an offset.

    >>> value_key("Paul\u00a0Martin") == value_key("paul  MARTIN")
    True
    """
    return " ".join(text.split()).casefold()
