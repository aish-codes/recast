"""Read our own PDF back the way an ATS would, and report what it saw.

Almost nobody does this, and it is the cheapest trust you can buy: extract the raw
text from the PDF we just generated and check that the things that matter survived
the round trip — contact details, section headings, every bullet, the JD keywords.

If a bullet doesn't come back out, the renderer is broken, and the user needs to
know that before an ATS finds out for them.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader

from ..models.job import JobDescription
from ..models.tailored import TailoredResume
from ..textutil import clean

SECTIONS = ["experience", "skills", "education"]


@dataclass
class AtsReport:
    text: str
    pages: int
    found_email: bool
    found_phone: bool
    missing_sections: list[str] = field(default_factory=list)
    missing_bullets: list[str] = field(default_factory=list)
    keyword_hits: list[str] = field(default_factory=list)
    keyword_misses: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing_bullets and not self.missing_sections and not self.warnings

    @property
    def keyword_coverage(self) -> float:
        total = len(self.keyword_hits) + len(self.keyword_misses)
        return len(self.keyword_hits) / total if total else 1.0


def _normalise(s: str) -> str:
    """Fold to the same ASCII form we write into the PDF, then flatten whitespace."""
    return re.sub(r"\s+", " ", clean(s)).strip().lower()


def _matches(keyword: str, haystack: str) -> bool:
    """Substring match, tolerant of word-splitting.

    JD parsers routinely split compounds ("OpenTelemetry" -> "open telemetry"),
    so a keyword also counts as present if its despaced form appears.
    """
    if keyword in haystack:
        return True
    # "runbooks" should match a resume that says "runbook".
    for stem in (keyword[:-1] if keyword.endswith("s") else keyword + "s",):
        if len(stem) > 4 and stem in haystack:
            return True
    squashed = keyword.replace(" ", "").replace("-", "")
    return len(squashed) > 4 and squashed in haystack.replace(" ", "").replace("-", "")


def extract_text(pdf: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(pdf))
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(pages), len(reader.pages)


def check_pdf(pdf: bytes, resume: TailoredResume, jd: JobDescription | None = None) -> AtsReport:
    raw, pages = extract_text(pdf)
    flat = _normalise(raw)

    report = AtsReport(
        text=raw,
        pages=pages,
        found_email=bool(resume.contact.email and resume.contact.email.lower() in flat),
        found_phone=bool(
            resume.contact.phone
            and re.sub(r"\D", "", resume.contact.phone)[-7:] in re.sub(r"\D", "", raw)
        ),
    )

    report.missing_sections = [s for s in SECTIONS if s not in flat]

    for bullet in resume.bullets():
        # Compare on a distinctive slice: extraction often mangles spacing but
        # rarely reorders words.
        probe = _normalise(bullet.text)[:60]
        if probe and probe not in flat:
            report.missing_bullets.append(bullet.text[:80])

    if jd:
        for kw in jd.keywords:
            hit = _matches(_normalise(kw), flat)
            (report.keyword_hits if hit else report.keyword_misses).append(kw)

    if resume.contact.email and not report.found_email:
        report.warnings.append("Email did not survive text extraction.")
    if resume.contact.phone and not report.found_phone:
        report.warnings.append("Phone did not survive text extraction.")
    if len(flat) < 600:
        report.warnings.append(
            f"Only {len(flat)} characters extracted — the PDF may be image-based or over-styled."
        )
    if "\ufffd" in raw:
        report.warnings.append("Replacement characters in extracted text — font embedding issue.")

    # Control characters mean a glyph did not survive the round trip. This is how
    # the bullet marker silently became U+007F in every PDF for a while.
    controls = {ch for ch in raw if ord(ch) < 32 and ch not in "\n\r\t"} | {
        ch for ch in raw if ord(ch) == 127
    }
    if controls:
        codes = ", ".join(f"U+{ord(c):04X}" for c in sorted(controls))
        report.warnings.append(
            f"Control characters in extracted text ({codes}) — a glyph is not "
            "extracting as itself."
        )

    return report
