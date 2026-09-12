"""Storage, with the backend chosen by environment.

    DATABASE_URL set  -> Postgres  (what the deployed app uses)
    otherwise         -> local files under out/  (what the CLI uses)

The module-level functions are a facade with the signatures the CLI has always
used, so nothing above this layer knows or cares which backend is live.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..config import EXAMPLE_PROFILE
from ..config import OUT_DIR as _DEFAULT_OUT
from ..models.analysis import Analysis
from ..models.job import JobDescription
from ..models.profile import MasterProfile
from ..models.tailored import CoverLetter, TailoredResume
from .base import DEFAULT_USER, Application, Status, Store
from .files import FileStore

__all__ = [
    "Application", "Status", "Store", "FileStore", "DEFAULT_USER", "OUT_DIR",
    "app_dir", "backend", "using_postgres",
    "save_job", "load_job", "save_resume", "load_resume",
    "save_cover_letter", "load_cover_letter",
    "save_application", "load_application", "list_applications", "delete_application",
    "count_resumes",
    "save_profile", "load_profile", "ProtectedProfile",
    "save_analysis", "load_analysis", "find_analysis",
]

# Tests and the CLI both reassign this; FileStore is constructed from it per call
# so a reassignment always takes effect.
OUT_DIR = _DEFAULT_OUT


def using_postgres() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def backend(root: Path | None = None) -> Store:
    if using_postgres():
        from .postgres import PgStore

        return PgStore()
    return FileStore(root or OUT_DIR)


def app_dir(job_id: str, root: Path | None = None) -> Path:
    """Filesystem location for one application. Local/CLI use only."""
    return FileStore(root or OUT_DIR).app_dir(job_id)


def save_job(jd: JobDescription, root: Path | None = None, user: str = DEFAULT_USER) -> None:
    backend(root).save_job(jd, user)


def load_job(job_id: str, root: Path | None = None, user: str = DEFAULT_USER) -> JobDescription:
    return backend(root).load_job(job_id, user)


def save_resume(resume: TailoredResume, root: Path | None = None,
                user: str = DEFAULT_USER) -> None:
    backend(root).save_resume(resume, user)


def load_resume(job_id: str, root: Path | None = None,
                user: str = DEFAULT_USER) -> TailoredResume:
    return backend(root).load_resume(job_id, user)


def save_cover_letter(letter: CoverLetter, root: Path | None = None,
                      user: str = DEFAULT_USER) -> None:
    backend(root).save_cover_letter(letter, user)


def load_cover_letter(job_id: str, root: Path | None = None,
                      user: str = DEFAULT_USER) -> CoverLetter:
    return backend(root).load_cover_letter(job_id, user)


def save_application(app: Application, root: Path | None = None,
                     user: str = DEFAULT_USER) -> None:
    backend(root).save_application(app, user)


def load_application(job_id: str, root: Path | None = None,
                     user: str = DEFAULT_USER) -> Application:
    return backend(root).load_application(job_id, user)


def list_applications(root: Path | None = None, user: str = DEFAULT_USER) -> list[Application]:
    return backend(root).list_applications(user)


def delete_application(job_id: str, root: Path | None = None,
                       user: str = DEFAULT_USER) -> None:
    backend(root).delete_application(job_id, user)


def count_resumes(root: Path | None = None, user: str = DEFAULT_USER) -> int:
    """How many resumes this user has had recast."""
    return backend(root).count_resumes(user)


def save_analysis(analysis: Analysis, root: Path | None = None,
                  user: str = DEFAULT_USER) -> None:
    backend(root).save_analysis(analysis, user)


def load_analysis(analysis_id: str, root: Path | None = None,
                  user: str = DEFAULT_USER) -> Analysis:
    return backend(root).load_analysis(analysis_id, user)


def find_analysis(fingerprint: str, job_id: str, ruleset: str,
                  root: Path | None = None, user: str = DEFAULT_USER) -> Analysis | None:
    """A cache probe. Returns None when the profile or the ruleset has moved on."""
    return backend(root).find_analysis(fingerprint, job_id, ruleset, user)


class ProtectedProfile(RuntimeError):
    """Raised on any attempt to write over the packaged demo profile."""


def save_profile(profile: MasterProfile, path: Path, user: str = DEFAULT_USER) -> Path:
    """Path-addressed locally; user-addressed on Postgres."""
    if Path(path).resolve() == EXAMPLE_PROFILE.resolve():
        raise ProtectedProfile(
            f"{EXAMPLE_PROFILE.name} is the demo fixture the tests rely on and is "
            "tracked in git — writing a real resume there would commit personal "
            "details. Use --profile data/profiles/me.json instead."
        )
    if using_postgres():
        backend().save_profile(profile, user)
    else:
        FileStore(OUT_DIR).save_profile(profile, path)
    return path


def load_profile(path: Path, user: str = DEFAULT_USER) -> MasterProfile:
    if using_postgres():
        stored = backend().load_profile(user)
        if stored is not None:
            return stored
        # First deploy: seed Postgres from the file the user shipped.
        seeded = FileStore(OUT_DIR).load_profile(path)
        backend().save_profile(seeded, user)
        return seeded
    path = Path(path)
    if not path.exists() and path != EXAMPLE_PROFILE:
        # Nothing of yours yet — fall back to the demo so the tool runs out of the
        # box. Read-only: writes always go to `path`.
        return FileStore(OUT_DIR).load_profile(EXAMPLE_PROFILE)
    return FileStore(OUT_DIR).load_profile(path)
