"""Which bullets make the cut.

Two stages, on purpose:

1. A deterministic keyword-overlap prescore. Free, instant, and it means the model
   only ever sees a shortlist — so cost stays flat as the master profile grows.
2. A model pass that scores relevance and says which requirement each bullet answers.

The model is only ever allowed to *rank existing bullets*. It cannot add one.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.job import JobDescription
from ..models.profile import Bullet, MasterProfile

SYSTEM = """You rank a candidate's existing resume bullets against a job description.

For each bullet id you are given, return:
- score: 0.0-1.0 relevance to THIS job. Be harsh. 0.9+ means it directly evidences a
  stated requirement. Below 0.3 means it is filler for this application.
- answers: the requirement text(s) from the JD this bullet is evidence for (verbatim, or []).
- keywords_hit: JD keywords already present in the bullet.

Score every id you were given, exactly once. Never invent ids. Never write new bullet text.
"""


class _Score(BaseModel):
    id: str
    score: float = 0.0
    answers: list[str] = Field(default_factory=list)
    keywords_hit: list[str] = Field(default_factory=list)


class _Scores(BaseModel):
    scores: list[_Score] = Field(default_factory=list)


def prescore(bullet: Bullet, jd: JobDescription) -> float:
    """Keyword overlap, normalised. No model call."""
    wanted = jd.keyword_tokens()
    if not wanted:
        return 0.0
    hits = bullet.tokens() & wanted
    return min(1.0, len(hits) / max(4, len(wanted) * 0.25))


def shortlist(profile: MasterProfile, jd: JobDescription, limit: int = 40) -> list[Bullet]:
    ranked = sorted(
        profile.all_bullets(),
        key=lambda b: (b.pinned, prescore(b, jd)),
        reverse=True,
    )
    return ranked[:limit]


def score_bullets(
    profile: MasterProfile, jd: JobDescription, limit: int = 40
) -> dict[str, _Score]:
    """Return {bullet_id: score} for the shortlist, falling back to prescore on failure."""
    candidates = shortlist(profile, jd, limit)
    if not candidates:
        return {}

    jd_block = _jd_block(jd)
    bullets_block = "\n".join(f"{b.id}: {b.text}" for b in candidates)
    user = f"JOB:\n{jd_block}\n\nBULLETS:\n{bullets_block}"

    try:
        result = structured(SYSTEM, user, _Scores, task="fast", max_tokens=6000)
        by_id = {s.id: s for s in result.scores if s.id in {b.id for b in candidates}}
    except Exception:  # noqa: BLE001 - degrade to deterministic scoring, never hard-fail
        by_id = {}

    for b in candidates:
        if b.id not in by_id:
            by_id[b.id] = _Score(id=b.id, score=prescore(b, jd))
        if b.pinned:
            by_id[b.id].score = max(by_id[b.id].score, 0.95)
    return by_id


def _jd_block(jd: JobDescription) -> str:
    lines = [f"Role: {jd.role or '?'} at {jd.company or '?'} ({jd.seniority})"]
    if jd.requirements:
        lines.append("Requirements:")
        lines += [f"- [{r.kind}] {r.text}" for r in jd.requirements]
    if jd.keywords:
        lines.append("Keywords: " + ", ".join(jd.keywords))
    return "\n".join(lines)
