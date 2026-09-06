"""Deterministic anti-fabrication checks on every rewritten bullet.

The tailoring prompt tells the model not to invent things. That is necessary and
insufficient. This module verifies it afterwards, with no model in the loop:

    invented_metric  a number appears in the rewrite that is not in the original
    invented_entity  a proper noun / technology appears that the user never claimed
                     anywhere in their master profile
    length_drift     the rewrite is materially longer or shorter than the original
    keyword_stuffing the same JD keyword repeated beyond plausibility

A flagged bullet is never silently dropped or silently shipped — it is surfaced to
the user with the original alongside it. This is the check that makes the tool
safe to actually send.
"""

from __future__ import annotations

import re

from ..models.profile import MasterProfile

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")
_SENTENCE_END = (".", "!", "?", ";", ":")

# Numbers are compared by VALUE, not by spelling. "40M", "40 million" and
# "40,000,000" are the same claim; "zero" and "0%" are the same claim. Comparing
# strings here produced a steady drip of false rejections of honest rewrites.
_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_MAGNITUDES = {
    "hundred": 1e2, "k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9, "lakh": 1e5, "crore": 1e7,
}
_NUM_TOKEN = re.compile(
    r"(\d+(?:\.\d+)?|\b(?:" + "|".join(_NUM_WORDS) + r")\b)\s*([a-z%]*)", re.IGNORECASE
)

# Capitalised mid-sentence in ordinary writing, and not entities.
_BENIGN_CAPS = {"i", "a", "the"}


def _trim(token: str) -> str:
    """Strip trailing sentence punctuation so 'effort.' matches 'effort'."""
    return token.rstrip(".,;:-/")


def _numeric_claims(text: str) -> dict[float, str]:
    """-> {numeric value: the substring that expressed it}."""
    flat = text.lower().replace(",", "")
    out: dict[float, str] = {}
    for m in _NUM_TOKEN.finditer(flat):
        raw, suffix = m.group(1), (m.group(2) or "").strip("%")
        base = _NUM_WORDS.get(raw)
        if base is None:
            try:
                base = float(raw)
            except ValueError:
                continue
        value = float(base) * _MAGNITUDES.get(suffix, 1.0)
        out.setdefault(value, m.group(0).strip())
    return out


def profile_vocabulary(profile: MasterProfile) -> set[str]:
    """Every term the user has claimed anywhere in their own profile.

    A rewrite may reuse anything in here. Anything outside it is unverifiable.
    """
    parts: list[str] = []
    for b in profile.all_bullets():
        parts.append(b.text)
        parts.extend(b.tags)
    for e in profile.experience:
        parts += [e.company, e.title, e.location or "", e.summary or ""]
    for p in profile.projects:
        parts += [p.name, p.description or "", *p.tech]
    for ed in profile.education:
        parts += [ed.institution, ed.degree, ed.field or "", ed.detail or ""]
    parts += profile.all_skills()
    parts += profile.certifications
    parts.append(profile.contact.name)
    joined = " ".join(parts).lower()
    return {_trim(w) for w in _WORD.findall(joined)}


def _accounted_for(part: str, original_words: set[str], original_low: str, vocab: set[str]) -> bool:
    p = part.lower()
    # The substring check catches parts the word regex can't isolate: "TB" lives
    # inside "8TB", which never starts a word token.
    return p in original_words or p in vocab or (len(p) >= 2 and p in original_low)


def _entity_shaped(part: str, *, at_sentence_start: bool) -> bool:
    """Does this look like a name/technology rather than ordinary prose?"""
    if len(part) < 2:
        return False
    return (
        (part[0].isupper() and not at_sentence_start)
        or any(c.isdigit() for c in part)
        or "." in part[1:-1]  # internal dot ("node.js"), not sentence-final
    )


def check(
    original: str,
    rewritten: str,
    vocab: set[str],
    *,
    max_drift: float = 0.25,
) -> list[str]:
    flags: list[str] = []

    before = _numeric_claims(original)
    invented = {v: s for v, s in _numeric_claims(rewritten).items() if v not in before}
    if invented:
        flags.append(f"invented_metric: {', '.join(sorted(invented.values()))}")

    original_low = original.lower()
    original_words = {_trim(w) for w in _WORD.findall(original_low)}
    unverified: set[str] = set()
    prev_end, prev_raw = 0, ""
    for m in _WORD.finditer(rewritten):
        raw = m.group(0)
        gap = rewritten[prev_end : m.start()]
        # A capital at the start of a sentence says nothing about entity-hood —
        # "Eliminated the duplicate-payout class" is a verb, not a product.
        sentence_start = (
            prev_end == 0
            or prev_raw.endswith(_SENTENCE_END)
            or any(c in _SENTENCE_END for c in gap)
        )
        prev_end, prev_raw = m.end(), raw

        token = _trim(raw)
        low = token.lower()
        if not token or low in original_words or low in vocab or low in _BENIGN_CAPS:
            continue

        # Compounds get split: "Airflow-driven" and "TB/week" are recombinations of
        # terms the user already claimed, not new claims. Flag only when a part is
        # both entity-shaped and unaccounted for.
        parts = [p for p in re.split(r"[-/]", token) if p]
        for i, part in enumerate(parts):
            if _accounted_for(part, original_words, original_low, vocab):
                continue
            if _entity_shaped(part, at_sentence_start=sentence_start and i == 0):
                unverified.add(token)
                break
    if unverified:
        flags.append(f"invented_entity: {', '.join(sorted(unverified))}")

    if original.strip():
        drift = abs(len(rewritten) - len(original)) / len(original)
        if drift > max_drift:
            direction = "longer" if len(rewritten) > len(original) else "shorter"
            flags.append(f"length_drift: {int(drift * 100)}% {direction}")

    lowered = rewritten.lower()
    for word in set(_WORD.findall(lowered)):
        if len(word) > 3 and lowered.count(word) >= 3:
            flags.append(f"keyword_stuffing: '{word}' x{lowered.count(word)}")
            break

    return flags
