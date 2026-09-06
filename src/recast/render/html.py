from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models.profile import Contact
from ..models.tailored import CoverLetter, TailoredResume
from ..textutil import clean

TEMPLATES = Path(__file__).parent / "templates"

# Conservative, widely-installed faces. Anything exotic risks font substitution
# in the PDF, which changes line breaks and therefore page count.
FONT_STACK = '"Calibri", "Carlito", "Helvetica Neue", Helvetica, Arial, sans-serif'


def _strip_scheme(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["strip_scheme"] = _strip_scheme
# Same normalisation the PDF applies, so the preview matches the output.
_env.filters["norm"] = clean


def resume_html(
    resume: TailoredResume,
    *,
    scale: float = 1.0,
    page_size: str = "Letter",
    margin: str = "0.5in 0.55in",
    preview: bool = True,
) -> str:
    """Render the resume as HTML.

    `preview` adds on-screen page framing — the @page margin only applies when
    printing, so without it the text runs to the edge of the viewport and reads
    as clipped.
    """
    return _env.get_template("resume.html.j2").render(
        r=resume, scale=scale, page_size=page_size, margin=margin,
        font_stack=FONT_STACK, preview=preview,
    )


def cover_letter_html(
    letter: CoverLetter,
    contact: Contact,
    *,
    page_size: str = "Letter",
    margin: str = "0.9in",
) -> str:
    return _env.get_template("cover_letter.html.j2").render(
        cl=letter, contact=contact, page_size=page_size, margin=margin, font_stack=FONT_STACK
    )
