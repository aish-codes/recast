"""Job description -> structured requirements.

Cheap, high-volume, structured: this is the `fast` model's job.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.job import JobDescription, Requirement, Seniority
from ..textutil import clean

SYSTEM = """You extract structure from job descriptions for a resume-tailoring tool.

Rules:
- Discard boilerplate: EEO statements, benefits, "we are a fast-paced team", application instructions.
- A requirement is a "must" if the posting frames it as required/essential/minimum. Otherwise "nice".
- `skill` is a short canonical lowercase token when the requirement maps to a technology or
  named competency ("terraform", "pytorch", "distributed systems"). Leave null for soft asks.
- `keywords` are literal terms an ATS would match on. Lowercase, deduplicated, no filler words.
  Include technologies, methodologies and the role title's key nouns. Aim for 15-30.
- `company_notes` are concrete, checkable facts about the company or product that a cover letter
  could honestly reference. Never invent; leave empty if the posting says nothing substantive.
"""


class _Req(BaseModel):
    """The requirement fields the model may fill — deliberately without `id`.

    Requirement carries a content-hashed id, but exposing the field in the prompt
    schema meant the model happily numbered them 1..n, and `_ensure_id` only fires
    when the id is empty. Positional ids break every stored match and gap the
    moment a JD is re-parsed in a different order, so the model never sees it.
    """

    text: str
    kind: Literal["must", "nice"] = "must"
    skill: str | None = None


class _Extraction(BaseModel):
    company: str | None = None
    role: str | None = None
    location: str | None = None
    seniority: Seniority = "unknown"
    requirements: list[_Req] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    company_notes: list[str] = Field(default_factory=list)


def parse_jd(raw: str) -> JobDescription:
    ext = structured(SYSTEM, raw.strip()[:20000], _Extraction, task="fast")
    data = ext.model_dump()
    data["requirements"] = [Requirement(**r) for r in data["requirements"]]
    jd = JobDescription(**data, raw=raw)
    jd.keywords = sorted({clean(k).lower() for k in jd.keywords if k.strip()})
    return jd.ensure_id()
