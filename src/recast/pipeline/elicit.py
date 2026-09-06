"""Filling gaps by asking the user, not by inventing.

When the job asks for something the profile has no evidence of, there are exactly
three honest moves, and this module implements all three:

  1. You have done it, it just isn't written down.
     Ask for the specifics — scope, stack, outcome, numbers — and compose a bullet
     *from your answers*. The model phrases; you supply every fact. The result is
     added to your master profile, so you only answer once, ever.

  2. You have done something adjacent.
     Reframe the real bullet in the job's vocabulary. Not "call it Terraform" —
     surface the part of what you actually did that speaks to the requirement.

  3. You haven't done it.
     Accept the gap. It goes in the report, and nothing goes on the resume.

There is deliberately no fourth path. A bullet with no source is a claim an
employer will act on and a background check can test, and a warning shown to you
never reaches the person reading the resume.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.job import JobDescription
from ..models.profile import Bullet, MasterProfile
from ..models.tailored import Gap, TailoredResume
from ..textutil import clean
from . import guard

RESPONSIBILITY_NOTICE = (
    "Everything on this resume traces back to something you wrote or told this tool — "
    "nothing is invented. That does not make it self-verifying: you are responsible for "
    "what you send. Assume every line will be probed in an interview and may be checked "
    "with a former employer. If you cannot talk for two minutes about a bullet, cut it."
)


# --- what to ask -------------------------------------------------------------


@dataclass
class GapPrompt:
    """One question to put to the user, with the material for either answer."""

    gap: Gap
    question: str
    # Real bullets that already sit closest to this requirement — the reframe path.
    adjacent: list[Bullet] = field(default_factory=list)

    @property
    def skill(self) -> str:
        return self.gap.requirement


def prompts_for(
    profile: MasterProfile,
    jd: JobDescription,
    gaps: list[Gap],
    *,
    musts_only: bool = True,
) -> list[GapPrompt]:
    """Turn the gap report into questions worth a user's time.

    Low-confidence gaps are included: "we couldn't confirm this" is exactly the
    case where asking beats guessing.
    """
    wanted = [g for g in gaps if g.kind == "must"] if musts_only else list(gaps)
    return [
        GapPrompt(
            gap=g,
            question=(
                f"This job asks for: {g.requirement}\n"
                "Have you actually worked on something matching this?"
            ),
            adjacent=_closest(profile, g.requirement),
        )
        for g in wanted
    ]


def _closest(profile: MasterProfile, requirement: str, n: int = 3) -> list[Bullet]:
    """Bullets sharing the most vocabulary with the requirement. No model call."""
    words = {w for w in requirement.lower().split() if len(w) > 3}
    if not words:
        return []
    scored = [(len(b.tokens() & words), b) for b in profile.all_bullets()]
    return [b for score, b in sorted(scored, key=lambda p: -p[0]) if score][:n]


# --- 1. compose from the user's own answers ----------------------------------

ANSWER_FIELDS = [
    ("scope", "What was it, and what was your part in it?"),
    ("stack", "What did you build it with?"),
    ("outcome", "What changed because you did it?"),
    ("metrics", "Any numbers you can stand behind? (blank if none)"),
]

COMPOSE_SYSTEM = """You turn a person's own description of their work into one resume bullet.

You are a copy-editor, not an author. Every fact in your output must come from the
notes you were given.

HARD CONSTRAINTS:
- Use only facts present in the notes. No invented numbers, tools, scale, team sizes or outcomes.
- If the notes give no metric, write the bullet without one. Do not estimate or imply one.
- Do not inflate the person's role. "Helped with" stays "helped with".
- One sentence, ideally two clauses: what you did, and what changed as a result.
- Lead with the outcome where the notes support it. Start with a past-tense verb.
- Mirror the job's vocabulary only where the notes genuinely match it.

Return the bullet, plus `used`: the short phrases from the notes each claim rests on.
"""


class _Composed(BaseModel):
    text: str
    used: list[str] = Field(default_factory=list)


def compose_from_answers(
    answers: dict[str, str],
    requirement: str,
    jd: JobDescription,
    profile: MasterProfile,
) -> tuple[Bullet | None, list[str]]:
    """Build a bullet out of what the user typed. -> (bullet, flags)

    The user's answers are the source of truth for the guard, so the model cannot
    add anything the user did not say. Returns None if nothing usable was given.
    """
    notes = "\n".join(f"{k}: {v.strip()}" for k, v in answers.items() if v and v.strip())
    if not notes.strip():
        return None, []

    user = (
        f"JOB REQUIREMENT THIS SHOULD SPEAK TO:\n{requirement}\n\n"
        f"JOB VOCABULARY: {', '.join(jd.keywords[:20])}\n\n"
        f"THE PERSON'S OWN NOTES:\n{notes}"
    )
    result = structured(COMPOSE_SYSTEM, user, _Composed, task="smart", temperature=0.2)
    text = clean(result.text)
    if not text:
        return None, []

    # The guard runs against the user's notes, not the profile: this is new
    # material, so the notes are the only thing that can vouch for it.
    vocab = guard.profile_vocabulary(profile) | {
        w.lower() for w in guard._WORD.findall(notes)  # noqa: SLF001
    }
    flags = [f for f in guard.check(notes, text, vocab, max_drift=10.0)
             if not f.startswith("length_drift")]

    bullet = Bullet(text=text, tags=_tags_from(answers, jd))
    return bullet, flags


def _tags_from(answers: dict[str, str], jd: JobDescription) -> list[str]:
    """Tag the new bullet with any job keywords the user's own words support."""
    said = " ".join(answers.values()).lower()
    return sorted({k for k in jd.keywords if len(k) > 2 and k in said})


def add_to_profile(profile: MasterProfile, bullet: Bullet, experience_id: str | None) -> Bullet:
    """Persist a newly-authored bullet so the user never answers that question twice."""
    for exp in profile.experience:
        if exp.id == experience_id:
            exp.bullets.append(bullet)
            return bullet
    # No role named: park it on the most recent one.
    if profile.experience:
        profile.experience[0].bullets.append(bullet)
    else:
        profile.summaries.append(bullet)
    return bullet


# --- 2. reframe adjacent real experience -------------------------------------

REFRAME_SYSTEM = """You reframe a resume bullet so that the part of it relevant to a specific job
requirement is the part a reader notices first.

You are re-emphasising, not re-labelling. The work described must stay the same work.

ALLOWED:
- Reorder the clauses so the relevant outcome leads.
- Use the job's term where the original genuinely describes that thing
  ("event-driven Celery workflow" may be framed as asynchronous message processing).
- Surface a detail already implicit in the original.

FORBIDDEN:
- Claiming a technology, scale, metric or responsibility the original does not contain.
- Renaming the work as the requirement when it is merely similar. If the bullet is
  about Airflow and the job wants Terraform, that is not a reframe — return it unchanged.
- Any new number.

Set `honest` to false and return the original text if the requirement is genuinely
not what this bullet is about. Refusing is the correct answer more often than not.
"""


class _Reframed(BaseModel):
    text: str
    honest: bool = True
    rationale: str = ""


def reframe(
    bullet: Bullet,
    requirement: str,
    jd: JobDescription,
    profile: MasterProfile,
) -> tuple[str, str, list[str]]:
    """-> (text, rationale, flags). Falls back to the original on any doubt."""
    user = (
        f"JOB REQUIREMENT:\n{requirement}\n\n"
        f"JOB VOCABULARY: {', '.join(jd.keywords[:20])}\n\n"
        f"THE BULLET, AS WRITTEN:\n{bullet.text}"
    )
    try:
        result = structured(REFRAME_SYSTEM, user, _Reframed, task="smart", temperature=0.25)
    except Exception:  # noqa: BLE001 - never lose the user's wording to an API blip
        return bullet.text, "unchanged (reframe unavailable)", []

    if not result.honest or not result.text.strip():
        return bullet.text, "unchanged — the work here isn't what the job is asking for", []

    text = clean(result.text)
    flags = guard.check(bullet.text, text, guard.profile_vocabulary(profile))
    hard = [f for f in flags if f.startswith(("invented_metric", "invented_entity"))]
    if hard:
        return bullet.text, f"reframe rejected: {hard[0]}", flags
    return text, result.rationale or "reframed toward the requirement", flags


# --- applying the results ----------------------------------------------------


def resolved_gaps(resume: TailoredResume, resolved: set[str]) -> None:
    """Drop gaps the user has now answered, in place."""
    resume.gaps = [g for g in resume.gaps if g.requirement not in resolved]
