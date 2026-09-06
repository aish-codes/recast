"""Ingest: documents in, canonical structure out.

The load-bearing property is the same one the rest of the system has: a parsed
bullet must be traceable to text that was actually in the document. The parser runs
*before* any guard exists, so a fabrication here would become permanent truth.

Extraction is tested against PDFs this project generates itself, which gives real
byte-level ground truth without checking in binary fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from recast.ingest import extract, parse_resume, sniff
from recast.ingest.extract import ExtractedDoc, PdfExtractor
from recast.ingest.validate import MAX_BYTES, RejectedUpload, accept
from recast.pipeline.tailor import baseline
from recast.render import docx as docx_render
from recast.render import pdf as pdf_render
from recast.store import load_profile

PROFILE = Path(__file__).resolve().parents[1] / "data" / "profiles" / "example.json"


@pytest.fixture(scope="module")
def profile():
    return load_profile(PROFILE)


@pytest.fixture(scope="module")
def resume_pdf(profile):
    return pdf_render.render_resume_pdf(baseline(profile)).pdf


@pytest.fixture(scope="module")
def resume_docx(profile, tmp_path_factory):
    return docx_render.resume_docx_bytes(baseline(profile))


# --- format detection --------------------------------------------------------


def test_sniff_uses_magic_bytes_not_the_extension(resume_pdf, resume_docx):
    assert sniff(resume_pdf, "cv.docx") == "pdf"
    assert sniff(resume_docx, "cv.pdf") == "docx"
    assert sniff(b"Alex Rao\nSenior Engineer\n", "cv.pdf") == "text"


def test_a_non_docx_zip_is_rejected():
    with pytest.raises(ValueError, match="zip archive"):
        sniff(b"PK\x03\x04" + b"\x00" * 200)


def test_binary_junk_is_rejected():
    with pytest.raises(ValueError, match="binary"):
        sniff(b"\x89PNG\r\n\x1a\n" + b"\x00" * 300)


# --- upload gate -------------------------------------------------------------


def test_oversized_upload_is_refused_with_a_useful_message():
    with pytest.raises(RejectedUpload, match="limit is"):
        accept(b"%PDF-" + b"x" * (MAX_BYTES + 1))


def test_empty_upload_is_refused():
    with pytest.raises(RejectedUpload, match="empty"):
        accept(b"")


def test_a_real_pdf_is_accepted(resume_pdf):
    up = accept(resume_pdf, "alex.pdf")
    assert up.kind == "pdf" and up.size == len(resume_pdf)


# --- extraction --------------------------------------------------------------


def test_pdf_extraction_recovers_sections_and_bullets(resume_pdf, profile):
    doc = extract(resume_pdf, "alex.pdf")
    assert doc.kind == "pdf" and doc.looks_usable
    assert {"EXPERIENCE", "SKILLS", "EDUCATION"} <= set(doc.headings())

    # Every rendered bullet should come back as a bullet block. The renderer emits
    # the list marker on its own line, so this also covers marker rejoining.
    rendered = [b.text for b in baseline(profile).bullets()]
    found = sum(b.is_bullet for b in doc.blocks)
    assert found >= len(rendered) - 1, f"only {found} bullets from {len(rendered)}"


def test_pdf_extraction_loses_no_bullet_text(resume_pdf, profile):
    doc = extract(resume_pdf, "alex.pdf")
    flat = " ".join(doc.text.split()).lower()
    for bullet in baseline(profile).bullets():
        probe = " ".join(bullet.text.split()).lower()[:50]
        assert probe in flat, f"lost in extraction: {bullet.text[:60]}"


def test_docx_extraction_keeps_structure(resume_docx):
    doc = extract(resume_docx, "alex.docx")
    assert doc.kind == "docx"
    assert any(b.is_bullet for b in doc.blocks)
    assert "Fintrail" in doc.text


def test_scanned_pdf_is_flagged_rather_than_silently_empty():
    """A PDF with no text layer must warn, not return a confident empty parse."""
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 720, "x")
    c.save()

    doc = extract(buf.getvalue(), "scan.pdf")
    assert not doc.looks_usable
    assert any("scan" in w or "image" in w for w in doc.warnings)


def test_password_protected_pdf_fails_clearly():
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 720, "secret resume content here")
    c.setEncrypt(__import__("reportlab.lib.pdfencrypt", fromlist=["StandardEncryption"])
                 .StandardEncryption("owner", "user"))
    c.save()
    with pytest.raises(ValueError, match="password"):
        PdfExtractor().extract(buf.getvalue(), "locked.pdf")


# --- parse verification (the important part) ---------------------------------


# The package exports the *function* `parse_resume`, which shadows the module of
# the same name — so reach the module through sys.modules to patch inside it.
_PARSE_MODULE = sys.modules["recast.ingest.parse_resume"]


def _stub(monkeypatch, payload: dict):
    """Force the parser to return `payload`, so verification is what's under test."""
    monkeypatch.setattr(
        _PARSE_MODULE, "structured",
        lambda system, user, schema, **kw: schema.model_validate(payload),
    )


BASE = {
    "contact": {"name": "Alex Rao", "email": "alex.rao@example.com"},
    "experience": [{
        "company": "Fintrail", "title": "Senior Backend Engineer", "start": "2023-02",
        "bullets": [{"text": "Owned the double-entry ledger service processing 40M transactions per month."}],
    }],
    "skills": [{"name": "Languages", "skills": ["Python"]}],
}


def test_a_faithful_parse_is_high_confidence(monkeypatch):
    doc = ExtractedDoc(
        text=("Alex Rao alex.rao@example.com\nEXPERIENCE\nSenior Backend Engineer, Fintrail\n"
              "Owned the double-entry ledger service processing 40M transactions per month.\n"
              "SKILLS\nLanguages: Python\n" + "filler content to pass the length check. " * 12),
        kind="text",
    )
    _stub(monkeypatch, BASE)
    res = parse_resume(doc)
    assert res.unverified == []
    assert res.confidence >= 0.8
    assert res.profile.contact.name == "Alex Rao"


def test_a_bullet_absent_from_the_document_is_flagged(monkeypatch):
    """The whole safety property: the parser cannot smuggle in a claim."""
    doc = ExtractedDoc(
        text="Alex Rao alex.rao@example.com\nEXPERIENCE\nSenior Backend Engineer, Fintrail\n"
             + "unrelated filler text. " * 30,
        kind="text",
    )
    invented = dict(BASE)
    invented["experience"] = [{
        "company": "Fintrail", "title": "Senior Backend Engineer", "start": "2023-02",
        "bullets": [{"text": "Led a team of forty engineers migrating Kubernetes clusters to Rust."}],
    }]
    _stub(monkeypatch, invented)

    res = parse_resume(doc)
    assert res.unverified, "an invented bullet must not pass verification"
    assert res.needs_review
    assert res.confidence < 0.9


def test_ids_are_generated_locally_not_by_the_model(monkeypatch):
    doc = ExtractedDoc(text="Alex Rao " + "Owned the double-entry ledger service. " * 20, kind="text")
    _stub(monkeypatch, BASE)
    prof = parse_resume(doc).profile
    for bullet in prof.all_bullets():
        assert bullet.id.startswith("b_") and len(bullet.id) == 10
    assert prof.experience[0].id.startswith("e_")


def test_empty_document_raises_rather_than_calling_the_model():
    with pytest.raises(ValueError, match="Nothing to parse"):
        parse_resume(ExtractedDoc(text="   ", kind="text"))


# --- regressions from a real resume ------------------------------------------


def test_ligatures_are_folded_in_every_field_not_just_bullets(monkeypatch):
    """PDF extraction returns "MLﬂow" as one U+FB02 glyph. It used to be cleaned in
    bullets only, so it survived into the skills list — where a job asking for
    MLflow then scored zero against a profile that appears to list it."""
    doc = ExtractedDoc(text="Aishwarya " + "MLflow Snowflake agentic workflows. " * 20, kind="text")
    _stub(monkeypatch, {
        "contact": {"name": "Aishwarya"},
        "skills": [{"name": "Cloud & DevOps", "skills": ["MLﬂow", "Snowﬂake"]}],
        "projects": [{"name": "Tool", "tech": ["Pyﬁles"], "bullets": []}],
        "experience": [{"company": "EY", "title": "Staﬀ Engineer", "start": "2020",
                        "bullets": [{"text": "Built workﬂows."}]}],
    })
    prof = parse_resume(doc).profile

    everything = (
        [s for g in prof.skills for s in g.skills]
        + [t for p in prof.projects for t in p.tech]
        + [e.title for e in prof.experience]
        + [b.text for b in prof.all_bullets()]
    )
    assert not any(ch in v for v in everything for ch in "ﬀﬁﬂﬃﬄ"), everything
    assert "MLflow" in [s for g in prof.skills for s in g.skills]


def test_the_demo_fixture_cannot_be_overwritten(tmp_path):
    """Uploading a resume once wrote real contact details into the tracked
    example profile and broke fourteen tests."""
    from recast import store
    from recast.config import EXAMPLE_PROFILE

    prof = store.load_profile(EXAMPLE_PROFILE)
    with pytest.raises(store.ProtectedProfile):
        store.save_profile(prof, EXAMPLE_PROFILE)

    # Any other path is fine.
    target = tmp_path / "me.json"
    store.save_profile(prof, target)
    assert target.exists()
