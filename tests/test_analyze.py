"""The matching engine.

Two properties matter more than the numbers themselves:

  reproducibility — the same profile and job must score the same twice. The model
                    layer picks which requirements to cite and that varies between
                    runs, so the deterministic layers have to carry the verdict.

  honest categories — telling someone a gap is "semantically equivalent" when they
                      have no such experience is worse than telling them nothing.

The model is stubbed throughout; everything under test here is deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recast.models.job import JobDescription, Requirement
from recast.models.profile import Bullet
from recast.pipeline import analyze as A
from recast.pipeline import select
from recast.store import load_profile

PROFILE = Path(__file__).resolve().parents[1] / "data" / "profiles" / "example.json"


@pytest.fixture
def profile():
    return load_profile(PROFILE)


def _jd(*requirements, seniority="unknown", keywords=()):
    return JobDescription(
        raw="x", role="Engineer", seniority=seniority,
        requirements=list(requirements), keywords=list(keywords),
    ).ensure_id()


class _Score:
    def __init__(self, score=0.0, answers=()):
        self.score, self.answers = score, list(answers)
        self.keywords_hit = []


def _scores(monkeypatch, mapping):
    monkeypatch.setattr(select, "score_bullets", lambda p, j, limit=40: mapping)


# --- skill matching ----------------------------------------------------------


def test_short_skill_is_not_matched_as_a_substring():
    """"go" must not match the "go" inside ArgoCD — this shipped as a bug."""
    b = Bullet(text="Migrated to Terraform and ArgoCD.", tags=["terraform", "argocd"])
    assert A._mentions_skill(b, "go") is False
    assert A._mentions_skill(b, "terraform") is True


def test_skill_matching_tolerates_naming_drift():
    """Postings say PostgreSQL; profiles say Postgres. Same skill."""
    b = Bullet(text="Cut p99 latency with a materialised view.", tags=["postgres", "sql"])
    assert A._mentions_skill(b, "postgresql") is True


def test_one_generic_word_is_not_evidence():
    assert A._similar("Built an internal service for finance.", "Go, for our newer services") is False


def test_one_long_specific_word_is_evidence():
    assert A._similar(
        "Owned a payments ledger handling 40M transactions.",
        "Experience in payments, fintech, or another regulated domain",
    ) is True


# --- verdicts ----------------------------------------------------------------


def test_a_skill_in_the_profile_but_undemonstrated_is_partial(profile, monkeypatch):
    """Go is in their skills list; no bullet shows it. Not absent, not strong."""
    _scores(monkeypatch, {})
    a = A.analyze(profile, _jd(Requirement(text="Go, for our newer services",
                                           kind="nice", skill="go")))
    assert a.matches[0].verdict == "partial"
    assert a.matches[0].method == "deterministic"


def test_a_skill_absent_everywhere_is_absent(profile, monkeypatch):
    _scores(monkeypatch, {})
    a = A.analyze(profile, _jd(Requirement(text="Figma fluency", kind="must", skill="figma")))
    assert a.matches[0].verdict == "absent"
    assert a.matches[0].evidence == []


def test_verdicts_do_not_depend_on_which_requirements_the_model_cites(profile, monkeypatch):
    """The model's `answers` vary run to run; a named skill must decide regardless."""
    req = Requirement(text="Experience with infrastructure as code", kind="must", skill="terraform")
    tf = next(b for b in profile.all_bullets() if "Terraform" in b.text)

    _scores(monkeypatch, {tf.id: _Score(0.9, answers=["Experience with infrastructure as code"])})
    cited = A.analyze(profile, _jd(req)).matches[0].verdict

    _scores(monkeypatch, {tf.id: _Score(0.9, answers=[])})   # same bullet, no citation
    uncited = A.analyze(profile, _jd(req)).matches[0].verdict

    assert cited == uncited == "strong"


# --- gap categories ----------------------------------------------------------


def test_no_evidence_and_not_in_vocabulary_is_missing(profile, monkeypatch):
    _scores(monkeypatch, {})
    a = A.analyze(profile, _jd(Requirement(text="Experience with WCAG accessibility auditing",
                                           kind="must", skill="accessibility")))
    gap = a.gaps[0]
    assert gap.category == "missing" and gap.confidence == "high"
    assert not gap.fixable_by_generation


def test_weak_textual_overlap_is_not_called_semantically_equivalent(profile, monkeypatch):
    """The damaging false positive: claiming they have it when they do not."""
    weak = profile.all_bullets()[0]
    _scores(monkeypatch, {weak.id: _Score(0.1, answers=[])})
    a = A.analyze(profile, _jd(Requirement(text="Strong CSS architecture and theming skills",
                                           kind="must", skill="css")))
    assert a.gaps[0].category in ("missing", "transferable")


def test_listed_but_undemonstrated_is_underrepresented(profile, monkeypatch):
    _scores(monkeypatch, {})
    a = A.analyze(profile, _jd(Requirement(text="Kubernetes operational experience",
                                           kind="nice", skill="kubernetes")))
    gap = a.gaps[0]
    assert gap.category == "underrepresented"
    assert gap.fixable_by_generation


def test_a_strong_match_produces_no_gap(profile, monkeypatch):
    tf = next(b for b in profile.all_bullets() if "Terraform" in b.text)
    _scores(monkeypatch, {tf.id: _Score(0.9)})
    a = A.analyze(profile, _jd(Requirement(text="Infrastructure as code", kind="must",
                                           skill="terraform")))
    assert a.gaps == []


# --- scoring -----------------------------------------------------------------


def test_weights_sum_to_one():
    assert abs(sum(A.WEIGHTS.values()) - 1.0) < 1e-9


def test_subscores_carry_the_inputs_that_produced_them(profile, monkeypatch):
    _scores(monkeypatch, {})
    a = A.analyze(profile, _jd(Requirement(text="Figma fluency", kind="must", skill="figma")))
    musts = next(s for s in a.subscores if s.name == "Must-have requirements")
    assert musts.inputs == [a.matches[0].requirement_id], "a score must name what dragged it down"


def test_an_unmet_must_have_caps_the_band(profile, monkeypatch):
    """A high arithmetic score with a hard requirement missing is not 'strong'."""
    tf = next(b for b in profile.all_bullets() if "Terraform" in b.text)
    _scores(monkeypatch, {tf.id: _Score(0.95)})
    a = A.analyze(profile, _jd(
        Requirement(text="Infrastructure as code", kind="must", skill="terraform"),
        Requirement(text="Figma fluency", kind="must", skill="figma"),
    ))
    assert a.unmet_musts()
    assert a.band != "strong"


def test_seniority_is_a_step_function(profile, monkeypatch):
    _scores(monkeypatch, {})
    principal = A.analyze(profile, _jd(seniority="principal"))
    senior = A.analyze(profile, _jd(seniority="senior"))
    s_p = next(s for s in principal.subscores if s.name == "Seniority fit")
    s_s = next(s for s in senior.subscores if s.name == "Seniority fit")
    assert s_s.score == 1.0
    assert s_p.score < 0.5, "three levels below should be near-disqualifying"
    assert "levels below" in s_p.detail


def test_keyword_coverage_is_the_smallest_weight():
    assert A.WEIGHTS["keyword_coverage"] == min(A.WEIGHTS.values())


# --- identity / caching ------------------------------------------------------


def test_analysis_id_is_stable_for_the_same_inputs(profile, monkeypatch):
    _scores(monkeypatch, {})
    jd = _jd(Requirement(text="Python", kind="must", skill="python"))
    assert A.analyze(profile, jd).id == A.analyze(profile, jd).id


def test_editing_the_profile_changes_the_cache_key(profile, monkeypatch):
    _scores(monkeypatch, {})
    jd = _jd(Requirement(text="Python", kind="must", skill="python"))
    before = A.analyze(profile, jd).id
    profile.experience[0].bullets.append(Bullet(text="Something new I did last quarter."))
    assert A.analyze(profile, jd).id != before, "a stale analysis must not be servable"


def test_explain_names_every_dimension(profile, monkeypatch):
    _scores(monkeypatch, {})
    text = A.analyze(profile, _jd(Requirement(text="Python", skill="python"))).explain()
    for name in ("Must-have", "Seniority", "Keyword"):
        assert name in text


def test_editing_a_bullet_in_place_invalidates_the_cache_key(profile):
    """Bullet ids are assigned at construction and not recomputed on mutation, so a
    fingerprint over ids reports 'unchanged' for edited text — and a stale analysis
    gets served. This is the regression that matters most in the whole cache."""
    before = profile.fingerprint()
    profile.experience[0].bullets[0].text += " Also shipped a thing."
    assert profile.fingerprint() != before


def test_reordering_without_editing_is_still_a_change(profile):
    """Order affects selection, so it must affect the key."""
    before = profile.fingerprint()
    profile.experience[0].bullets.reverse()
    assert profile.fingerprint() != before


def test_an_untouched_profile_keeps_its_key(profile):
    assert profile.fingerprint() == profile.fingerprint()


def test_requirement_ids_are_content_hashed_not_positional():
    """The JD parser used to be handed a schema containing `id`, so the model
    numbered requirements 1..n. Positional ids break every stored match and gap
    as soon as a job is re-parsed in a different order."""
    from recast.pipeline.parse_jd import _Req

    assert "id" not in _Req.model_fields, "the model must never be shown the id field"

    a = Requirement(text="Strong PostgreSQL")
    b = Requirement(text="Strong PostgreSQL")
    c = Requirement(text="Deep Python experience")
    assert a.id == b.id and a.id != c.id
    assert a.id.startswith("r_")
