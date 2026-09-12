"""Postgres backend. Two tables, both mostly JSONB.

Our domain objects are Pydantic models that already round-trip through JSON, so
shredding them into columns would buy nothing and cost every schema change a
migration. The columns that exist outside the JSON are the ones we filter and
sort on — status, company, dates.

Connection handling assumes serverless: a new short-lived connection per request
against a pooled endpoint (Neon's `-pooler` host). No global pool, because a
serverless function may be frozen between requests and a pool it holds would rot.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from ..models.analysis import Analysis
from ..models.job import JobDescription
from ..models.profile import MasterProfile
from ..models.tailored import CoverLetter, TailoredResume
from .base import Application, Totals


def _jsonb(model):
    """Adapt a Pydantic model for a jsonb column.

    Passing model_dump_json() straight in sends a text-typed parameter, and
    Postgres will not implicitly cast text to jsonb for an explicitly-typed
    parameter — it fails at insert time, not at import time. Jsonb() is the
    adapter that does it properly.
    """
    from psycopg.types.json import Jsonb

    return Jsonb(model.model_dump(mode="json"))


# user_id is the Supabase user id — the `sub` claim out of the caller's JWT.
#
# Kept portable on purpose: no foreign key to auth.users and no row-level
# security here, because both are Supabase-specific and this statement also has
# to run against a plain Postgres. The deployed database gets them from
# migrations/0001_google_auth.sql, which is the authority on that shape; this is
# the floor, not the finished article.
SCHEMA = """
create table if not exists profiles (
    user_id    uuid primary key,
    data       jsonb not null,
    updated    timestamptz not null default now()
);

create table if not exists applications (
    user_id      uuid not null,
    job_id       text not null,
    company      text,
    role         text,
    status       text not null default 'draft',
    job          jsonb not null,
    resume       jsonb,
    cover_letter jsonb,
    meta         jsonb not null default '{}'::jsonb,
    created      timestamptz not null default now(),
    updated      timestamptz not null default now(),
    primary key (user_id, job_id)
);

create index if not exists applications_user_updated
    on applications (user_id, updated desc);

-- Analyses are immutable and content-addressed: the id is a hash of
-- (resume fingerprint, job, ruleset version). A row is therefore a cache entry
-- and a history entry at once — re-analysing after a profile edit writes a new
-- row rather than overwriting, so a generated resume can always be traced to the
-- analysis it came from.
create table if not exists analyses (
    user_id            uuid not null,
    id                 text not null,
    job_id             text not null,
    resume_fingerprint text not null,
    ruleset_version    text not null,
    overall            real,
    band               text,
    data               jsonb not null,
    created            timestamptz not null default now(),
    primary key (user_id, id)
);

create index if not exists analyses_lookup
    on analyses (user_id, job_id, resume_fingerprint, ruleset_version);
"""


class PgStore:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ["DATABASE_URL"]

    @contextmanager
    def _conn(self):
        import psycopg  # imported lazily so local file-backed use needs no driver

        with psycopg.connect(self.dsn) as conn:
            yield conn

    def init_schema(self) -> None:
        with self._conn() as c:
            c.execute(SCHEMA)

    # --- applications --------------------------------------------------------

    def _upsert(self, user: str, job_id: str, **cols) -> None:
        """Write some columns of one application, creating the row if it is new.

        Update first, insert only if nothing was updated. `insert ... on conflict
        do update` reads better and is wrong here: Postgres validates the proposed
        row — NOT NULL included — *before* it looks for a conflict, so every
        partial write except `save_job` (the only one that supplies `job`) fails
        with a not-null violation on `job`, even when the row already exists and
        the update branch is the one that would have run.

        Both statements share one transaction, so a failing insert takes the
        update with it and the row is never half-written.
        """
        keys = list(cols)
        assignments = ", ".join(f"{k} = %s" for k in keys)
        placeholders = ", ".join(["%s"] * len(keys))
        with self._conn() as c:
            updated = c.execute(
                f"update applications set {assignments}, updated = now() "
                f"where user_id = %s and job_id = %s",
                [*cols.values(), user, job_id],
            ).rowcount
            if updated:
                return
            c.execute(
                f"insert into applications (user_id, job_id, {', '.join(keys)}) "
                f"values (%s, %s, {placeholders})",
                [user, job_id, *cols.values()],
            )

    def save_job(self, jd: JobDescription, user: str) -> None:
        self._upsert(user, jd.id, company=jd.company, role=jd.role, job=_jsonb(jd))

    def load_job(self, job_id: str, user: str) -> JobDescription:
        row = self._one("select job from applications where user_id=%s and job_id=%s",
                        (user, job_id))
        return JobDescription.model_validate(row[0])

    def save_resume(self, resume: TailoredResume, user: str) -> None:
        self._upsert(user, resume.job_id, resume=_jsonb(resume))

    def load_resume(self, job_id: str, user: str) -> TailoredResume:
        row = self._one("select resume from applications where user_id=%s and job_id=%s",
                        (user, job_id))
        if row[0] is None:
            raise KeyError(f"no resume for {job_id}")
        return TailoredResume.model_validate(row[0])

    def save_cover_letter(self, letter: CoverLetter, user: str) -> None:
        self._upsert(user, letter.job_id, cover_letter=_jsonb(letter))

    def load_cover_letter(self, job_id: str, user: str) -> CoverLetter:
        row = self._one("select cover_letter from applications where user_id=%s and job_id=%s",
                        (user, job_id))
        if row[0] is None:
            raise KeyError(f"no cover letter for {job_id}")
        return CoverLetter.model_validate(row[0])

    def save_application(self, app: Application, user: str) -> None:
        app.touch()
        self._upsert(
            user, app.job_id,
            company=app.company, role=app.role, status=app.status,
            meta=_jsonb(app),
        )

    def load_application(self, job_id: str, user: str) -> Application:
        with self._conn() as c:
            row = c.execute(
                "select meta from applications where user_id=%s and job_id=%s", (user, job_id)
            ).fetchone()
        if not row or not row[0]:
            return Application(job_id=job_id)
        return Application.model_validate(row[0])

    def list_applications(self, user: str) -> list[Application]:
        with self._conn() as c:
            rows = c.execute(
                "select job_id, company, role, status, meta, updated from applications "
                "where user_id=%s order by updated desc",
                (user,),
            ).fetchall()
        out = []
        for job_id, company, role, status, meta, updated in rows:
            app = Application.model_validate(meta) if meta else Application(job_id=job_id)
            # Columns win over the JSON snapshot — they are what the queries saw.
            app.job_id, app.company, app.role, app.status = job_id, company, role, status
            app.updated = updated.date().isoformat()
            out.append(app)
        return out

    def delete_application(self, job_id: str, user: str) -> None:
        with self._conn() as c:
            c.execute("delete from applications where user_id=%s and job_id=%s", (user, job_id))

    def count_resumes(self, user: str) -> int:
        # `resume is not null` is the definition of "recast": the column is
        # filled by save_resume and by nothing else, so the count is of resumes
        # the pipeline actually produced rather than of job descriptions pasted.
        with self._conn() as c:
            row = c.execute(
                "select count(*) from applications where user_id=%s and resume is not null",
                (user,),
            ).fetchone()
        return int(row[0]) if row else 0

    def totals(self) -> Totals:
        # Accounts live in auth.users, Supabase's table rather than ours. The
        # function connects as `postgres`, which can read it — the same role the
        # dashboard's SQL editor uses. A plain Postgres has no auth schema, so
        # to_regclass() (null rather than an error, which would poison the
        # transaction) decides whether to ask it or to count the ids that have
        # written something of their own instead.
        with self._conn() as c:
            recasted = c.execute(
                "select count(*) from applications where resume is not null"
            ).fetchone()[0]
            if c.execute("select to_regclass('auth.users')").fetchone()[0]:
                users = c.execute("select count(*) from auth.users").fetchone()[0]
            else:
                users = c.execute(
                    "select count(*) from "
                    "(select user_id from profiles union select user_id from applications) u"
                ).fetchone()[0]
        return Totals(users=int(users), recasted=int(recasted))

    # --- analyses ------------------------------------------------------------

    def save_analysis(self, analysis: Analysis, user: str) -> None:
        with self._conn() as c:
            c.execute(
                "insert into analyses (user_id, id, job_id, resume_fingerprint, "
                "ruleset_version, overall, band, data) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s) "
                "on conflict (user_id, id) do nothing",
                (user, analysis.id, analysis.job_id, analysis.resume_fingerprint,
                 analysis.ruleset_version, analysis.overall, analysis.band, _jsonb(analysis)),
            )

    def load_analysis(self, analysis_id: str, user: str) -> Analysis:
        row = self._one("select data from analyses where user_id=%s and id=%s",
                        (user, analysis_id))
        return Analysis.model_validate(row[0])

    def find_analysis(
        self, fingerprint: str, job_id: str, ruleset: str, user: str
    ) -> Analysis | None:
        with self._conn() as c:
            row = c.execute(
                "select data from analyses where user_id=%s and job_id=%s "
                "and resume_fingerprint=%s and ruleset_version=%s "
                "order by created desc limit 1",
                (user, job_id, fingerprint, ruleset),
            ).fetchone()
        return Analysis.model_validate(row[0]) if row else None

    # --- profile -------------------------------------------------------------

    def save_profile(self, profile: MasterProfile, user: str) -> None:
        with self._conn() as c:
            c.execute(
                "insert into profiles (user_id, data) values (%s, %s) "
                "on conflict (user_id) do update set data = excluded.data, updated = now()",
                (user, _jsonb(profile)),
            )

    def load_profile(self, user: str) -> MasterProfile | None:
        with self._conn() as c:
            row = c.execute("select data from profiles where user_id=%s", (user,)).fetchone()
        return MasterProfile.model_validate(row[0]) if row else None

    # --- helpers -------------------------------------------------------------

    def _one(self, sql: str, params: tuple):
        with self._conn() as c:
            row = c.execute(sql, params).fetchone()
        if row is None:
            raise KeyError(f"not found: {params}")
        return row
