"""Normalise model output before it reaches a PDF.

Models like typographic punctuation — non-breaking hyphens, en dashes, curly
quotes, narrow spaces. They look fine on screen and then a resume parser hands
back "cross‑team" as a token that matches nothing.

A resume is a document whose primary reader is a machine, so everything gets
folded to ASCII on the way in.
"""

from __future__ import annotations

import re

_PUNCT = str.maketrans(
    {
        "‐": "-", "‑": "-", "‒": "-", "–": "-",  # hyphens/dashes
        "—": "-", "―": "-", "−": "-",
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"',
        "…": "...",
        " ": " ", " ": " ", " ": " ", " ": " ", "\u200b": "",
        "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
        "•": "", "‣": "", "●": "",  # stray bullet glyphs; we add our own
    }
)


def clean(text: str) -> str:
    """ASCII-fold punctuation, collapse whitespace, strip leading list markers."""
    out = text.translate(_PUNCT)
    out = re.sub(r"^\s*[-*\u2022]\s+", "", out)
    # Models sometimes detach a suffix the user had glued on: "40 M" -> "40M",
    # "1.2 %" -> "1.2%", "890 ms" -> "890ms". Cosmetic, but it is the user's
    # punctuation being changed under them, and it reads as sloppy on the page.
    out = re.sub(r"(?<=\d) (?=[KMB]\b)", "", out)
    out = re.sub(r"(?<=\d)\s+%", "%", out)
    out = re.sub(r"(?<=\d) (?=(?:ms|us|ns|s|TB|GB|MB|KB)\b)", "", out)
    return re.sub(r"[ \t]+", " ", out).strip()


def escape_xml(text: str) -> str:
    """Escape user text for ReportLab's Paragraph markup.

    Paragraph parses a small XML dialect, so a bullet containing "R&D" or
    "latency <200ms" would otherwise raise at render time or silently swallow
    the rest of the line. Applied to content only \u2014 never to the <b> tags the
    renderer adds itself.
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
