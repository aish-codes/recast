"""Constrained rewriting.

The model is given one bullet at a time (batched into a single call) and may only
rephrase it — mirror the JD's vocabulary, lead with the outcome, tighten the verb.
It may not add facts, numbers, technologies or scope.

Every rewrite then goes through `guard.check`. Hard violations are *reverted to the
user's original text*, with the flag kept so the UI can explain what happened.
Quality of the rewrite is visible to the user, so this runs on the `smart` model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.job import JobDescription
from ..models.profile import Bullet, MasterProfile
from ..textutil import clean
from . import guard

SYSTEM = """You rewrite resume bullets to fit a specific job description.

HARD CONSTRAINTS — violating any of these makes the output unusable:
- Never introduce a fact, number, metric, tool, technology, company or scope that is
  not already in the original bullet. You are rephrasing, not writing.
- Never inflate seniority ("led" when the original says "contributed to").
- Keep length within 15% of the original.
- If the original already fits the job well, return it unchanged. Unchanged is a good answer.

WHAT YOU MAY DO:
- Mirror the job description's exact vocabulary where it genuinely matches the original
  ("microservices" -> "distributed services" only if the original supports it).
- Lead with the outcome rather than the activity.
- Replace weak verbs with precise ones.
- Cut filler ("responsible for", "worked on", "helped to").

Return one entry per input id. `rationale` is one short clause explaining the change,
or "unchanged" if you left it alone.
"""


class _Rewrite(BaseModel):
    id: str
    text: str
    rationale: str = ""


class _Rewrites(BaseModel):
    rewrites: list[_Rewrite] = Field(default_factory=list)


# Flags severe enough to discard the rewrite and keep the user's words.
HARD_FLAGS = ("invented_metric", "invented_entity")


def rewrite_bullets(
    bullets: list[Bullet],
    jd: JobDescription,
    profile: MasterProfile,
    *,
    strict: bool = True,
) -> dict[str, tuple[str, str, list[str]]]:
    """-> {bullet_id: (final_text, rationale, flags)}"""
    if not bullets:
        return {}

    jd_block = _jd_block(jd)
    bullets_block = "\n".join(f"{b.id}: {b.text}" for b in bullets)
    user = f"JOB:\n{jd_block}\n\nBULLETS TO REWRITE:\n{bullets_block}"

    try:
        result = structured(SYSTEM, user, _Rewrites, task="smart", temperature=0.2, max_tokens=6000)
        proposed = {r.id: r for r in result.rewrites}
    except Exception:  # noqa: BLE001 - a failed rewrite must never lose the user's content
        proposed = {}

    vocab = guard.profile_vocabulary(profile)
    out: dict[str, tuple[str, str, list[str]]] = {}

    for b in bullets:
        r = proposed.get(b.id)
        candidate = clean(r.text) if r else ""
        if not candidate:
            out[b.id] = (b.text, "unchanged (no rewrite returned)", [])
            continue

        flags = guard.check(b.text, candidate, vocab)
        hard = [f for f in flags if f.startswith(HARD_FLAGS)]
        if strict and hard:
            out[b.id] = (b.text, f"rewrite rejected: {hard[0]}", flags)
        else:
            out[b.id] = (candidate, r.rationale or "", flags)

    return out


def _jd_block(jd: JobDescription) -> str:
    lines = [f"Role: {jd.role or '?'} at {jd.company or '?'} ({jd.seniority})"]
    if jd.requirements:
        lines.append("Requirements:")
        lines += [f"- [{r.kind}] {r.text}" for r in jd.requirements[:20]]
    if jd.keywords:
        lines.append("Keywords: " + ", ".join(jd.keywords))
    return "\n".join(lines)
