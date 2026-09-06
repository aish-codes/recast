"""The master profile: the single source of truth.

Everything the tailoring engine is allowed to say about the candidate lives here.
The engine selects, reorders and rephrases these objects — it never invents new ones.

Every bullet carries a stable `id`. That id is what makes editing, diffing and
provenance possible: a tailored bullet always points back at the master bullet it
came from, so the user can see exactly what was changed and why.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def _slug(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.strip().lower().encode()).hexdigest()[:n]


class Bullet(BaseModel):
    """One achievement. The atomic unit of the whole system."""

    id: str = ""
    text: str
    # Free-form tags the user controls: "python", "kubernetes", "leadership".
    # Used for cheap deterministic pre-ranking before any model is called.
    tags: list[str] = Field(default_factory=list)
    # Optional hint so the engine knows what it may lean on.
    metric: str | None = None
    # Bullets the user always wants included regardless of the JD.
    pinned: bool = False
    # Bullets the user never wants shown (kept for history).
    hidden: bool = False

    @model_validator(mode="after")
    def _ensure_id(self) -> Bullet:
        if not self.id:
            object.__setattr__(self, "id", f"b_{_slug(self.text)}")
        return self

    def tokens(self) -> set[str]:
        """Lowercased word set of text + tags, for keyword overlap scoring."""
        raw = f"{self.text} {' '.join(self.tags)}".lower()
        return set(re.findall(r"[a-z0-9+#.]{2,}", raw))


class Experience(BaseModel):
    id: str = ""
    company: str
    title: str
    location: str | None = None
    start: str                      # "2023-04" or "Apr 2023" — rendered verbatim
    end: str | None = None          # None => "Present"
    summary: str | None = None
    bullets: list[Bullet] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_id(self) -> Experience:
        if not self.id:
            object.__setattr__(self, "id", f"e_{_slug(self.company + self.title)}")
        return self


class Project(BaseModel):
    id: str = ""
    name: str
    url: str | None = None
    description: str | None = None
    tech: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_id(self) -> Project:
        if not self.id:
            object.__setattr__(self, "id", f"p_{_slug(self.name)}")
        return self


class Education(BaseModel):
    institution: str
    degree: str
    field: str | None = None
    start: str | None = None
    end: str | None = None
    detail: str | None = None


class SkillGroup(BaseModel):
    name: str                       # "Languages", "ML", "Infra"
    skills: list[str]


class Contact(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: dict[str, str] = Field(default_factory=dict)   # {"GitHub": "https://..."}


class AnswerBankEntry(BaseModel):
    """Canned answers to the questions every portal asks.

    Not used by the resume renderer — this feeds the eventual autofill layer.
    Kept in the master profile because it is the same kind of thing: user-authored
    truth that gets tailored per-application, never invented.
    """

    key: str                        # "why_this_company", "visa_status", "salary_expectation"
    question: str
    answer: str
    tailorable: bool = True         # False => must be emitted verbatim (visa, notice period)


class MasterProfile(BaseModel):
    schema_version: Literal[1] = 1
    # Where this came from. Set by the ingest path; absent for hand-written profiles.
    origin: Literal["upload", "wizard", "manual"] = "manual"
    source_filename: str | None = None
    parse_confidence: float | None = None
    contact: Contact
    headline: str | None = None
    # Several summaries, one per role archetype the user targets. The engine picks,
    # it does not write from scratch.
    summaries: list[Bullet] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    answer_bank: list[AnswerBankEntry] = Field(default_factory=list)

    def all_bullets(self) -> list[Bullet]:
        out: list[Bullet] = list(self.summaries)
        for e in self.experience:
            out.extend(e.bullets)
        for p in self.projects:
            out.extend(p.bullets)
        return [b for b in out if not b.hidden]

    def bullet_index(self) -> dict[str, Bullet]:
        return {b.id: b for b in self.all_bullets()}

    def all_skills(self) -> list[str]:
        return [s for g in self.skills for s in g.skills]

    def fingerprint(self) -> str:
        """Content hash of everything an analysis depends on.

        Used as a cache key rather than an id, so a profile edit invalidates its
        analyses automatically — no version column to remember to bump, and no way
        for a stale analysis to be served against changed content.

        Hashes the *text*, deliberately, not the bullet ids. Ids are assigned when
        a Bullet is constructed and are not recomputed when `.text` is mutated in
        place, so an id-based hash reports "unchanged" for an edited bullet and
        serves a stale analysis — which is the one failure mode a cache key exists
        to prevent.
        """
        parts = [b.text.strip() for b in self.all_bullets()]
        parts += [f"{e.company}:{e.title}:{e.start}:{e.end or ''}" for e in self.experience]
        parts += [f"{p.name}:{','.join(p.tech)}" for p in self.projects]
        parts += sorted(self.all_skills())
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]
