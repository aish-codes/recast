"""Gatekeeping for uploaded files.

A resume upload is an untrusted binary from the internet that we hand to two
parsers. The checks here are the cheap ones that must happen before either parser
sees the bytes.

Deliberately not doing: virus scanning, deep PDF structure validation, or
sandboxing the parsers. Those matter at a different scale; pypdf and python-docx
on size-capped input from an authenticated single user is a proportionate risk.
Revisit when the service is public.
"""

from __future__ import annotations

from dataclasses import dataclass

from .extract import Kind, sniff

MAX_BYTES = 8 * 1024 * 1024          # 8 MB — a text resume is under 500 KB
MAX_TEXT_CHARS = 200_000             # a 40-page document, well past any real resume
MIN_BYTES = 64

ALLOWED: set[Kind] = {"pdf", "docx", "text"}


class RejectedUpload(ValueError):
    """Raised with a message intended to be shown to the user verbatim."""


@dataclass
class AcceptedUpload:
    data: bytes
    kind: Kind
    filename: str
    size: int


def accept(data: bytes, filename: str = "") -> AcceptedUpload:
    if len(data) < MIN_BYTES:
        raise RejectedUpload("That file is empty.")
    if len(data) > MAX_BYTES:
        mb = len(data) / 1024 / 1024
        raise RejectedUpload(
            f"That file is {mb:.1f} MB. The limit is {MAX_BYTES // 1024 // 1024} MB — "
            "a resume should be far smaller, so this is usually an embedded image."
        )

    try:
        kind = sniff(data, filename)
    except ValueError as exc:
        raise RejectedUpload(str(exc)) from exc

    if kind not in ALLOWED:
        raise RejectedUpload(f"Can't read {kind} files. Upload a PDF, a .docx, or paste the text.")

    if kind == "text" and len(data) > MAX_TEXT_CHARS:
        raise RejectedUpload("That text is too long to be a resume.")

    return AcceptedUpload(data=data, kind=kind, filename=filename or f"upload.{kind}", size=len(data))
