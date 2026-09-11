"""HTTP surface for the editor.

Two properties make this deployable to a serverless function:

  * It never touches the filesystem. Everything persists through `store`, which is
    Postgres when DATABASE_URL is set.
  * PDFs and DOCX are rendered on demand, in about 40ms, from the resume JSON.
    Nothing binary is stored, so nothing binary can go stale, and there is no blob
    store to pay for.

The client never posts prose — it posts a TailoredResume, the same structured
object the pipeline produced. Editing is mutating that object; rendering is a pure
function of it.

Every route takes `user: CurrentUser` and passes it to the store. That is
deliberately a parameter rather than a module-level constant or a request-scoped
global: the store's whole isolation story is the user id on each call, so making
it impossible to write a handler without naming it is worth the repetition.
"""

from __future__ import annotations

import os

from fastapi import (
    Body,
    FastAPI,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from .. import store
from ..ats.check import check_pdf
from ..config import DEFAULT_PROFILE
from ..models.analysis import Analysis
from ..models.job import JobDescription
from ..models.profile import MasterProfile
from ..models.tailored import CoverLetter, TailoredResume
from ..pipeline.analyze import analyze
from ..pipeline.cover_letter import write_cover_letter
from ..pipeline.elicit import RESPONSIBILITY_NOTICE
from ..pipeline.parse_jd import parse_jd
from ..pipeline.tailor import TailorConfig, tailor
from ..render import docx as docx_render
from ..render import pdf as pdf_render
from ..render.html import resume_html
from .auth import CurrentUser

# Only meaningful on the file-backed store, where the profile lives at a path.
# On Postgres the user id addresses it and this is ignored.
PROFILE_PATH = DEFAULT_PROFILE

api = FastAPI(title="recast", version="0.2.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("RECAST_ORIGINS", "http://localhost:3000").split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
    # The bearer token is read out of the Supabase session by page JavaScript and
    # set as a header, so cross-origin callers need it on the allowlist.
    allow_credentials=True,
)


def _profile(user: str) -> MasterProfile:
    try:
        return store.load_profile(PROFILE_PATH, user)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(404, f"No master profile: {exc}") from exc


def _resume(job_id: str, user: str) -> TailoredResume:
    try:
        return store.load_resume(job_id, user=user)
    except KeyError as exc:
        raise HTTPException(404, f"No resume for {job_id}.") from exc


def _job(job_id: str, user: str) -> JobDescription:
    try:
        return store.load_job(job_id, user=user)
    except KeyError as exc:
        raise HTTPException(404, f"No job {job_id}.") from exc


def _ats_summary(report) -> dict:
    return {
        "keyword_coverage": round(report.keyword_coverage, 3),
        "keyword_hits": report.keyword_hits,
        "keyword_misses": report.keyword_misses,
        "missing_bullets": report.missing_bullets,
        "warnings": report.warnings,
        "pages": report.pages,
    }


# --- meta --------------------------------------------------------------------


@api.get("/health")
def health(user: CurrentUser) -> dict:
    return {
        "ok": True,
        "storage": "postgres" if store.using_postgres() else "files",
        "notice": RESPONSIBILITY_NOTICE,
    }


@api.get("/profile")
def get_profile(user: CurrentUser) -> MasterProfile:
    return _profile(user)


@api.post("/resumes")
async def upload_resume(user: CurrentUser, file: UploadFile = File(...)) -> dict:
    """Upload a resume, get back the parsed structure — NOT saved yet.

    Deliberately does not persist. PDF extraction is lossy, so the user reviews the
    parse and confirms with PUT /profile. Saving first would make a bad parse the
    permanent source of truth that everything downstream is checked against.
    """
    from ..ingest import accept, extract, parse_resume
    from ..ingest.validate import RejectedUpload

    try:
        upload = accept(await file.read(), file.filename or "")
        doc = extract(upload.data, upload.filename)
        result = parse_resume(doc)
    except RejectedUpload as exc:
        raise HTTPException(415, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    profile = result.profile
    profile.origin = "upload"
    profile.source_filename = upload.filename
    profile.parse_confidence = result.confidence

    return {
        "profile": profile,
        "confidence": result.confidence,
        "needs_review": result.needs_review,
        "warnings": result.warnings,
        "unverified": result.unverified,
        "extracted_chars": len(doc.text),
        "pages": doc.pages,
    }


@api.put("/profile")
def put_profile(user: CurrentUser, profile: MasterProfile) -> MasterProfile:
    store.save_profile(profile, PROFILE_PATH, user)
    return profile


# --- analyses ----------------------------------------------------------------


def _analysis_for(profile, jd, user: str, *, refresh: bool = False) -> Analysis:
    """Analyse, reusing a stored result when nothing it depends on has changed.

    The cache key is (profile fingerprint, job, ruleset version), so an edit to
    either side invalidates it automatically. This is what makes re-rendering,
    re-templating and cover-letter tone changes free — they were the motivating
    case for making Analysis a stored object at all.
    """
    from ..models.analysis import RULESET_VERSION

    fingerprint = profile.fingerprint()
    if not refresh:
        cached = store.find_analysis(fingerprint, jd.id, RULESET_VERSION, user=user)
        if cached is not None:
            return cached

    fresh = analyze(profile, jd)
    store.save_analysis(fresh, user=user)
    return fresh


@api.post("/analyses")
def create_analysis(user: CurrentUser,
                    job_id: str = Body(..., embed=True),
                    refresh: bool = Body(False, embed=True)) -> Analysis:
    return _analysis_for(_profile(user), _job(job_id, user), user, refresh=refresh)


@api.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, user: CurrentUser) -> Analysis:
    try:
        return store.load_analysis(analysis_id, user=user)
    except KeyError as exc:
        raise HTTPException(404, f"No analysis {analysis_id}.") from exc


@api.get("/applications/{job_id}/analysis")
def analysis_for_application(job_id: str, user: CurrentUser) -> Analysis:
    """The dashboard payload: subscores with their inputs, matches with evidence, gaps."""
    return _analysis_for(_profile(user), _job(job_id, user), user)


# --- applications ------------------------------------------------------------


@api.post("/applications")
def create(user: CurrentUser, raw: str = Body(..., embed=True), strict: bool = True) -> dict:
    """Paste a job description, get a tailored resume. The whole pipeline, one call."""
    jd = parse_jd(raw)
    store.save_job(jd, user=user)

    profile = _profile(user)
    analysis = _analysis_for(profile, jd, user)
    resume = tailor(profile, jd, TailorConfig(strict_guard=strict), analysis=analysis)
    store.save_resume(resume, user=user)

    fit = pdf_render.render_resume_pdf(resume)
    report = check_pdf(fit.pdf, resume, jd)

    record = store.load_application(jd.id, user=user)
    record.company, record.role = jd.company, jd.role
    record.resume_pages = fit.pages
    record.keyword_coverage = round(report.keyword_coverage, 3)
    store.save_application(record, user=user)

    return {"job": jd, "resume": resume, "app": record, "analysis": analysis,
            "ats": _ats_summary(report)}


@api.get("/applications")
def applications(user: CurrentUser) -> list[store.Application]:
    return store.list_applications(user=user)


@api.get("/applications/{job_id}")
def application(job_id: str, user: CurrentUser) -> dict:
    return {
        "app": store.load_application(job_id, user=user),
        "job": _job(job_id, user),
        "resume": _resume(job_id, user),
    }


@api.put("/applications/{job_id}/resume")
def save_edited(job_id: str, user: CurrentUser, resume: TailoredResume,
                max_pages: int | None = None) -> dict:
    """Accept the edited plan, re-render, and report what a parser sees."""
    fit = pdf_render.render_resume_pdf(resume, max_pages=max_pages)
    store.save_resume(resume, user=user)
    report = check_pdf(fit.pdf, resume, _job(job_id, user))

    record = store.load_application(job_id, user=user)
    record.resume_pages = fit.pages
    record.keyword_coverage = round(report.keyword_coverage, 3)
    store.save_application(record, user=user)

    return {
        "pages": fit.pages,
        "trimmed": [b.model_dump() for b in resume.trimmed],
        "ats": _ats_summary(report),
    }


@api.patch("/applications/{job_id}")
def update_status(job_id: str, user: CurrentUser, status: str = Body(..., embed=True),
                  note: str = Body("", embed=True)) -> store.Application:
    record = store.load_application(job_id, user=user)
    record.status = status  # type: ignore[assignment]
    if note:
        record.notes.append(note)
    store.save_application(record, user=user)
    return record


@api.delete("/applications/{job_id}")
def delete(job_id: str, user: CurrentUser) -> dict:
    store.delete_application(job_id, user=user)
    return {"deleted": job_id}


# --- rendering (all on demand) -----------------------------------------------


@api.post("/preview", response_class=HTMLResponse)
def preview(user: CurrentUser, resume: TailoredResume) -> str:
    """Live preview as HTML, so typing doesn't cost a PDF render."""
    return resume_html(resume)


@api.get("/applications/{job_id}/resume.pdf")
def resume_pdf(job_id: str, user: CurrentUser, max_pages: int | None = None) -> Response:
    fit = pdf_render.render_resume_pdf(_resume(job_id, user), max_pages=max_pages)
    return Response(fit.pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{job_id}.pdf"'})


@api.get("/applications/{job_id}/resume.docx")
def resume_docx(job_id: str, user: CurrentUser) -> Response:
    data = docx_render.resume_docx_bytes(_resume(job_id, user))
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.docx"'},
    )


@api.get("/applications/{job_id}/ats", response_class=PlainTextResponse)
def ats_text(job_id: str, user: CurrentUser) -> str:
    """Exactly what a parser pulls out of the PDF."""
    resume = _resume(job_id, user)
    fit = pdf_render.render_resume_pdf(resume)
    return check_pdf(fit.pdf, resume, _job(job_id, user)).text


@api.get("/applications/{job_id}/ats.json")
def ats_report(job_id: str, user: CurrentUser) -> dict:
    resume = _resume(job_id, user)
    fit = pdf_render.render_resume_pdf(resume)
    return _ats_summary(check_pdf(fit.pdf, resume, _job(job_id, user)))


# --- cover letter ------------------------------------------------------------


@api.post("/applications/{job_id}/cover-letter")
def make_cover_letter(job_id: str, user: CurrentUser,
                      tone: str = "direct and professional") -> CoverLetter:
    letter = write_cover_letter(
        _resume(job_id, user), _job(job_id, user), _profile(user), tone=tone
    )
    store.save_cover_letter(letter, user=user)
    return letter


@api.get("/applications/{job_id}/cover-letter")
def get_cover_letter(job_id: str, user: CurrentUser) -> CoverLetter:
    try:
        return store.load_cover_letter(job_id, user=user)
    except KeyError as exc:
        raise HTTPException(404, "No cover letter yet.") from exc


@api.get("/applications/{job_id}/cover-letter.pdf")
def cover_letter_pdf(job_id: str, user: CurrentUser) -> Response:
    letter = get_cover_letter(job_id, user)
    data = pdf_render.render_cover_letter_pdf(letter, _profile(user).contact)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{job_id}-letter.pdf"'})
