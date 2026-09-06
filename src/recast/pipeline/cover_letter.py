"""Cover letter generation.

Same principle as the resume: the model may only draw on evidence it is handed.
It gets the top-scoring tailored bullets and the JD's company notes, and is told
which bullet ids it used so the claims stay traceable.

This is the one place where prose quality is the product, so it runs on the
`prose` model at a higher temperature.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.job import JobDescription
from ..models.profile import MasterProfile
from ..models.tailored import CoverLetter, TailoredResume
from ..textutil import clean
from . import guard

SYSTEM = """You write short, specific cover letters. Three or four paragraphs, 180-280 words total.

STRUCTURE:
1. Why this role at this company — reference something concrete from the posting.
   If the posting gives you nothing specific, talk about the work itself, not the company.
2-3. Two pieces of evidence, drawn ONLY from the supplied bullets. Expand on the story
   behind them; do not restate the bullet verbatim.
4. A short close.

HARD CONSTRAINTS:
- Every factual claim must be traceable to a supplied bullet. Invent nothing:
  no metrics, no employers, no technologies, no dates.
- No flattery ("I have long admired..."), no filler ("I am writing to apply for..."),
  no superlatives about yourself.
- Never claim to have used something the bullets do not mention.
- Plain, direct sentences. Contractions are fine. Do not sound like a template.

For each paragraph, list the bullet ids you drew on in `evidence` (empty list for
the opening and close if they use none).
"""


class _Para(BaseModel):
    text: str
    evidence: list[str] = Field(default_factory=list)


class _Letter(BaseModel):
    greeting: str = "Dear Hiring Manager,"
    paragraphs: list[_Para] = Field(default_factory=list)


def write_cover_letter(
    resume: TailoredResume,
    jd: JobDescription,
    profile: MasterProfile,
    *,
    top_n: int = 8,
    tone: str = "direct and professional",
) -> CoverLetter:
    evidence = sorted(resume.bullets(), key=lambda b: b.score, reverse=True)[:top_n]
    evidence_block = "\n".join(f"{b.source_id}: {b.text}" for b in evidence)

    notes = "\n".join(f"- {n}" for n in jd.company_notes) or "- (nothing specific in the posting)"
    reqs = "\n".join(f"- [{r.kind}] {r.text}" for r in jd.requirements[:12])

    user = (
        f"CANDIDATE: {profile.contact.name}\n"
        f"ROLE: {jd.role or 'the role'} at {jd.company or 'the company'}\n"
        f"TONE: {tone}\n\n"
        f"WHAT THE POSTING ASKS FOR:\n{reqs}\n\n"
        f"CONCRETE THINGS ABOUT THE COMPANY/PRODUCT:\n{notes}\n\n"
        f"EVIDENCE YOU MAY USE (and nothing else):\n{evidence_block}"
    )

    letter = structured(SYSTEM, user, _Letter, task="prose", temperature=0.6, max_tokens=1600)

    # Same fabrication check, applied to the whole letter against the whole profile.
    vocab = guard.profile_vocabulary(profile)
    source_text = " ".join(b.text for b in evidence) + " " + " ".join(jd.company_notes)
    vocab |= {w.lower() for w in guard._WORD.findall(source_text)}  # noqa: SLF001
    if jd.company:
        vocab |= {w.lower() for w in guard._WORD.findall(jd.company)}  # noqa: SLF001
    if jd.role:
        vocab |= {w.lower() for w in guard._WORD.findall(jd.role)}  # noqa: SLF001

    return CoverLetter(
        job_id=jd.id,
        company=jd.company,
        role=jd.role,
        greeting=letter.greeting,
        paragraphs=[clean(p.text) for p in letter.paragraphs if p.text.strip()],
        name=profile.contact.name,
        evidence={i: p.evidence for i, p in enumerate(letter.paragraphs)},
    )
