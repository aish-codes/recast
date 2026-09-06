"""The tailored resume: a *rendering plan*, not a document.

This is the object the user edits in the UI and the object the renderer consumes.
It is deliberately not prose — it is a list of decisions ("include this bullet,
in this order, worded this way, because of this requirement"), each traceable back
to the master profile.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .analysis import Gap
from .job import JobDescription
from .profile import Contact, Education, SkillGroup


class TailoredBullet(BaseModel):
    source_id: str                  # -> MasterProfile bullet id. Never empty.
    text: str                       # what will be printed
    original: str                   # what the user wrote
    score: float = 0.0              # relevance to this JD, 0..1
    rationale: str = ""             # why it was kept / how it was reworded
    keywords_hit: list[str] = Field(default_factory=list)
    # Set by the fabrication guard. Non-empty = the rewrite introduced something
    # not present in the original. Surface this in the UI, loudly.
    flags: list[str] = Field(default_factory=list)
    locked: bool = False            # user edited it; regeneration must not touch it

    @property
    def changed(self) -> bool:
        return self.text.strip() != self.original.strip()


class TailoredExperience(BaseModel):
    source_id: str
    company: str
    title: str
    location: str | None = None
    start: str
    end: str | None = None
    bullets: list[TailoredBullet] = Field(default_factory=list)


class TailoredProject(BaseModel):
    source_id: str
    name: str
    url: str | None = None
    tech: list[str] = Field(default_factory=list)
    bullets: list[TailoredBullet] = Field(default_factory=list)


class TailoredResume(BaseModel):
    schema_version: Literal[1] = 1
    job_id: str
    company: str | None = None
    role: str | None = None

    contact: Contact
    summary: TailoredBullet | None = None
    experience: list[TailoredExperience] = Field(default_factory=list)
    projects: list[TailoredProject] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    gaps: list[Gap] = Field(default_factory=list)
    # Bullets dropped to make the page fit, in the order they were dropped.
    # Shown in the editor so trimming is never silent.
    trimmed: list[TailoredBullet] = Field(default_factory=list)

    def bullets(self) -> list[TailoredBullet]:
        out = [self.summary] if self.summary else []
        for e in self.experience:
            out.extend(e.bullets)
        for p in self.projects:
            out.extend(p.bullets)
        return out

    def coverage(self, jd: JobDescription) -> float:
        """Fraction of JD keywords that appear somewhere in the rendered text."""
        wanted = jd.keyword_tokens()
        if not wanted:
            return 1.0
        haystack = " ".join(b.text.lower() for b in self.bullets())
        haystack += " " + " ".join(s.lower() for g in self.skills for s in g.skills)
        return sum(1 for k in wanted if k in haystack) / len(wanted)


class CoverLetter(BaseModel):
    job_id: str
    company: str | None = None
    role: str | None = None
    greeting: str = "Dear Hiring Manager,"
    paragraphs: list[str] = Field(default_factory=list)
    signoff: str = "Best regards,"
    name: str = ""
    # Each paragraph's supporting bullet ids, so claims stay traceable.
    evidence: dict[int, list[str]] = Field(default_factory=dict)

    def text(self) -> str:
        body = "\n\n".join(self.paragraphs)
        return f"{self.greeting}\n\n{body}\n\n{self.signoff}\n{self.name}"
