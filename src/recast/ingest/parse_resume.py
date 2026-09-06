"""Extracted text -> SourceResume.

The one LLM call in the ingest path, and the riskiest in the whole system: it runs
before any guard exists, because the profile it produces IS the ground truth
everything downstream is checked against. If the parser hallucinates here, nothing
later can catch it — `guard.py` compares rewrites against the profile, so a lie
baked into the profile becomes a fact.

So this module does the one thing available: verify the parse against the source
text it came from. Every bullet the model emits has to be traceable back to words
that were actually in the document. Anything that isn't gets flagged and surfaced
in the review screen rather than silently accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.profile import (
    Bullet,
    Contact,
    Education,
    Experience,
    MasterProfile,
    Project,
    SkillGroup,
)
from ..textutil import clean
from .extract import ExtractedDoc

SYSTEM = """You convert the raw text of a resume into structured data.

You are transcribing, not improving. This is the single most important rule: the
output becomes the candidate's permanent record and everything downstream is checked
against it, so an invented detail here can never be caught later.

RULES:
- Copy bullet text VERBATIM. Do not reword, shorten, expand, fix grammar or add metrics.
- Never infer a fact that is not written down. No guessed dates, employers, titles or
  technologies. If a field is not in the text, leave it empty.
- Do not merge two bullets into one, or split one into two.
- Dates: copy the form used in the document ("Jan 2023", "2023-01", "2023"). Use null
  for an end date when the text says Present/Current/Ongoing.
- Text extraction breaks lines mid-sentence. Rejoin a bullet that is split across lines
  into one bullet — that is repair, not rewriting.
- `summaries`: the professional summary or objective, if present, as a single entry.
- `skills`: group them the way the document groups them. If it has no groups, use one
  group named "Skills".
- Project headings are usually "name - tech, tech, tech" or "name | tech". Put ONLY the
  project's own name in `name`, and the technologies in `tech` as separate entries. The
  same applies to a role line like "Title, Company" — those are two fields, not one.
- Ignore page furniture: headers, footers, page numbers, "References available on request".

Return only what the document supports.
"""


@dataclass
class ParseResult:
    profile: MasterProfile
    confidence: float
    warnings: list[str] = field(default_factory=list)
    # Bullets the model produced that could not be found in the source text.
    unverified: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.confidence < 0.9 or bool(self.warnings) or bool(self.unverified)


# A lean schema, deliberately not MasterProfile.
#
# The full domain model's JSON schema is ~6k tokens once inlined in the prompt —
# enough on its own to blow a free-tier per-minute budget — and most of it is
# fields a parser has no business setting: stable ids, `pinned`, `hidden`, the
# answer bank. Handing the model a narrow schema is both cheaper and safer: it
# cannot populate what it is never shown.


class _PBullet(BaseModel):
    text: str


class _PExperience(BaseModel):
    company: str
    title: str
    location: str | None = None
    start: str
    end: str | None = None
    bullets: list[_PBullet] = Field(default_factory=list)


class _PProject(BaseModel):
    name: str
    url: str | None = None
    tech: list[str] = Field(default_factory=list)
    bullets: list[_PBullet] = Field(default_factory=list)


class _PEducation(BaseModel):
    institution: str
    degree: str
    field: str | None = None
    start: str | None = None
    end: str | None = None
    detail: str | None = None


class _PSkillGroup(BaseModel):
    name: str
    skills: list[str] = Field(default_factory=list)


class _PContact(BaseModel):
    name: str = ""
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: dict[str, str] = Field(default_factory=dict)


class _Parsed(BaseModel):
    contact: _PContact = Field(default_factory=_PContact)
    summary: str | None = None
    experience: list[_PExperience] = Field(default_factory=list)
    projects: list[_PProject] = Field(default_factory=list)
    education: list[_PEducation] = Field(default_factory=list)
    skills: list[_PSkillGroup] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


def _c(value: str | None) -> str | None:
    """ASCII-fold one field. Applied to every string that comes out of the parser.

    PDF text extraction hands back ligatures — "MLﬂow", "Snowﬂake", "workﬂows" are
    single U+FB02 glyphs, not the letters they look like. Bullets were being
    cleaned and everything else was not, so those landed in the skills list and
    then matched nothing: a job asking for MLflow would score zero against a
    profile that appears to list it.
    """
    return clean(value) if value else value


def _to_profile(p: _Parsed) -> MasterProfile:
    """Lean parse output -> the canonical model. IDs are generated here, not by the model."""
    return MasterProfile(
        contact=Contact(**{k: _c(v) if isinstance(v, str) else v
                           for k, v in p.contact.model_dump().items()}),
        summaries=[Bullet(text=_c(p.summary))] if p.summary else [],
        experience=[
            Experience(
                company=_c(e.company), title=_c(e.title), location=_c(e.location),
                start=_c(e.start), end=_c(e.end),
                bullets=[Bullet(text=_c(b.text)) for b in e.bullets if b.text.strip()],
            )
            for e in p.experience
        ],
        projects=[
            Project(
                name=_c(pr.name), url=pr.url, tech=[_c(x) for x in pr.tech],
                bullets=[Bullet(text=_c(b.text)) for b in pr.bullets if b.text.strip()],
            )
            for pr in p.projects
        ],
        education=[
            Education(**{k: _c(v) if isinstance(v, str) else v
                         for k, v in ed.model_dump().items()})
            for ed in p.education
        ],
        skills=[
            SkillGroup(name=_c(g.name), skills=[_c(s) for s in g.skills])
            for g in p.skills if g.skills
        ],
        certifications=[_c(x) for x in p.certifications],
    )


def parse_resume(doc: ExtractedDoc) -> ParseResult:
    if not doc.text.strip():
        raise ValueError("Nothing to parse — no text was extracted.")

    hint = ""
    if doc.headings():
        hint = "\n\nSection headings detected: " + ", ".join(doc.headings()[:15])

    parsed = structured(
        SYSTEM,
        f"RESUME TEXT:\n{doc.text[:30000]}{hint}",
        _Parsed,
        task="smart",
        temperature=0.0,
        # Counts toward the provider's per-minute token budget, so it is a real
        # cost, not just a ceiling. A parsed resume is rarely over 3k tokens.
        max_tokens=5000,
    )
    profile = _to_profile(parsed)

    warnings = list(doc.warnings)
    unverified = _unverified_bullets(profile, doc.text)
    confidence = _confidence(profile, doc, unverified)

    if not profile.contact.name:
        warnings.append("No name found — check the top of the document.")
    if not profile.contact.email:
        warnings.append("No email address found.")
    if not profile.experience:
        warnings.append("No work experience found. This usually means the layout confused the parser.")
    if unverified:
        warnings.append(
            f"{len(unverified)} bullet(s) could not be matched to the original text. "
            "Check these especially — they may have been reworded during parsing."
        )

    return ParseResult(
        profile=profile, confidence=confidence, warnings=warnings, unverified=unverified
    )


_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _unverified_bullets(profile: MasterProfile, source: str, threshold: float = 0.75) -> list[str]:
    """Bullets whose words mostly are not in the source document.

    Token overlap rather than substring: extraction mangles whitespace and hyphens,
    so an exact match is too strict, but a bullet the model invented will share
    very few content words with the page it claims to come from.
    """
    haystack = _tokens(source)
    out = []
    for bullet in profile.all_bullets():
        words = {w for w in _tokens(bullet.text) if len(w) > 3}
        if not words:
            continue
        if len(words & haystack) / len(words) < threshold:
            out.append(bullet.text)
    return out


def _confidence(profile: MasterProfile, doc: ExtractedDoc, unverified: list[str]) -> float:
    """A blunt, explainable number. Not a probability — a checklist score."""
    bullets = profile.all_bullets()
    checks = [
        bool(profile.contact.name),
        bool(profile.contact.email),
        bool(profile.experience),
        bool(bullets),
        bool(profile.skills),
        doc.looks_usable,
        not doc.warnings,
        not unverified,
    ]
    score = sum(checks) / len(checks)
    if bullets and unverified:
        # Scale by how much of the content actually traced back.
        score *= 1 - (len(unverified) / len(bullets)) * 0.5
    return round(max(0.0, min(1.0, score)), 3)


__all__ = ["ParseResult", "parse_resume"]
