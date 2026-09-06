"""Match a profile against a job, and explain the result.

This is the stage that used to live inside `tailor()` as a private detail. It now
produces a standalone Analysis, which means the score is inspectable, the evidence
is kept, and generation can be re-run without re-deriving any of it.

Three layers, each doing what it is actually good at:

  deterministic  skill presence, keyword coverage, seniority distance — free,
                 reproducible, and not something a model should be guessing at
  llm            whether a bullet genuinely evidences a responsibility, which is a
                 judgement call and the one thing worth paying for
  semantic       not implemented — see the note on gap classification below

Scoring weights are a product decision, not physics, and they are stated in one
place (WEIGHTS) so they can be argued with. The principle behind them: weight by
what actually gets a resume rejected. An unmet must-have or a two-level seniority
mismatch is usually fatal; keyword coverage almost never is, which is why it is
deliberately the smallest term.
"""

from __future__ import annotations

from ..models.analysis import (
    RULESET_VERSION,
    Analysis,
    Evidence,
    Gap,
    RequirementMatch,
    SubScore,
)
from ..models.job import JobDescription, Requirement
from ..models.profile import MasterProfile
from . import guard, select

WEIGHTS: dict[str, float] = {
    "must_have_requirements": 0.35,
    "responsibility_evidence": 0.20,
    "skill_overlap": 0.15,
    "seniority_fit": 0.15,
    "nice_to_haves": 0.08,
    "keyword_coverage": 0.07,
}

# Bullet relevance thresholds. Named rather than inline so the gap categories and
# the verdicts cannot drift apart.
STRONG = 0.7
PARTIAL = 0.45
WEAK = 0.25

_SENIORITY_ORDER = [
    "intern", "junior", "mid", "senior", "staff", "lead", "principal",
]


def analyze(profile: MasterProfile, jd: JobDescription) -> Analysis:
    """Score a profile against a job. One model call, everything else deterministic."""
    scores = select.score_bullets(profile, jd)
    index = profile.bullet_index()
    vocab = guard.profile_vocabulary(profile)

    bullet_scores = {bid: round(s.score, 3) for bid, s in scores.items()}
    bullet_answers = {bid: list(s.answers) for bid, s in scores.items() if s.answers}

    matches = [
        _match_requirement(req, scores, index, vocab) for req in jd.requirements
    ]
    hit, missed = _keyword_split(profile, jd)
    subscores = _subscores(profile, jd, matches, hit, missed)

    overall = sum(s.contribution for s in subscores)
    analysis = Analysis(
        resume_fingerprint=profile.fingerprint(),
        job_id=jd.id,
        ruleset_version=RULESET_VERSION,
        overall=round(overall, 4),
        band=_band(overall, matches),
        subscores=subscores,
        matches=matches,
        gaps=[g for g in (_gap_for(m, vocab) for m in matches) if g],
        bullet_scores=bullet_scores,
        bullet_answers=bullet_answers,
        keywords_hit=hit,
        keywords_missed=missed,
    )
    return analysis.ensure_id()


# --- per-requirement ---------------------------------------------------------


def _match_requirement(req: Requirement, scores, index, vocab: set[str]) -> RequirementMatch:
    """Collect the bullets that speak to one requirement, and rate the result."""
    needle = (req.skill or "").lower().strip()
    evidence: list[Evidence] = []

    for bullet_id, s in scores.items():
        bullet = index.get(bullet_id)
        if bullet is None:
            continue

        # Three independent ways a bullet can count. The deterministic ones matter
        # most: which requirements the scoring pass chooses to cite varies between
        # runs, so an analysis that depends only on that is not reproducible.
        mentions = bool(needle) and _mentions_skill(bullet, needle)
        cited = any(_similar(a, req.text) for a in s.answers)
        textual = _similar(bullet.text, req.text)

        # A requirement naming a specific technology needs that technology present.
        # Otherwise "Go, for our newer services" collects every bullet about a
        # service — and a substring test would also match the "go" inside ArgoCD.
        if needle and cited and not mentions:
            cited = False

        if not (mentions or cited or textual):
            continue

        reason = (f"names '{needle}'" if mentions
                  else "cited by scoring" if cited
                  else "covers the requirement's terms")
        evidence.append(Evidence(
            bullet_id=bullet_id,
            excerpt=bullet.text[:160],
            reason=reason,
            score=round(s.score, 3),
        ))

    evidence.sort(key=lambda e: -e.score)
    best = evidence[0].score if evidence else 0.0

    # Deterministic backstop: a named skill present in the user's own vocabulary
    # is evidence even when nothing scored well for this job.
    in_vocab = bool(needle) and all(
        part in vocab for part in needle.split() if len(part) > 2
    )

    if best >= STRONG:
        verdict, method = "strong", "llm"
    elif best >= PARTIAL or (in_vocab and best >= WEAK):
        verdict, method = "partial", "llm"
    elif in_vocab:
        verdict, method = "partial", "deterministic"
    elif best >= WEAK:
        verdict, method = "weak", "llm"
    else:
        verdict, method = "absent", "deterministic"

    return RequirementMatch(
        requirement_id=req.id,
        requirement=req.text,
        skill=req.skill,
        kind=req.kind,
        verdict=verdict,
        confidence=round(max(best, 0.6 if in_vocab else 0.0), 3),
        evidence=evidence[:4],
        method=method,
    )


def _gap_for(m: RequirementMatch, vocab: set[str]) -> Gap | None:
    """Classify what kind of gap this is — the actionable distinction.

    Driven by how strong the evidence actually is, not merely whether any exists.
    That distinction is load-bearing: a weak textual overlap is not the same as
    "you have this, described differently", and telling someone they hold
    accessibility experience they do not have is worse than telling them nothing.

    Only "missing" needs the user to supply new information. The other three are
    generation problems, which is a far more useful thing to be told.
    """
    if m.verdict == "strong":
        return None

    best = max((e.score for e in m.evidence), default=0.0)
    # The canonical skill token first — it is the reliable signal, and it is
    # often too short to survive the distinctive-word filter ("Go", "R", "C#").
    in_vocab = bool(m.skill) and all(
        part in vocab for part in m.skill.lower().split() if len(part) > 1
    )
    if not in_vocab:
        in_vocab = any(w in vocab for w in _distinctive(m.requirement) if len(w) > 4)

    if in_vocab and m.verdict in ("partial", "weak"):
        # They can claim it — the resume just never demonstrates it.
        category, confidence = "underrepresented", "high"
        suggestion = "You list this but no bullet demonstrates it. Worth a bullet of its own."
    elif best >= PARTIAL:
        # Real evidence, different vocabulary. Generation can mirror their term.
        category, confidence = "semantically_equivalent", "high"
        suggestion = "You have this, described in other words. Generation can mirror their term."
    elif best >= WEAK or (m.evidence and in_vocab):
        category, confidence = "transferable", "low"
        suggestion = "Adjacent experience only. Judge whether it is honest to claim."
    else:
        category, confidence = "missing", "high"
        suggestion = (
            "Nothing in your profile evidences this. Answer it with `recast fill` "
            "if you have the experience, or accept the gap."
        )

    return Gap(
        requirement_id=m.requirement_id,
        requirement=m.requirement,
        kind=m.kind,
        category=category,
        confidence=confidence,
        evidence=m.evidence[:2],
        suggestion=suggestion,
    )


# --- scoring -----------------------------------------------------------------


def _subscores(profile, jd, matches, hit, missed) -> list[SubScore]:
    musts = [m for m in matches if m.kind == "must"]
    nices = [m for m in matches if m.kind == "nice"]

    def satisfaction(group: list[RequirementMatch]) -> float:
        if not group:
            return 1.0
        credit = {"strong": 1.0, "partial": 0.6, "weak": 0.25, "absent": 0.0}
        return sum(credit[m.verdict] for m in group) / len(group)

    must_score = satisfaction(musts)
    nice_score = satisfaction(nices)

    responsibilities = [m for m in matches if not m.requirement_id.startswith("__")]
    resp_score = (
        sum(1 for m in responsibilities if m.evidence) / len(responsibilities)
        if responsibilities else 0.0
    )

    skills = {s.lower() for s in profile.all_skills()}
    wanted = {(r.skill or "").lower() for r in jd.requirements if r.skill}
    skill_score = len(skills & wanted) / len(wanted) if wanted else 1.0

    sen_score, sen_detail = _seniority(profile, jd)
    kw_score = len(hit) / (len(hit) + len(missed)) if (hit or missed) else 1.0

    unmet = [m.requirement_id for m in musts if not m.satisfied]
    return [
        SubScore(name="Must-have requirements", score=round(must_score, 4),
                 weight=WEIGHTS["must_have_requirements"], inputs=unmet,
                 detail=f"{len(musts) - len(unmet)}/{len(musts)} met" if musts else "none stated"),
        SubScore(name="Responsibility evidence", score=round(resp_score, 4),
                 weight=WEIGHTS["responsibility_evidence"],
                 inputs=[m.requirement_id for m in responsibilities if not m.evidence],
                 detail=f"{sum(1 for m in responsibilities if m.evidence)} of "
                        f"{len(responsibilities)} backed by a bullet"),
        SubScore(name="Skill overlap", score=round(skill_score, 4),
                 weight=WEIGHTS["skill_overlap"], inputs=sorted(wanted - skills),
                 detail=f"{len(skills & wanted)}/{len(wanted)} named skills present"
                        if wanted else "no named skills in the posting"),
        SubScore(name="Seniority fit", score=round(sen_score, 4),
                 weight=WEIGHTS["seniority_fit"], detail=sen_detail),
        SubScore(name="Nice-to-haves", score=round(nice_score, 4),
                 weight=WEIGHTS["nice_to_haves"],
                 inputs=[m.requirement_id for m in nices if not m.satisfied],
                 detail=f"{sum(1 for m in nices if m.satisfied)}/{len(nices)} met"
                        if nices else "none stated"),
        SubScore(name="Keyword coverage", score=round(kw_score, 4),
                 weight=WEIGHTS["keyword_coverage"], inputs=missed[:20],
                 detail=f"{len(hit)}/{len(hit) + len(missed)} terms on the page — "
                        "a diagnostic, not a target"),
    ]


def _seniority(profile: MasterProfile, jd: JobDescription) -> tuple[float, str]:
    """A step function, not a line: two levels off is disqualifying either way.

    Over-qualification is penalised more gently than under-qualification, because
    it costs you an interview far less often.
    """
    if jd.seniority == "unknown":
        return 1.0, "not stated in the posting"

    titles = " ".join(e.title.lower() for e in profile.experience)
    theirs = _SENIORITY_ORDER.index(jd.seniority) if jd.seniority in _SENIORITY_ORDER else 2
    mine = max(
        (_SENIORITY_ORDER.index(level) for level in _SENIORITY_ORDER if level in titles),
        default=None,
    )
    if mine is None:
        return 0.7, f"they want {jd.seniority}; your titles don't state a level"

    delta = mine - theirs
    if delta == 0:
        return 1.0, f"{jd.seniority} — matched"
    if delta > 0:
        return (0.9 if delta == 1 else 0.75), \
            f"they want {jd.seniority}; you read as {_SENIORITY_ORDER[mine]}"
    if delta == -1:
        return 0.6, f"they want {jd.seniority}; you read one level below"
    return 0.25, f"they want {jd.seniority}; you read {-delta} levels below"


def _keyword_split(profile: MasterProfile, jd: JobDescription) -> tuple[list[str], list[str]]:
    """Keyword presence against the profile, before any tailoring happens."""
    haystack = " ".join(
        [b.text for b in profile.all_bullets()] + profile.all_skills()
    ).lower()
    hit, missed = [], []
    for kw in jd.keywords:
        (hit if kw.lower() in haystack else missed).append(kw)
    return hit, missed


def _band(overall: float, matches: list[RequirementMatch]) -> str:
    """The headline. A number alone invites more trust than it has earned.

    An unmet must-have caps the band regardless of the arithmetic — a 78% with a
    hard requirement missing is not a "strong" match, whatever the weights say.
    """
    unmet_musts = [m for m in matches if m.kind == "must" and not m.satisfied]
    if unmet_musts:
        return "weak" if len(unmet_musts) > 1 else "partial"
    if overall >= 0.75:
        return "strong"
    if overall >= 0.5:
        return "partial"
    return "weak"


# Words that appear in almost every requirement and therefore distinguish nothing.
# Without this, "Go, for our newer services" matches any bullet mentioning a
# service, because the only long words left are "newer" and "services".
_GENERIC = {
    "experience", "experiences", "service", "services", "team", "teams", "work",
    "working", "using", "strong", "familiarity", "knowledge", "ability", "years",
    "newer", "with", "our", "the", "and", "for", "role", "skills", "including",
    "understanding", "proficiency", "excellent", "good", "solid", "hands",
    "plus", "bonus", "nice", "have", "must", "should", "would", "well",
}


def _distinctive(requirement: str) -> set[str]:
    import re

    return {
        w for w in re.findall(r"[a-z0-9+#.]{3,}", requirement.lower())
        if w not in _GENERIC
    }


def _mentions_skill(bullet, skill: str) -> bool:
    """Word-boundary match, tolerant of the usual naming drift.

    Boundaries matter: a substring test says "go" is present in "ArgoCD".
    Stem tolerance matters too: profiles say "Postgres" where postings say
    "PostgreSQL", and treating those as different skills is just wrong.
    """
    import re

    haystack = f"{bullet.text} {' '.join(bullet.tags)}".lower()
    if re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", haystack):
        return True
    if len(skill) >= 6:
        stem = skill[:6]
        return any(w.startswith(stem) for w in re.findall(r"[a-z0-9+#.]+", haystack))
    return False


def _similar(text: str, requirement: str) -> bool:
    """Does `text` speak to `requirement`?

    Two distinctive words agreeing is evidence; one is usually coincidence at this
    scale. The exception is a single long, specific word — "payments" or
    "mentoring" carries the whole requirement on its own in a way "services" never
    does, and that is exactly the case a flat threshold gets wrong.
    """
    words = _distinctive(requirement)
    if not words:
        return False
    hay = text.lower()
    matched = [w for w in words if w in hay or w.rstrip("sd") in hay]
    if len(matched) >= 2:
        return True
    return len(matched) == 1 and len(matched[0]) >= 7
