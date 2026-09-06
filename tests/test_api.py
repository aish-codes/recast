"""API tests, in-process.

What matters here is the editor's round trip — GET a plan, PUT an edited plan, get
a PDF and an ATS report back — plus the two properties that make the API
deployable: it never touches the filesystem for output, and the token gate holds.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from recast import store
from recast.api.main import api
from recast.models.job import JobDescription, Requirement
from recast.pipeline.tailor import baseline

PROFILE = Path(__file__).resolve().parents[1] / "data" / "profiles" / "example.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point at a COPY of the profile: PUT /profile writes through to this path,
    # and a test must never edit the repo's fixture out from under the next one.
    scratch = tmp_path / "profile.json"
    scratch.write_text(PROFILE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(store, "OUT_DIR", tmp_path)
    monkeypatch.setattr("recast.api.main.PROFILE_PATH", scratch)
    return TestClient(api)


@pytest.fixture
def seeded(tmp_path):
    """One application on disk, as the pipeline would leave it."""
    jd = JobDescription(
        raw="python backend role",
        company="Acme",
        role="Backend Engineer",
        requirements=[Requirement(text="Python", kind="must", skill="python")],
        keywords=["python", "postgresql"],
    ).ensure_id()
    resume = baseline(store.load_profile(PROFILE))
    resume.job_id = jd.id
    store.save_job(jd, tmp_path)
    store.save_resume(resume, tmp_path)
    store.save_application(store.Application(job_id=jd.id, company="Acme"), tmp_path)
    return jd.id


# --- basics ------------------------------------------------------------------


def test_health_reports_the_active_backend(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["storage"] in {"files", "postgres"}
    assert "responsible" in body["notice"]


def test_profile_round_trip(client):
    """PUT then GET must persist — and must not touch the repo's fixture."""
    got = client.get("/profile")
    assert got.status_code == 200
    assert got.json()["contact"]["name"] == "Alex Rao"

    edited = got.json()
    edited["contact"]["location"] = "Chennai, India"
    assert client.put("/profile", json=edited).status_code == 200
    assert client.get("/profile").json()["contact"]["location"] == "Chennai, India"
    assert "Bengaluru" in PROFILE.read_text(encoding="utf-8"), "repo fixture was modified"


# --- auth --------------------------------------------------------------------


def test_token_gate_rejects_and_admits(client, monkeypatch):
    monkeypatch.setattr("recast.api.main.TOKEN", "s3cret")
    assert client.get("/profile").status_code == 401
    assert client.get("/profile", headers={"X-Recast-Token": "wrong"}).status_code == 401
    assert client.get("/profile", headers={"X-Recast-Token": "s3cret"}).status_code == 200


def test_no_token_configured_means_open(client):
    assert client.get("/profile").status_code == 200


# --- the editor round trip ---------------------------------------------------


def test_application_listing_and_fetch(client, seeded):
    listed = client.get("/applications")
    assert listed.status_code == 200
    assert any(a["job_id"] == seeded for a in listed.json())

    one = client.get(f"/applications/{seeded}")
    assert one.status_code == 200
    assert one.json()["resume"]["job_id"] == seeded


def test_preview_returns_html_without_a_job(client, seeded):
    resume = client.get(f"/applications/{seeded}").json()["resume"]
    r = client.post("/preview", json=resume)
    assert r.status_code == 200
    assert "Alex Rao" in r.text
    assert "&#34;" not in r.text.split("<style>")[1].split("</style>")[0]


def test_editing_a_bullet_survives_the_round_trip(client, seeded):
    resume = client.get(f"/applications/{seeded}").json()["resume"]
    edited = "Owned the ledger. Edited by hand."
    resume["experience"][0]["bullets"][0]["text"] = edited
    resume["experience"][0]["bullets"][0]["locked"] = True

    r = client.put(f"/applications/{seeded}/resume", json=resume)
    assert r.status_code == 200, r.text
    body = r.json()
    # No page cap was asked for, so nothing is sacrificed to fit.
    assert body["trimmed"] == []
    assert body["ats"]["missing_bullets"] == []

    assert store.load_resume(seeded, store.OUT_DIR).experience[0].bullets[0].text == edited
    assert edited.lower() in client.get(f"/applications/{seeded}/ats").text.lower()


def test_editing_updates_the_tracked_coverage(client, seeded):
    resume = client.get(f"/applications/{seeded}").json()["resume"]
    client.put(f"/applications/{seeded}/resume", json=resume)
    app = next(a for a in client.get("/applications").json() if a["job_id"] == seeded)
    assert app["keyword_coverage"] is not None
    assert app["resume_pages"] >= 1


# --- rendering on demand -----------------------------------------------------


def test_pdf_is_rendered_without_ever_being_stored(client, seeded, tmp_path):
    r = client.get(f"/applications/{seeded}/resume.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    # The whole point: no PDF was written to disk to serve that.
    assert list(tmp_path.rglob("*.pdf")) == []


def test_docx_is_rendered_on_demand(client, seeded):
    r = client.get(f"/applications/{seeded}/resume.docx")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_ats_json_report(client, seeded):
    body = client.get(f"/applications/{seeded}/ats.json").json()
    assert body["missing_bullets"] == []
    assert 0.0 <= body["keyword_coverage"] <= 1.0


def test_missing_resume_is_404_not_a_crash(client):
    assert client.get("/applications/jd_nope/resume.pdf").status_code == 404
    assert client.get("/applications/jd_nope/ats").status_code == 404


# --- tracker -----------------------------------------------------------------


def test_status_update_and_delete(client, seeded):
    r = client.patch(f"/applications/{seeded}", json={"status": "applied", "note": "referred"})
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    assert "referred" in r.json()["notes"]

    assert client.delete(f"/applications/{seeded}").status_code == 200
    assert client.get("/applications").json() == []


# --- analyses (Phase 2) ------------------------------------------------------


def test_analysis_is_addressable_and_cached(client, seeded, monkeypatch):
    """A second request must not pay for a second analysis."""
    calls = {"n": 0}
    real = __import__("recast.api.main", fromlist=["analyze"]).analyze

    def counting(profile, jd):
        calls["n"] += 1
        return real(profile, jd)

    monkeypatch.setattr("recast.api.main.analyze", counting)
    monkeypatch.setattr("recast.pipeline.select.score_bullets", lambda p, j, limit=40: {})

    first = client.get(f"/applications/{seeded}/analysis")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["id"].startswith("an_")
    assert 0.0 <= body["overall"] <= 1.0
    assert body["subscores"], "the score must be decomposed"

    client.get(f"/applications/{seeded}/analysis")
    assert calls["n"] == 1, "the second call should have hit the cache"

    fetched = client.get(f"/analyses/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_refresh_bypasses_the_cache(client, seeded, monkeypatch):
    monkeypatch.setattr("recast.pipeline.select.score_bullets", lambda p, j, limit=40: {})
    client.get(f"/applications/{seeded}/analysis")
    r = client.post("/analyses", json={"job_id": seeded, "refresh": True})
    assert r.status_code == 200


def test_every_subscore_declares_its_weight(client, seeded, monkeypatch):
    monkeypatch.setattr("recast.pipeline.select.score_bullets", lambda p, j, limit=40: {})
    subs = client.get(f"/applications/{seeded}/analysis").json()["subscores"]
    assert abs(sum(s["weight"] for s in subs) - 1.0) < 1e-6
    assert all("name" in s and "detail" in s for s in subs)


def test_unknown_analysis_is_404(client):
    assert client.get("/analyses/an_nope").status_code == 404
