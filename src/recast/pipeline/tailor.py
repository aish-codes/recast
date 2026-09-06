"""Assemble a TailoredResume from a MasterProfile and a JobDescription.

Order of operations matters:
    analyse (once) -> budget the page -> rewrite what survives

Matching used to happen here. It now lives in `analyze.py` and arrives as a stored
Analysis, so generation never re-scores: changing the page budget, the template or
the cover-letter tone reuses the same analysis instead of paying for it again. Pass
`analysis=` to reuse one; omit it and this computes a fresh one.

Rewriting is the expensive step, so it happens last and only on bullets that made
the cut. Selection and ordering are deterministic given the scores; the model never
decides layout.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.analysis import Analysis
from ..models.job import JobDescription
from ..models.profile import MasterProfile, SkillGroup
from ..models.tailored import (
    TailoredBullet,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
)
from . import rewrite
from .analyze import analyze


@dataclass
class TailorConfig:
    """Caps here exist to drop *irrelevant* content, never to hit a page count.

    Page fitting is the renderer's problem and it is opt-in — a resume that runs to
    a second page is a fine resume. These numbers are set generously on purpose:
    the tailoring decision should be "does this speak to the job", not "is there
    room". Tighten them only if you actively want a shorter document.
    """

    max_bullets_total: int = 24
    max_bullets_per_role: int = 7
    max_projects: int = 4
    min_score: float = 0.25
    include_summary: bool = True
    strict_guard: bool = True
    # Always keep at least this many bullets on the most recent role, even if the
    # JD match is weak — a role with one bullet reads as a gap in employment.
    min_bullets_recent_role: int = 2


def tailor(
    profile: MasterProfile,
    jd: JobDescription,
    cfg: TailorConfig | None = None,
    analysis: Analysis | None = None,
) -> TailoredResume:
    cfg = cfg or TailorConfig()
    analysis = analysis or analyze(profile, jd)
    index = profile.bullet_index()

    def score_of(bullet_id: str) -> float:
        return analysis.bullet_scores.get(bullet_id, 0.0)

    def hits_of(bullet_id: str) -> list[str]:
        """Which of the job's keywords this bullet already contains."""
        bullet = index.get(bullet_id)
        return sorted(bullet.tokens() & jd.keyword_tokens()) if bullet else []

    # --- decide what goes on the page (deterministic) ------------------------
    keep: list[str] = []
    experiences: list[tuple] = []
    for idx, exp in enumerate(profile.experience):
        ranked = sorted(
            (b for b in exp.bullets if not b.hidden),
            key=lambda b: (b.pinned, score_of(b.id)),
            reverse=True,
        )
        floor = cfg.min_bullets_recent_role if idx == 0 else 0
        chosen = [b for b in ranked if b.pinned or score_of(b.id) >= cfg.min_score]
        if len(chosen) < floor:
            chosen = ranked[:floor]
        chosen = chosen[: cfg.max_bullets_per_role]
        experiences.append((exp, chosen))
        keep += [b.id for b in chosen]

    projects = []
    if profile.projects:
        ranked_projects = sorted(
            profile.projects,
            key=lambda p: max((score_of(b.id) for b in p.bullets), default=0.0),
            reverse=True,
        )
        for proj in ranked_projects[: cfg.max_projects]:
            chosen = [
                b
                for b in sorted(proj.bullets, key=lambda b: score_of(b.id), reverse=True)
                if b.pinned or score_of(b.id) >= cfg.min_score
            ][:3]
            if chosen:
                projects.append((proj, chosen))
                keep += [b.id for b in chosen]

    # Cap the page budget before rewriting rather than after: rewriting is the
    # expensive step and the fit loop would only throw the surplus away.
    surplus = len(keep) - cfg.max_bullets_total
    if surplus > 0:
        expendable = sorted(
            (b for _, chosen in experiences for b in chosen if not b.pinned),
            key=lambda b: score_of(b.id),
        )
        for bullet in expendable[:surplus]:
            for exp, chosen in experiences:
                if bullet in chosen and len(chosen) > cfg.min_bullets_recent_role:
                    chosen.remove(bullet)
                    keep.remove(bullet.id)
                    break

    summary_bullet = None
    if cfg.include_summary and profile.summaries:
        summary_bullet = max(profile.summaries, key=lambda b: score_of(b.id))
        keep.append(summary_bullet.id)

    # --- rewrite only what survived -----------------------------------------
    to_rewrite = [index[bid] for bid in dict.fromkeys(keep) if bid in index]
    rewritten = rewrite.rewrite_bullets(to_rewrite, jd, profile, strict=cfg.strict_guard)

    def make(bullet_id: str) -> TailoredBullet:
        src = index[bullet_id]
        text, rationale, flags = rewritten.get(bullet_id, (src.text, "unchanged", []))
        return TailoredBullet(
            source_id=bullet_id,
            text=text,
            original=src.text,
            score=round(score_of(bullet_id), 3),
            rationale=rationale,
            keywords_hit=hits_of(bullet_id),
            flags=flags,
        )

    resume = TailoredResume(
        job_id=jd.id,
        company=jd.company,
        role=jd.role,
        contact=profile.contact,
        summary=make(summary_bullet.id) if summary_bullet else None,
        experience=[
            TailoredExperience(
                source_id=exp.id,
                company=exp.company,
                title=exp.title,
                location=exp.location,
                start=exp.start,
                end=exp.end,
                bullets=[make(b.id) for b in chosen],
            )
            for exp, chosen in experiences
        ],
        projects=[
            TailoredProject(
                source_id=proj.id,
                name=proj.name,
                url=proj.url,
                tech=_order_by_relevance(proj.tech, jd),
                bullets=[make(b.id) for b in chosen],
            )
            for proj, chosen in projects
        ],
        skills=_tailor_skills(profile, jd),
        education=profile.education,
        certifications=profile.certifications,
    )
    resume.gaps = analysis.gaps
    return resume


def baseline(profile: MasterProfile) -> TailoredResume:
    """The master profile rendered as-is: no JD, no model calls, no network.

    Useful on its own (this is your master resume) and it is the offline path for
    testing the renderer.
    """

    def plain(b) -> TailoredBullet:
        return TailoredBullet(source_id=b.id, text=b.text, original=b.text, score=0.0)

    return TailoredResume(
        job_id="baseline",
        contact=profile.contact,
        summary=plain(profile.summaries[0]) if profile.summaries else None,
        experience=[
            TailoredExperience(
                source_id=e.id,
                company=e.company,
                title=e.title,
                location=e.location,
                start=e.start,
                end=e.end,
                bullets=[plain(b) for b in e.bullets if not b.hidden],
            )
            for e in profile.experience
        ],
        projects=[
            TailoredProject(
                source_id=p.id,
                name=p.name,
                url=p.url,
                tech=p.tech,
                bullets=[plain(b) for b in p.bullets if not b.hidden],
            )
            for p in profile.projects
        ],
        skills=profile.skills,
        education=profile.education,
        certifications=profile.certifications,
    )


def _order_by_relevance(items: list[str], jd: JobDescription) -> list[str]:
    """JD-relevant terms first. Nothing is dropped — order is the only lever."""
    wanted = jd.keyword_tokens()
    return sorted(items, key=lambda s: s.lower() not in wanted)


def _tailor_skills(profile: MasterProfile, jd: JobDescription) -> list[SkillGroup]:
    wanted = jd.keyword_tokens()
    groups = [
        SkillGroup(name=g.name, skills=_order_by_relevance(g.skills, jd)) for g in profile.skills
    ]
    # Groups with a JD hit float to the top; empty groups never rendered.
    return sorted(
        [g for g in groups if g.skills],
        key=lambda g: -sum(1 for s in g.skills if s.lower() in wanted),
    )
