"""Constrained rewriting.

The model gets every surviving bullet in one call and may only rephrase them —
mirror the JD's vocabulary, lead with the outcome, tighten the verb. It may not
add facts, numbers, technologies or scope.

What it *may* reuse is the candidate's whole profile, not just the bullet in front
of it. That distinction is the point of `_claimable_keywords`. The prompt used to
forbid anything "not already in the original bullet" while `guard.check` has
always allowed anything in `profile_vocabulary` — so the model was banned from the
one move that raises keyword coverage without inventing anything: using a job term
the candidate evidenced in their skills list or a neighbouring bullet. The prompt
was enforcing a stricter rule than the guard, and the result was copy-editing.

Claimable is still not applicable. A term is only usable where the bullet already
describes the work it names, which is a judgement the model has to make and the
guard cannot check — hence the prompt spending as much space on refusing terms as
on adopting them.

Two things are checked in code rather than asked for in the prompt, because both
are exactly decidable:

    guard.check       fabrication — invented metrics, entities, drift, stuffing
    _keyword_delta    a rewrite that drops a job keyword and adds none

Hard violations of either are *reverted to the user's original text*, with the flag
kept so the UI can explain what happened. Quality of the rewrite is visible to the
user, so this runs on the `smart` model.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..llm.client import structured
from ..models.job import JobDescription
from ..models.profile import Bullet, MasterProfile
from ..textutil import clean
from . import guard

SYSTEM = """You rewrite resume bullets to fit a specific job description.

There are two independent jobs to do on every bullet. Do both. They have
different rules, and conflating them is the usual failure: skipping the edit
because no keyword fitted, or forcing a keyword because the bullet needed an edit.

JOB 1 — EDIT. Always applies. Needs no permission from anyone:
- Lead with the outcome rather than the activity.
- Replace weak verbs with precise ones.
- Cut filler: "responsible for", "worked on", "helped to", "used for".
Most bullets need this. Do it whether or not Job 2 turns out to be possible.

JOB 2 — ADOPT THE JOB'S VOCABULARY. Only where the original licenses it:
- CLAIMABLE TERMS below is this job's vocabulary that the candidate has evidenced
  somewhere in their profile. Nothing outside that list may be added, ever.
- A term belongs only where the original bullet already describes the work that
  term names. The test: can you quote the words that license it? "'ridge
  regression model' -> machine learning" is a licence. "backend work is usually
  Python" is not.
- "Likely", "probably", "typically", "presumably" are not evidence. If that is
  your reason for a term, skip the term — and still do Job 1.
- Prefer the job's exact word to a synonym for the same thing: "machine learning"
  over "predictive modelling" when they describe the candidate's same work.

HARD CONSTRAINTS — violating any of these makes the output unusable:
- Never introduce a fact, number, metric, tool, technology, company or scope the
  candidate has not claimed.
- Never inflate seniority ("led" when the original says "contributed to").
- Stay within 20% of the original length, longer or shorter. Outside that the
  bullet is flagged to the candidate as drift, which is worse than a plain
  rewrite. Working in one term does not justify restructuring the sentence.
- Never use the same term more than twice.

Return the text unchanged only when the bullet is already tight AND carries no
licensable term. That is the exception, not the default.

Return one entry per input id. `rationale`: if you worked a term in, quote its
licence — "'LLMs' -> machine learning". Otherwise name the edit you made. If you
genuinely changed nothing, say "unchanged". Never write "tightened wording"; it
tells the reader nothing.
"""


class _Rewrite(BaseModel):
    id: str
    text: str
    rationale: str = ""


class _Rewrites(BaseModel):
    rewrites: list[_Rewrite] = Field(default_factory=list)


# Flags severe enough to discard the rewrite and keep the user's words.
HARD_FLAGS = ("invented_metric", "invented_entity")

# The same tokenisation Bullet.tokens() uses, so "claimed somewhere in the
# profile" means the same thing here as it does to the guard.
_TOKEN = re.compile(r"[a-z0-9+#.]{2,}")


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
    # "{id}: {text}", with nothing between the id and the colon. Per-bullet
    # character budgets were tried here and removed: three runs showed no effect
    # on length_drift against run-to-run variance, and anything sitting between
    # the id and its colon is something the model can echo back as part of the
    # id — at which point every lookup below misses and every bullet silently
    # falls through to "unchanged".
    bullets_block = "\n".join(f"{b.id}: {b.text}" for b in bullets)
    user = (
        f"JOB:\n{jd_block}\n\n"
        f"{_claimable_block(jd, profile, bullets)}\n\n"
        f"BULLETS TO REWRITE:\n{bullets_block}"
    )

    try:
        result = structured(SYSTEM, user, _Rewrites, task="smart", temperature=0.2, max_tokens=6000)
        proposed = {r.id: r for r in result.rewrites}
    except Exception:  # noqa: BLE001 - a failed rewrite must never lose the user's content
        proposed = {}

    vocab = guard.profile_vocabulary(profile)
    wanted = jd.keyword_tokens()
    out: dict[str, tuple[str, str, list[str]]] = {}

    for b in bullets:
        r = proposed.get(b.id)
        candidate = clean(r.text) if r else ""
        if not candidate:
            out[b.id] = (b.text, "unchanged (no rewrite returned)", [])
            continue

        flags = guard.check(b.text, candidate, vocab)
        lost, gained = _keyword_delta(b.text, candidate, wanted)

        # A rewrite that drops a job keyword and replaces it with nothing has made
        # the resume worse at the only thing it was asked to improve. Checked here
        # rather than asked for in the prompt because it is exactly decidable, and
        # the fallback costs nothing: the original is the text that had the word.
        if lost and not gained:
            flags.append(f"dropped_keyword: {', '.join(lost)}")
            if strict:
                out[b.id] = (b.text, f"rewrite rejected: it dropped '{lost[0]}'", flags)
                continue
        elif lost:
            # Traded one term for another. Legitimate — "ML pipelines" becoming
            # "machine learning pipelines" reads better — so it ships, visibly.
            flags.append(f"swapped_keyword: {', '.join(lost)} -> {', '.join(gained)}")

        hard = [f for f in flags if f.startswith(HARD_FLAGS)]
        if strict and hard:
            out[b.id] = (b.text, f"rewrite rejected: {hard[0]}", flags)
        else:
            out[b.id] = (candidate, r.rationale or "", flags)

    return out


def _keyword_delta(original: str, candidate: str, wanted: set[str]) -> tuple[list[str], list[str]]:
    """-> (job keywords the rewrite lost, job keywords it gained)."""
    before = set(_TOKEN.findall(original.lower())) & wanted
    after = set(_TOKEN.findall(candidate.lower())) & wanted
    return sorted(before - after), sorted(after - before)


def _claimable_keywords(
    jd: JobDescription, profile: MasterProfile, bullets: list[Bullet]
) -> tuple[list[str], list[str]]:
    """Split the job's keywords into (safe and missing, safe and already said).

    "Safe" means every word of the phrase appears somewhere in the candidate's own
    profile — the same set `guard.check` verifies against. That is the point of
    computing this: the guard has always allowed the whole profile's vocabulary
    while the prompt only allowed the one bullet in front of it, so the model was
    forbidden from the only move that raises keyword coverage without inventing
    anything. Handing it the intersection replaces a rule it had to guess at with
    a list it can read.

    Terms outside the list are simply not mentioned. Naming what it may not say is
    an invitation to say it.
    """
    vocab = guard.profile_vocabulary(profile)
    on_page: set[str] = set()
    for b in bullets:
        on_page |= b.tokens()

    missing: list[str] = []
    present: list[str] = []
    for keyword in jd.keywords:
        words = _TOKEN.findall(keyword.lower())
        # Every word has to be claimed. A phrase is only as safe as its rarest
        # half: "machine learning" is not evidenced by having written "learning".
        if not words or not all(w in vocab for w in words):
            continue
        (present if all(w in on_page for w in words) else missing).append(keyword)

    return missing, present


def _claimable_block(jd: JobDescription, profile: MasterProfile, bullets: list[Bullet]) -> str:
    missing, present = _claimable_keywords(jd, profile, bullets)
    if not missing and not present:
        return "CLAIMABLE TERMS: none — this job's vocabulary is not evidenced in the profile."

    lines = ["CLAIMABLE TERMS — the candidate has evidenced all of these somewhere."]
    if missing:
        lines.append(
            "  Not yet anywhere in the bullets below. These are the opportunities — "
            "use each one where a bullet genuinely supports it:\n    "
            + ", ".join(missing)
        )
    if present:
        lines.append(
            "  Already present in the bullets below. Keep them; adding more "
            "instances gains nothing:\n    " + ", ".join(present)
        )
    return "\n".join(lines)


def _jd_block(jd: JobDescription) -> str:
    lines = [f"Role: {jd.role or '?'} at {jd.company or '?'} ({jd.seniority})"]
    if jd.requirements:
        lines.append("Requirements:")
        lines += [f"- [{r.kind}] {r.text}" for r in jd.requirements[:20]]
    if jd.keywords:
        lines.append("Keywords: " + ", ".join(jd.keywords))
    return "\n".join(lines)
