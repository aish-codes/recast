"""Offline tests: the whole pipeline with the model stubbed out.

Everything that matters for correctness here is deterministic — selection order,
the fabrication guard, gap detection, page fitting, ATS round-tripping. The model
is stubbed so these run with no API key and no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recast.ats.check import check_pdf
from recast.models.job import JobDescription, Requirement
from recast.pipeline import guard, rewrite, select
from recast.pipeline.tailor import TailorConfig, baseline, tailor
from recast.render import pdf as pdf_render
from recast.store import load_profile

PROFILE = Path(__file__).resolve().parents[1] / "data" / "profiles" / "example.json"


@pytest.fixture
def profile():
    return load_profile(PROFILE)


@pytest.fixture
def jd():
    return JobDescription(
        raw="senior platform engineer, payments",
        company="Acme Pay",
        role="Senior Platform Engineer",
        seniority="senior",
        requirements=[
            Requirement(text="Deep Python experience", kind="must", skill="python"),
            Requirement(text="Strong PostgreSQL", kind="must", skill="postgresql"),
            Requirement(text="Idempotency in distributed systems", kind="must", skill="kafka"),
            Requirement(text="Infrastructure as code", kind="must", skill="terraform"),
            Requirement(text="Rust for new services", kind="nice", skill="rust"),
        ],
        keywords=["python", "postgresql", "kafka", "terraform", "idempotency", "on-call",
                  "kubernetes", "ledger", "reconciliation", "rust"],
    ).ensure_id()


# --- guard ------------------------------------------------------------------

ORIGINAL = (
    "Owned the double-entry ledger service processing 40M transactions per month, "
    "cutting reconciliation breaks from 1.2% to 0.03% over two quarters."
)


@pytest.mark.parametrize(
    "rewritten,expected",
    [
        ("Owned a double-entry ledger processing 40M transactions monthly, cutting "
         "reconciliation breaks from 1.2% to 0.03% in two quarters.", None),
        ("Owned the ledger service processing 90M transactions per month, cutting "
         "reconciliation breaks by 99% over two quarters.", "invented_metric"),
        ("Owned the double-entry ledger in Rust, processing 40M transactions per month, "
         "cutting breaks from 1.2% to 0.03% over two quarters.", "invented_entity"),
    ],
)
def test_guard_catches_fabrication(profile, rewritten, expected):
    flags = guard.check(ORIGINAL, rewritten, guard.profile_vocabulary(profile))
    if expected is None:
        assert flags == []
    else:
        assert any(f.startswith(expected) for f in flags), flags


def test_guard_allows_terms_the_user_claimed_elsewhere(profile):
    """Kubernetes is in the user's skills, so reusing it is verifiable, not invented."""
    rewritten = ORIGINAL.replace("service", "service on Kubernetes")
    flags = guard.check(ORIGINAL, rewritten, guard.profile_vocabulary(profile))
    assert not any(f.startswith("invented_entity") for f in flags), flags


@pytest.mark.parametrize(
    "original,rewritten,flagged",
    [
        # Same claim, different spelling — must not be treated as fabrication.
        ("Processed 40M transactions per month.", "Processed 40 million transactions per month.", False),
        ("Went from zero coverage to 71%.", "Took coverage from 0% to 71%.", False),
        ("Cut deploy time to under 4.", "Cut deploy time to under 4 by removing scripts.", False),
        # Genuinely different claims.
        ("Processed 40M transactions per month.", "Processed 90M transactions per month.", True),
        ("Processed 40M transactions per month.", "Processed 40B transactions per month.", True),
        ("Processed 40M transactions per month.", "Processed 40M transactions at 99.99% uptime.", True),
    ],
)
def test_numbers_compare_by_value_not_spelling(profile, original, rewritten, flagged):
    flags = guard.check(original, rewritten, guard.profile_vocabulary(profile), max_drift=1.0)
    assert any(f.startswith("invented_metric") for f in flags) is flagged, flags


@pytest.mark.parametrize(
    "rewritten",
    [
        "Eliminated duplicate payouts by redesigning settlement around idempotency keys.",
        "Generated transaction sequences to verify invariants. Gained adoption in CI.",
    ],
)
def test_sentence_initial_capitals_are_not_entities(profile, rewritten):
    """A capital after a full stop is grammar, not a product name."""
    flags = guard.check(rewritten, rewritten, guard.profile_vocabulary(profile))
    assert not any(f.startswith("invented_entity") for f in flags), flags


ORIG_AIRFLOW = (
    "Built the ingestion pipeline for satellite imagery metadata, handling 8TB a week "
    "through Airflow and S3."
)


@pytest.mark.parametrize(
    "rewritten,flagged",
    [
        # Recombinations of terms already in the original.
        ("Built an Airflow-driven ingestion pipeline for satellite imagery metadata "
         "at 8TB/week on S3.", False),
        # A genuinely new technology, even in compound form.
        ("Built a Spark-driven ingestion pipeline for satellite imagery metadata "
         "at 8TB a week through Airflow and S3.", True),
    ],
)
def test_compound_tokens_split_before_flagging(profile, rewritten, flagged):
    flags = guard.check(ORIG_AIRFLOW, rewritten, guard.profile_vocabulary(profile), max_drift=1.0)
    assert any(f.startswith("invented_entity") for f in flags) is flagged, flags


def test_guard_ignores_sentence_final_punctuation(profile):
    flags = guard.check("Shipped the thing.", "Shipped the thing.", guard.profile_vocabulary(profile))
    assert flags == []


# --- selection & gaps -------------------------------------------------------

def test_prescore_prefers_relevant_bullets(profile, jd):
    scored = [(select.prescore(b, jd), b.text) for b in profile.all_bullets()]
    top = max(scored)[1].lower()
    assert any(k in top for k in ("ledger", "terraform", "idempotency", "settlement"))


# --- tailoring (model stubbed) ---------------------------------------------

def test_tailor_never_invents_bullets(profile, jd, monkeypatch):
    """Even if the model returns garbage, output must trace back to the profile."""

    def evil_rewrite(bullets, jd_, profile_, strict=True):
        return {
            b.id: ("Led a 200-person Rust team migrating 5 exabytes to Mars.", "evil", [])
            for b in bullets
        }

    monkeypatch.setattr(rewrite, "rewrite_bullets", evil_rewrite)
    monkeypatch.setattr(select, "score_bullets", lambda p, j, limit=40: {})

    resume = tailor(profile, jd, TailorConfig(strict_guard=False))
    valid_ids = set(profile.bullet_index())
    assert all(b.source_id in valid_ids for b in resume.bullets())
    # strict_guard off means the garbage ships, but every bullet keeps its original
    # and would be flagged by the guard on the strict path.
    assert all(b.original in {x.text for x in profile.all_bullets()} for b in resume.bullets())


def test_strict_guard_reverts_fabricated_rewrites(profile, jd, monkeypatch):
    def fabricating(system, user, schema, **kw):
        ids = [line.split(":", 1)[0] for line in user.splitlines() if line.startswith("b_")]
        return schema.model_validate(
            {"rewrites": [{"id": i, "text": "Scaled Rust services to 900M users.", "rationale": "x"}
                          for i in ids]}
        )

    monkeypatch.setattr(rewrite, "structured", fabricating)
    monkeypatch.setattr(select, "score_bullets", lambda p, j, limit=40: {})

    resume = tailor(profile, jd, TailorConfig(strict_guard=True))
    for b in resume.bullets():
        assert b.text == b.original, "fabricated rewrite was not reverted"
        assert b.flags, "revert happened silently"


def test_bullet_budget_is_enforced_before_rewriting(profile, jd, monkeypatch):
    """The cap must apply to what we pay to rewrite, not just what gets rendered."""
    seen: list[int] = []

    def counting_rewrite(bullets, jd_, profile_, strict=True):
        seen.append(len(bullets))
        return {b.id: (b.text, "", []) for b in bullets}

    monkeypatch.setattr(rewrite, "rewrite_bullets", counting_rewrite)
    monkeypatch.setattr(select, "score_bullets", lambda p, j, limit=40: {})

    cfg = TailorConfig(max_bullets_total=6, max_projects=0)
    resume = tailor(profile, jd, cfg)
    # +1 for the summary bullet, which is budgeted separately.
    assert seen[0] <= cfg.max_bullets_total + 1, seen
    assert len(resume.bullets()) <= cfg.max_bullets_total + 1


def test_budget_never_empties_the_most_recent_role(profile, jd, monkeypatch):
    monkeypatch.setattr(rewrite, "rewrite_bullets",
                        lambda bs, j, p, strict=True: {b.id: (b.text, "", []) for b in bs})
    monkeypatch.setattr(select, "score_bullets", lambda p, j, limit=40: {})
    resume = tailor(profile, jd, TailorConfig(max_bullets_total=1, max_projects=0))
    assert len(resume.experience[0].bullets) >= 1


def test_rewrite_survives_model_failure(profile, jd, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr(rewrite, "structured", boom)
    bullets = profile.all_bullets()[:3]
    out = rewrite.rewrite_bullets(bullets, jd, profile)
    assert [out[b.id][0] for b in bullets] == [b.text for b in bullets]


def test_scoring_falls_back_to_prescore(profile, jd, monkeypatch):
    monkeypatch.setattr(select, "structured", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError()))
    scores = select.score_bullets(profile, jd)
    assert scores and all(0.0 <= s.score <= 1.0 for s in scores.values())


# --- rendering --------------------------------------------------------------

def test_css_is_not_html_escaped(profile):
    """Autoescaping the font stack's quotes silently invalidates the declaration
    and the PDF falls back to a serif. It renders fine, so nothing catches it."""
    from recast.render.html import resume_html

    html = resume_html(baseline(profile))
    css = html.split("<style>")[1].split("</style>")[0]
    assert "&#34;" not in css and "&quot;" not in css, "CSS was HTML-escaped"
    assert '"Calibri"' in css


def test_user_content_is_still_escaped(profile):
    """`| safe` on the font stack must not have opened an injection path."""
    from recast.render.html import resume_html

    profile.contact.name = "<script>alert(1)</script>"
    html = resume_html(baseline(profile))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_baseline_fits_one_page_and_survives_extraction(profile):
    resume = baseline(profile)
    before = len(resume.bullets())
    fit = pdf_render.render_resume_pdf(resume, max_pages=1)

    assert fit.pages == 1
    report = check_pdf(fit.pdf, resume)
    assert report.missing_bullets == [], report.missing_bullets
    assert report.found_email and report.found_phone
    assert report.missing_sections == []
    assert report.warnings == []
    # Anything cut is accounted for, never silently dropped.
    assert before == len(resume.bullets()) + len(resume.trimmed)


def test_trimming_drops_lowest_scoring_first(profile):
    resume = baseline(profile)
    for i, b in enumerate(resume.experience[0].bullets):
        b.score = i / 10
    lowest = resume.experience[0].bullets[0].source_id
    pdf_render._trim_one(resume, min_per_role=1)
    assert resume.trimmed[0].source_id == lowest


def test_locked_bullets_are_never_trimmed(profile):
    resume = baseline(profile)
    for b in resume.bullets():
        b.locked = True
    resume.projects.clear()
    assert pdf_render._trim_one(resume, min_per_role=1) is False
