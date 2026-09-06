"""Document -> clean text, with whatever structure the format gives us.

Deliberately behind a small protocol. PDF text extraction is lossy in ways that
depend on how the PDF was produced — a two-column layout, a table-based resume or
a scanned page will each fail differently — so this layer is expected to be
replaced or upgraded (pdfplumber, an OCR pass, a hosted parser) without anything
downstream noticing.

What downstream gets is an ExtractedDoc: the text, optional block hints, and an
honest list of warnings. The warnings matter as much as the text — a resume we
extracted badly should be surfaced to the user, not silently structured into
something plausible and wrong.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

Kind = Literal["pdf", "docx", "text"]

# Line shapes that signal list items across most resume templates.
_BULLET_RE = re.compile(r"^\s*[\u2022\u2023\u25cf\u25aa\u00b7\-\*\u2013\u2014]\s+")
# A marker alone on its line: PDF extraction frequently separates the list marker
# from its text, so the two arrive as consecutive lines rather than one.
_LONE_MARKER_RE = re.compile(r"^\s*[\u2022\u2023\u25cf\u25aa\u00b7\-\*\u2013\u2014\x7f]\s*$")
# A heading is short, has no terminal punctuation, and is mostly capitals or title case.
_SECTION_WORDS = {
    "experience", "employment", "work experience", "professional experience",
    "education", "skills", "technical skills", "projects", "certifications",
    "summary", "profile", "objective", "publications", "awards", "interests",
}


@dataclass
class Block:
    text: str
    is_heading: bool = False
    is_bullet: bool = False
    page: int = 0


@dataclass
class ExtractedDoc:
    text: str
    kind: Kind
    source: str = ""
    pages: int = 1
    blocks: list[Block] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def looks_usable(self) -> bool:
        return len(self.text.strip()) >= 300 and not any(
            w.startswith("No extractable text") for w in self.warnings
        )

    def headings(self) -> list[str]:
        return [b.text for b in self.blocks if b.is_heading]


class Extractor(Protocol):
    def handles(self, kind: Kind) -> bool: ...
    def extract(self, data: bytes, source: str) -> ExtractedDoc: ...


# --- format detection --------------------------------------------------------


def sniff(data: bytes, filename: str = "") -> Kind:
    """Detect by magic bytes, not by extension.

    A file called resume.pdf that is actually a .docx (or vice versa) is common
    enough — people rename exports — and trusting the extension turns that into a
    confusing parse failure instead of a correct one.
    """
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK" and b"word/" in data[:4000]:
        return "docx"
    if data[:2] == b"PK":
        # A zip that isn't a Word document — .pages, .odt, or something unwanted.
        raise ValueError("That looks like a zip archive but not a .docx file.")
    if b"\x00" in data[:1000]:
        raise ValueError("That looks like a binary file, not a resume.")
    return "text"


# --- extractors --------------------------------------------------------------


def _classify(line: str) -> Block:
    stripped = line.strip()
    if _BULLET_RE.match(line):
        return Block(text=_BULLET_RE.sub("", line).strip(), is_bullet=True)
    low = stripped.lower().rstrip(":")
    short = len(stripped) <= 40
    heading = bool(stripped) and short and (
        low in _SECTION_WORDS
        or (stripped.isupper() and len(stripped) > 2)
        or (short and not stripped.endswith((".", ",", ";")) and low in _SECTION_WORDS)
    )
    return Block(text=stripped, is_heading=heading)


class PdfExtractor:
    """pypdf. Already a dependency (we use it to verify our own output).

    Good enough for the single-column, text-based PDFs that most resumes are, and
    wrong in predictable ways otherwise — which is what the warnings are for.
    """

    def handles(self, kind: Kind) -> bool:
        return kind == "pdf"

    def extract(self, data: bytes, source: str = "") -> ExtractedDoc:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        warnings: list[str] = []
        if reader.is_encrypted:
            # decrypt() reports failure by return value, not by raising — a wrong
            # password here surfaces much later as a FileNotDecryptedError from
            # somewhere deep in page parsing, which is not a message anyone can act on.
            try:
                opened = reader.decrypt("")
            except Exception:  # noqa: BLE001
                opened = 0
            if not opened:
                raise ValueError(
                    "That PDF is password-protected. Remove the password and try again, "
                    "or paste the text instead."
                )

        blocks: list[Block] = []
        pages_text: list[str] = []
        for i, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            pages_text.append(raw)
            pending_marker = False
            for line in raw.splitlines():
                if not line.strip():
                    continue
                if _LONE_MARKER_RE.match(line):
                    pending_marker = True
                    continue
                b = _classify(line)
                if pending_marker:
                    b.is_bullet, b.is_heading, pending_marker = True, False, False
                b.page = i
                blocks.append(b)

        text = "\n".join(pages_text)
        if len(text.strip()) < 300:
            warnings.append(
                "No extractable text layer — this is probably a scan or an image. "
                "Paste the text instead, or run it through OCR first."
            )
        if _looks_two_column(pages_text):
            warnings.append(
                "This looks like a multi-column layout. Line order may be scrambled; "
                "check the parsed result carefully."
            )
        return ExtractedDoc(text=text, kind="pdf", source=source,
                            pages=len(reader.pages), blocks=blocks, warnings=warnings)


class DocxExtractor:
    """python-docx. Structurally far richer than PDF — styles survive."""

    def handles(self, kind: Kind) -> bool:
        return kind == "docx"

    def extract(self, data: bytes, source: str = "") -> ExtractedDoc:
        from docx import Document

        doc = Document(io.BytesIO(data))
        blocks: list[Block] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name or "").lower()
            blocks.append(Block(
                text=text,
                is_heading="heading" in style or "title" in style,
                is_bullet="list" in style or bool(_BULLET_RE.match(para.text)),
            ))
        # Tables are a common resume layout; read them in row order so nothing is lost.
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    blocks.append(Block(text=" | ".join(cells)))

        text = "\n".join(b.text for b in blocks)
        warnings = []
        if doc.tables:
            warnings.append(
                f"{len(doc.tables)} table(s) found — table-based layouts sometimes "
                "read out of order. Check the parsed result."
            )
        return ExtractedDoc(text=text, kind="docx", source=source,
                            blocks=blocks, warnings=warnings)


class TextExtractor:
    def handles(self, kind: Kind) -> bool:
        return kind == "text"

    def extract(self, data: bytes, source: str = "") -> ExtractedDoc:
        text = data.decode("utf-8", errors="replace")
        blocks = [_classify(line) for line in text.splitlines() if line.strip()]
        return ExtractedDoc(text=text, kind="text", source=source, blocks=blocks)


EXTRACTORS: list[Extractor] = [PdfExtractor(), DocxExtractor(), TextExtractor()]


def extract(data: bytes, filename: str = "") -> ExtractedDoc:
    kind = sniff(data, filename)
    for ex in EXTRACTORS:
        if ex.handles(kind):
            return ex.extract(data, filename)
    raise ValueError(f"No extractor for {kind}.")


def _looks_two_column(pages: list[str]) -> bool:
    """Heuristic: many short lines with a big internal gap suggests side-by-side text."""
    suspicious = 0
    total = 0
    for page in pages:
        for line in page.splitlines():
            if not line.strip():
                continue
            total += 1
            if "   " in line.strip() and len(line) > 40:
                suspicious += 1
    return total > 20 and suspicious / total > 0.35
