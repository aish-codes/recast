"""Structured view of a job description.

A JD is ~70% boilerplate. The job of this model is to throw that away and keep
the parts that actually drive selection: what they require, what they'd like,
what seniority, and the literal keyword set the ATS is likely matching on.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Seniority = Literal["intern", "junior", "mid", "senior", "staff", "principal", "lead", "unknown"]


class Requirement(BaseModel):
    # Content-hashed, like bullet ids: a match or a gap has to reference a
    # requirement stably, and positional ids break the moment a JD is re-parsed
    # and the model orders the list differently.
    id: str = ""
    text: str
    kind: Literal["must", "nice"] = "must"
    # Short canonical skill name if this requirement maps to one ("terraform", "pytorch").
    skill: str | None = None

    @model_validator(mode="after")
    def _ensure_id(self) -> Requirement:
        if not self.id:
            digest = hashlib.sha1(self.text.strip().lower().encode()).hexdigest()[:8]
            object.__setattr__(self, "id", f"r_{digest}")
        return self


class JobDescription(BaseModel):
    id: str = ""
    company: str | None = None
    role: str | None = None
    location: str | None = None
    seniority: Seniority = "unknown"
    requirements: list[Requirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    # Literal terms worth mirroring in the resume, lowercased.
    keywords: list[str] = Field(default_factory=list)
    # Anything about culture/mission the cover letter can honestly reference.
    company_notes: list[str] = Field(default_factory=list)
    raw: str = ""

    def ensure_id(self) -> JobDescription:
        if not self.id:
            digest = hashlib.sha1(self.raw.strip().encode()).hexdigest()[:10]
            self.id = f"jd_{digest}"
        return self

    def must_haves(self) -> list[Requirement]:
        return [r for r in self.requirements if r.kind == "must"]

    def keyword_tokens(self) -> set[str]:
        joined = " ".join(self.keywords + [r.skill or "" for r in self.requirements]).lower()
        return {t for t in re.findall(r"[a-z0-9+#.]{2,}", joined)}
