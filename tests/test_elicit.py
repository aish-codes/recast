"""Gap-filling by asking, not inventing.

The load-bearing property: a bullet composed from the user's answers may not
contain anything the user did not say. The model phrases; the user supplies the
facts. These run with the model stubbed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recast.models.job import JobDescription, Requirement
from recast.models.tailored import Gap
from recast.pipeline import elicit
from recast.store import load_profile

PROFILE = Path(__file__).resolve().parents[1] / "data" / "profiles" / "example.json"


@pytest.fixture
def profile():
    return load_profile(PROFILE)


@pytest.fixture
def jd():
    return JobDescription(
        raw="platform role",
        role="Platform Engineer",
        requirements=[Requirement(text="Terraform", kind="must", skill="terraform")],
        keywords=["terraform", "kubernetes", "on-call"],
    ).ensure_id()


ANSWERS = {
    "scope": "I set up the Terraform modules for our staging environment on my own",
    "stack": "Terraform and AWS",
    "outcome": "we stopped hand-editing the console and could rebuild staging from scratch",
    "metrics": "",
}


def _stub(monkeypatch, text: str):
    monkeypatch.setattr(
        elicit, "structured",
        lambda system, user, schema, **kw: schema.model_validate(
            {"text": text, "used": [], "honest": True, "rationale": "x"}
        ),
    )


# --- composing from the user's own answers ----------------------------------


def test_composed_bullet_uses_only_what_the_user_said(profile, jd, monkeypatch):
    _stub(monkeypatch, "Built Terraform modules for staging on AWS, replacing "
                       "hand-edited console changes with a rebuildable environment.")
    bullet, flags = elicit.compose_from_answers(ANSWERS, "Terraform", jd, profile)
    assert bullet is not None
    assert flags == [], flags


def test_composed_bullet_flags_a_metric_the_user_never_gave(profile, jd, monkeypatch):
    """The user left `metrics` blank. A number appearing anyway is the whole risk."""
    _stub(monkeypatch, "Built Terraform modules for staging on AWS, cutting "
                       "environment setup time by 80% across 12 services.")
    bullet, flags = elicit.compose_from_answers(ANSWERS, "Terraform", jd, profile)
    assert any(f.startswith("invented_metric") for f in flags), flags


def test_composed_bullet_flags_a_technology_the_user_never_mentioned(profile, jd, monkeypatch):
    _stub(monkeypatch, "Built Terraform and Pulumi modules for staging on AWS.")
    _, flags = elicit.compose_from_answers(ANSWERS, "Terraform", jd, profile)
    assert any(f.startswith("invented_entity") for f in flags), flags


def test_empty_answers_produce_nothing(profile, jd, monkeypatch):
    _stub(monkeypatch, "Something impressive.")
    bullet, flags = elicit.compose_from_answers(
        {"scope": "", "stack": "", "outcome": "", "metrics": "  "}, "Terraform", jd, profile
    )
    assert bullet is None and flags == []


def test_new_bullet_is_saved_to_the_profile(profile, jd, monkeypatch):
    _stub(monkeypatch, "Built Terraform modules for staging on AWS.")
    bullet, _ = elicit.compose_from_answers(ANSWERS, "Terraform", jd, profile)
    target = profile.experience[1]
    before = len(target.bullets)

    elicit.add_to_profile(profile, bullet, target.id)
    assert len(target.bullets) == before + 1
    # It's now indistinguishable from anything else the user wrote — so it is
    # available to every future application, not just this one.
    assert bullet.id in profile.bullet_index()


def test_tags_come_from_the_users_own_words(profile, jd, monkeypatch):
    _stub(monkeypatch, "Built Terraform modules for staging on AWS.")
    bullet, _ = elicit.compose_from_answers(ANSWERS, "Terraform", jd, profile)
    assert "terraform" in bullet.tags
    # The user never mentioned Kubernetes, so it must not be tagged with it.
    assert "kubernetes" not in bullet.tags


# --- reframing adjacent real experience --------------------------------------


def test_reframe_rejects_a_claim_the_original_does_not_support(profile, jd, monkeypatch):
    airflow = next(b for b in profile.all_bullets() if "Airflow" in b.text)
    _stub(monkeypatch, "Managed infrastructure as code with Terraform across six environments.")
    text, rationale, _ = elicit.reframe(airflow, "Terraform", jd, profile)
    assert text == airflow.text, "an unsupported reframe must fall back to the original"
    assert "rejected" in rationale or "unchanged" in rationale


def test_reframe_keeps_an_honest_reemphasis(profile, jd, monkeypatch):
    celery = next(b for b in profile.all_bullets() if "Celery" in b.text)
    honest = ("Replaced nightly batch stock reconciliation with an event-driven Celery "
              "workflow, raising stock accuracy from 92% to 99.4%.")
    _stub(monkeypatch, honest)
    text, _, flags = elicit.reframe(celery, "asynchronous processing", jd, profile)
    assert not any(f.startswith(("invented_metric", "invented_entity")) for f in flags), flags
    assert "Celery" in text


def test_reframe_honours_the_models_own_refusal(profile, jd, monkeypatch):
    airflow = next(b for b in profile.all_bullets() if "Airflow" in b.text)
    monkeypatch.setattr(
        elicit, "structured",
        lambda s, u, schema, **kw: schema.model_validate(
            {"text": "", "honest": False, "rationale": "not what this bullet is about"}
        ),
    )
    text, rationale, _ = elicit.reframe(airflow, "Terraform", jd, profile)
    assert text == airflow.text
    assert "isn't what the job is asking for" in rationale


def test_reframe_survives_a_provider_outage(profile, jd, monkeypatch):
    bullet = profile.all_bullets()[0]
    monkeypatch.setattr(elicit, "structured",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("down")))
    text, _, flags = elicit.reframe(bullet, "Terraform", jd, profile)
    assert text == bullet.text and flags == []


# --- the questions themselves ------------------------------------------------


def test_prompts_offer_adjacent_bullets_to_reframe(profile, jd):
    gaps = [Gap(requirement="Experience with Airflow orchestration", kind="must")]
    prompt = elicit.prompts_for(profile, jd, gaps)[0]
    assert prompt.adjacent, "should surface the user's closest real work"
    assert any("Airflow" in b.text for b in prompt.adjacent)


def test_nice_to_haves_are_not_asked_about_by_default(profile, jd):
    gaps = [Gap(requirement="Rust", kind="nice"), Gap(requirement="Terraform", kind="must")]
    assert len(elicit.prompts_for(profile, jd, gaps)) == 1
    assert len(elicit.prompts_for(profile, jd, gaps, musts_only=False)) == 2
