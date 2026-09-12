"""What a storage backend has to be able to do.

Deliberately small. Everything the app persists is a Pydantic model that
serialises to JSON, so a backend needs to put JSON somewhere and get it back —
which is why swapping local files for Postgres is a file, not a project.

Note what is NOT here: PDFs. They are a pure function of the resume JSON and take
about 40ms to produce, so they are rendered on demand and never stored. That
removes an entire piece of infrastructure (S3/R2/blob storage) from the system,
and it means a rendered PDF can never go stale against the resume it came from.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ..models.analysis import Analysis
from ..models.job import JobDescription
from ..models.profile import MasterProfile
from ..models.tailored import CoverLetter, TailoredResume

Status = Literal["draft", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn"]

# Who a request belongs to when nobody signed in. That is the CLI, `recast
# serve`, and the test suite — all of them file-backed, where the user id is
# ignored entirely and this is just a label.
#
# RECAST_USER overrides it, and the case that needs it is the CLI pointed at the
# deployed Postgres: user_id there is a uuid with a foreign key to auth.users, so
# "me" is rejected on sight. Set it to your own Supabase user id and the CLI
# writes into the same rows the web app reads.
DEFAULT_USER = os.getenv("RECAST_USER", "me")


class Application(BaseModel):
    job_id: str
    company: str | None = None
    role: str | None = None
    url: str | None = None
    status: Status = "draft"
    created: str = Field(default_factory=lambda: date.today().isoformat())
    updated: str = Field(default_factory=lambda: date.today().isoformat())
    notes: list[str] = Field(default_factory=list)
    # Snapshot of what was actually sent, so a later profile edit can't rewrite history.
    resume_pages: int | None = None
    keyword_coverage: float | None = None

    def touch(self) -> Application:
        self.updated = date.today().isoformat()
        return self


class Store(Protocol):
    def save_job(self, jd: JobDescription, user: str) -> None: ...
    def load_job(self, job_id: str, user: str) -> JobDescription: ...
    def save_resume(self, resume: TailoredResume, user: str) -> None: ...
    def load_resume(self, job_id: str, user: str) -> TailoredResume: ...
    def save_cover_letter(self, letter: CoverLetter, user: str) -> None: ...
    def load_cover_letter(self, job_id: str, user: str) -> CoverLetter: ...
    def save_application(self, app: Application, user: str) -> None: ...
    def load_application(self, job_id: str, user: str) -> Application: ...
    def list_applications(self, user: str) -> list[Application]: ...
    def delete_application(self, job_id: str, user: str) -> None: ...

    # How many resumes this user has had recast. Separate from the number of
    # applications because the two diverge: an application row exists from the
    # moment a job description is parsed, and only gets a resume once the
    # pipeline has run. Counted in the backend rather than by filtering a
    # list_applications() result, because on Postgres that would mean shipping
    # every stored resume across the wire to look at whether it is null.
    def count_resumes(self, user: str) -> int: ...
    def save_profile(self, profile: MasterProfile, user: str) -> None: ...
    def load_profile(self, user: str) -> MasterProfile | None: ...

    # Analyses are content-addressed and immutable, so the lookup is a cache
    # probe: same profile + same job + same ruleset means the stored one is still
    # correct and re-running would burn a model call for an identical answer.
    def save_analysis(self, analysis: Analysis, user: str) -> None: ...
    def load_analysis(self, analysis_id: str, user: str) -> Analysis: ...
    def find_analysis(
        self, fingerprint: str, job_id: str, ruleset: str, user: str
    ) -> Analysis | None: ...
