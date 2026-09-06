"""The Analysis: what we learned about a resume against one job.

Today this all happens inside `tailor()` and only a single number survives —
keyword coverage. Everything the scoring pass works out about *why* a bullet
matched is computed and thrown away, which is why the product cannot answer
"why 71%?" and why changing the cover-letter tone re-runs the whole pipeline.

Promoting it to a stored object fixes four things at once:

  * the match dashboard and gap panel have something to render
  * generation becomes cacheable on (resume, job, ruleset) instead of re-derived
  * every score carries the evidence that produced it
  * a scoring change is a version bump, not a silent behaviour change

An Analysis is immutable. Re-running with a different ruleset produces a new one.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field

# Bump when scoring logic changes in a way that should invalidate cached analyses.
RULESET_VERSION = "1.0"

Verdict = Literal["strong", "partial", "weak", "absent"]
Band = Literal["strong", "partial", "weak"]
Method = Literal["deterministic", "semantic", "llm"]

GapCategory = Literal[
    "missing",                  # no evidence anywhere in the profile
    "underrepresented",         # evidence exists but is buried or unemphasised
    "semantically_equivalent",  # the candidate has it, described in other words
    "transferable",             # adjacent experience, needs a judgement call
]


class Evidence(BaseModel):
    """One bullet, and why it counts toward one requirement."""

    bullet_id: str
    excerpt: str
    reason: str = ""
    score: float = 0.0


class RequirementMatch(BaseModel):
    requirement_id: str
    requirement: str
    # The canonical technology token, when the requirement names one. Short tokens
    # like "go" or "r" cannot be recovered from the requirement text later.
    skill: str | None = None
    kind: Literal["must", "nice"] = "must"
    verdict: Verdict = "absent"
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)
    # Which layer decided this. Makes it possible to audit the matcher itself
    # rather than only its output.
    method: Method = "deterministic"

    @property
    def satisfied(self) -> bool:
        return self.verdict in ("strong", "partial")


class SubScore(BaseModel):
    """One dimension of the overall score, with the ids that produced it.

    `inputs` is what makes the number explainable rather than assertive — the UI
    can always answer "which requirements dragged this down".
    """

    name: str
    score: float                       # 0..1
    weight: float                      # 0..1, weights sum to 1
    detail: str = ""
    inputs: list[str] = Field(default_factory=list)

    @property
    def contribution(self) -> float:
        return self.score * self.weight


class Gap(BaseModel):
    """A requirement the resume does not currently answer well.

    This is the single Gap model. It used to have a thinner twin in `tailored.py`
    with only a confidence flag; keeping two meant the tailored resume and the
    analysis could disagree about what a gap even was.

    `category` is the actionable part. Only "missing" needs the user to supply new
    information; the other three are fixable by generation, because the evidence
    already exists and is simply not being surfaced.
    """

    requirement_id: str = ""
    requirement: str
    kind: Literal["must", "nice"] = "must"
    category: GapCategory = "missing"
    confidence: Literal["high", "low"] = "high"
    evidence: list[Evidence] = Field(default_factory=list)
    suggestion: str = ""

    @property
    def fixable_by_generation(self) -> bool:
        return self.category != "missing"


class Analysis(BaseModel):
    id: str = ""
    resume_fingerprint: str = ""
    job_id: str = ""
    ruleset_version: str = RULESET_VERSION

    overall: float = 0.0
    band: Band = "weak"
    subscores: list[SubScore] = Field(default_factory=list)
    matches: list[RequirementMatch] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)

    # Bullet relevance, reused by generation so scoring is never done twice.
    bullet_scores: dict[str, float] = Field(default_factory=dict)
    bullet_answers: dict[str, list[str]] = Field(default_factory=dict)
    keywords_hit: list[str] = Field(default_factory=list)
    keywords_missed: list[str] = Field(default_factory=list)

    def ensure_id(self) -> Analysis:
        if not self.id:
            key = f"{self.resume_fingerprint}:{self.job_id}:{self.ruleset_version}"
            self.id = f"an_{hashlib.sha1(key.encode()).hexdigest()[:10]}"
        return self

    def unmet_musts(self) -> list[RequirementMatch]:
        return [m for m in self.matches if m.kind == "must" and not m.satisfied]

    def gaps_needing_you(self) -> list[Gap]:
        """The only gaps a user can actually resolve by supplying information."""
        return [g for g in self.gaps if g.category == "missing" and g.kind == "must"]

    def explain(self) -> str:
        """One line per dimension. The answer to 'why this number?'."""
        lines = [f"Overall {self.overall:.0%} ({self.band})"]
        for s in sorted(self.subscores, key=lambda s: -s.contribution):
            lines.append(
                f"  {s.name:<26} {s.score:>5.0%} × {s.weight:>4.0%} "
                f"= {s.contribution:>5.1%}   {s.detail}"
            )
        return "\n".join(lines)
