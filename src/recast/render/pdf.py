"""Resume and cover letter -> PDF, with no browser involved.

ReportLab, pure Python: nothing to install at the OS level, nothing that needs a
headless Chromium on the server. That is a deployment decision as much as a
rendering one — without a 200-370MB browser in the image, the whole backend fits
inside an ordinary serverless function.

Two things this renderer will not do:

  * It will not restructure your content to hit a page count. Content flows onto a
    second page when it needs one. Trimming exists, but only if you ask for it.
  * It will not use a layout your resume has to be reverse-engineered out of. One
    column, real text, headings in reading order, no text in page furniture.

Fonts are the base-14 Helvetica family, which every PDF reader has built in. That
means no embedding, no font substitution, and no ligature glyphs — "first" extracts
as "first" rather than a single U+FB01, which is exactly what a parser needs.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models.profile import Contact
from ..models.tailored import CoverLetter, TailoredResume
from ..textutil import clean, escape_xml


def _txt(s: str) -> str:
    """Normalise then escape, for every piece of user content on the page.

    Applied at render rather than only at generation, so text that arrives by
    another route — a hand-edited resume.json, a pasted bullet — gets the same
    ASCII folding. It only touches punctuation and unit spacing, never words.
    """
    return escape_xml(clean(s))

PAGE_SIZES = {"letter": letter, "a4": A4}

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#444444")
RULE = colors.HexColor("#222222")


@dataclass
class FitResult:
    pdf: bytes
    pages: int
    scale: float
    trimmed: int


def _styles(scale: float) -> dict[str, ParagraphStyle]:
    body = 10.5 * scale
    return {
        "name": ParagraphStyle(
            "name", fontName="Helvetica-Bold", fontSize=19 * scale,
            leading=21 * scale, textColor=INK, spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "contact", fontName="Helvetica", fontSize=9.2 * scale,
            leading=12 * scale, textColor=MUTED, spaceAfter=9 * scale,
        ),
        "section": ParagraphStyle(
            "section", fontName="Helvetica-Bold", fontSize=10 * scale,
            leading=12 * scale, textColor=INK, spaceBefore=10 * scale,
            spaceAfter=2, keepWithNext=1,
        ),
        "entry": ParagraphStyle(
            "entry", fontName="Helvetica", fontSize=body,
            leading=body * 1.32, textColor=INK, keepWithNext=1,
        ),
        "meta": ParagraphStyle(
            "meta", fontName="Helvetica", fontSize=9.2 * scale,
            leading=body * 1.32, textColor=MUTED, alignment=TA_RIGHT, keepWithNext=1,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=body,
            leading=body * 1.34, textColor=INK, spaceAfter=2.2 * scale,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=body,
            leading=body * 1.34, textColor=INK, spaceAfter=3 * scale,
        ),
        "letter": ParagraphStyle(
            "letter", fontName="Helvetica", fontSize=11,
            leading=16.5, textColor=INK, spaceAfter=11, alignment=TA_JUSTIFY,
        ),
    }


def _rule(scale: float) -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=0.8, color=RULE,
        spaceBefore=1.5 * scale, spaceAfter=4 * scale,
    )


def _head_row(left: str, right: str, styles: dict, scale: float) -> Table:
    """Title on the left, dates on the right, on one line.

    A two-cell table rather than a layout hack: cells extract in order, so a parser
    reads "Senior Backend Engineer, Fintrail" then the dates, which is the order a
    human reads them in too.
    """
    table = Table(
        [[Paragraph(left, styles["entry"]), Paragraph(right, styles["meta"])]],
        colWidths=["68%", "32%"],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * scale),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ])
    )
    return table


def _bullets(texts: list[str], styles: dict, scale: float) -> ListFlowable:
    """A hyphen, not a bullet glyph.

    ReportLab's base-14 Helvetica has no round bullet that survives text
    extraction — "•" comes back out of the PDF as U+007F, a control character,
    and "▪" comes back as a different shape entirely. Since the whole point of
    this renderer is that a machine can read what it produces, the list marker
    has to be a character that round-trips, and a hyphen is the one that both
    extracts cleanly and reads as a deliberate list.
    """
    return ListFlowable(
        [ListItem(Paragraph(_txt(t), styles["bullet"])) for t in texts],
        bulletType="bullet",
        bulletFontName="Helvetica",
        bulletFontSize=10 * scale,
        leftIndent=12 * scale,
        bulletOffsetY=0.6 * scale,
        start="-",
        spaceAfter=4 * scale,
    )


def _resume_flowables(resume: TailoredResume, scale: float) -> list:
    s = _styles(scale)
    out: list = [Paragraph(_txt(resume.contact.name), s["name"])]

    bits = [resume.contact.email, resume.contact.phone, resume.contact.location]
    bits += [u.replace("https://", "").replace("http://", "").rstrip("/")
             for u in resume.contact.links.values()]
    out.append(Paragraph(_txt(" · ".join(b for b in bits if b)), s["contact"]))

    def section(title: str, blocks: list, *, keep_whole: bool = False) -> None:
        """Emit a section, deciding how it may break across pages.

        Long sections (experience, projects) may split — they have to. Short ones
        are kept whole: a page break that leaves three lines of Skills stranded on
        page two looks like a mistake rather than a document. Either way the
        heading never ends up alone at the foot of a page.
        """
        if not blocks:
            return
        head = [Paragraph(title, s["section"]), _rule(scale)]
        if keep_whole:
            out.append(KeepTogether(head + blocks))
        else:
            out.append(KeepTogether(head + blocks[:1]))
            out.extend(blocks[1:])

    if resume.summary:
        section("SUMMARY", [Paragraph(_txt(resume.summary.text), s["body"])])

    exp_blocks: list = []
    for e in resume.experience:
        meta = f"{e.start} – {e.end or 'Present'}"
        if e.location:
            meta += f" · {e.location}"
        exp_blocks.append(
            _head_row(f"<b>{_txt(e.title)}</b>, {_txt(e.company)}",
                      _txt(meta), s, scale)
        )
        if e.bullets:
            exp_blocks.append(_bullets([b.text for b in e.bullets], s, scale))
        exp_blocks.append(Spacer(1, 3 * scale))
    section("EXPERIENCE", exp_blocks)

    proj_blocks: list = []
    for p in resume.projects:
        left = f"<b>{_txt(p.name)}</b>"
        if p.tech:
            left += f" — {_txt(', '.join(p.tech))}"
        url = (p.url or "").replace("https://", "").replace("http://", "").rstrip("/")
        proj_blocks.append(_head_row(left, _txt(url), s, scale))
        if p.bullets:
            proj_blocks.append(_bullets([b.text for b in p.bullets], s, scale))
        proj_blocks.append(Spacer(1, 3 * scale))
    section("PROJECTS", proj_blocks)

    skill_blocks = [
        Paragraph(f"<b>{_txt(g.name)}:</b> {_txt(', '.join(g.skills))}", s["body"])
        for g in resume.skills
    ]
    section("SKILLS", skill_blocks, keep_whole=True)

    edu_blocks: list = []
    for ed in resume.education:
        left = f"<b>{_txt(ed.degree)}"
        if ed.field:
            left += f", {_txt(ed.field)}"
        left += f"</b>, {_txt(ed.institution)}"
        dates = " – ".join(x for x in (ed.start, ed.end) if x)
        edu_blocks.append(_head_row(left, _txt(dates), s, scale))
        if ed.detail:
            edu_blocks.append(Paragraph(_txt(ed.detail), s["body"]))
    section("EDUCATION", edu_blocks, keep_whole=True)

    if resume.certifications:
        section("CERTIFICATIONS", [_bullets(resume.certifications, s, scale)], keep_whole=True)

    return out


def _build(flowables: list, page_size: str, margin: float) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=PAGE_SIZES.get(page_size.lower(), letter),
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        # Nothing in the page furniture: text in headers and footers is a classic
        # cause of garbled extraction.
        title="", author="", subject="", creator="recast",
    )
    doc.build(list(flowables))
    return buf.getvalue()


def _page_count(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def render_resume_pdf(
    resume: TailoredResume,
    *,
    max_pages: int | None = None,
    page_size: str = "Letter",
    scale: float = 1.0,
    margin: float = 0.55 * inch,
    min_bullets_per_role: int = 1,
) -> FitResult:
    """Render the resume. Content is never restructured to hit a page count.

    `max_pages` is opt-in. Left as None (the default) the document simply flows
    onto as many pages as it needs — a second page is not a failure. Set it only
    if you specifically want the old shrink-then-trim behaviour, and anything
    dropped still lands in `resume.trimmed` rather than disappearing.
    """
    pdf = _build(_resume_flowables(resume, scale), page_size, margin)
    pages = _page_count(pdf)
    if max_pages is None or pages <= max_pages:
        return FitResult(pdf, pages, scale, 0)

    trimmed = 0
    for attempt_scale in (0.98, 0.96, 0.94, 0.92, 0.90):
        pdf = _build(_resume_flowables(resume, attempt_scale), page_size, margin)
        pages = _page_count(pdf)
        if pages <= max_pages:
            return FitResult(pdf, pages, attempt_scale, trimmed)

    while _trim_one(resume, min_bullets_per_role):
        trimmed += 1
        pdf = _build(_resume_flowables(resume, 0.90), page_size, margin)
        pages = _page_count(pdf)
        if pages <= max_pages:
            break

    return FitResult(pdf, _page_count(pdf), 0.90, trimmed)


def _trim_one(resume: TailoredResume, min_per_role: int) -> bool:
    """Drop the single lowest-scoring expendable bullet. -> True if one was dropped."""
    candidates = []
    for exp in resume.experience:
        if len(exp.bullets) > min_per_role:
            candidates += [(b, exp.bullets) for b in exp.bullets if not b.locked]
    for proj in resume.projects:
        candidates += [(b, proj.bullets) for b in proj.bullets if not b.locked]

    if not candidates:
        if resume.projects:
            dropped = resume.projects.pop()
            resume.trimmed.extend(dropped.bullets)
            return True
        return False

    bullet, container = min(candidates, key=lambda pair: pair[0].score)
    container.remove(bullet)
    resume.trimmed.append(bullet)
    return True


def render_cover_letter_pdf(
    letter_doc: CoverLetter,
    contact: Contact,
    *,
    page_size: str = "Letter",
    margin: float = 0.9 * inch,
) -> bytes:
    s = _styles(1.0)
    head = ParagraphStyle("clname", parent=s["name"], fontSize=15, leading=17)
    flow: list = [
        Paragraph(_txt(letter_doc.name), head),
        Paragraph(
            _txt(" · ".join(b for b in (contact.email, contact.phone, contact.location) if b)),
            s["contact"],
        ),
        Spacer(1, 10),
        Paragraph(_txt(letter_doc.greeting), s["letter"]),
    ]
    flow += [Paragraph(_txt(p), s["letter"]) for p in letter_doc.paragraphs]
    flow += [
        Spacer(1, 6),
        Paragraph(_txt(letter_doc.signoff), s["letter"]),
        Paragraph(_txt(letter_doc.name), s["letter"]),
    ]
    return _build(flow, page_size, margin)


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
