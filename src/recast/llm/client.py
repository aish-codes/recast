"""One call site for every model request in the codebase.

Deliberately thin and OpenAI-compatible: Groq, OpenAI, Together, vLLM and Ollama
all speak this protocol, so swapping provider is a base_url change, not a refactor.

Two entry points:
    complete()  -> free text (cover letter prose)
    structured() -> a validated Pydantic object, with repair-retries
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypeVar

from openai import APIStatusError, OpenAI
from pydantic import BaseModel, ValidationError

from ..config import settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

_client: OpenAI | None = None


class LLMError(RuntimeError):
    pass


def client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.api_key:
            raise LLMError(
                "No API key. Copy .env.example to .env and set RECAST_API_KEY "
                "(get a free one at https://console.groq.com/keys)."
            )
        _client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.request_timeout,
        )
    return _client


def complete(
    system: str,
    user: str,
    *,
    task: str = "smart",
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    resp = client().chat.completions.create(
        model=settings.model_for(task),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def structured(
    system: str,
    user: str,
    schema: type[T],
    *,
    task: str = "fast",
    temperature: float = 0.1,
    max_tokens: int = 4000,
    retries: int = 2,
) -> T:
    """Ask for JSON matching `schema` and keep asking until it validates.

    Uses native json_schema support when the provider has it, falls back to
    json_object + an inlined schema otherwise (Groq's smaller models).
    """
    json_schema = schema.model_json_schema()
    sys_prompt = (
        f"{system}\n\nRespond with a single JSON object matching this schema. "
        f"No markdown fences, no commentary.\n\n{json.dumps(json_schema)}"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user},
    ]

    last_err = ""
    json_mode = True  # providers reject their own json mode often enough to need a fallback

    for attempt in range(retries + 2):
        try:
            raw = _call(
                messages,
                task=task,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
        except APIStatusError as exc:
            last_err = f"{exc.status_code}: {str(exc)[:400]}"
            log.warning("structured() API error on attempt %d: %s", attempt + 1, last_err)

            # 429/413 mean "too much, too fast" — the request is fine, the timing
            # isn't. Backing off is the fix; dropping json mode is not, and giving
            # up loses work that would have succeeded a second later.
            if exc.status_code in (408, 409, 413, 429, 500, 502, 503, 504):
                if attempt >= retries + 1:
                    raise LLMError(_rate_limit_help(exc)) from exc
                time.sleep(min(2 ** attempt * 1.5, 20))
                continue

            # A 400 from json mode ("failed to validate JSON", empty generation) is
            # about the constrained decoder, not the prompt. Drop the constraint and
            # rely on the schema-in-prompt plus the validation loop below.
            if json_mode:
                json_mode = False
                continue
            raise LLMError(f"Provider rejected the request: {last_err}") from exc

        try:
            return schema.model_validate_json(_strip_fences(raw))
        except (ValidationError, ValueError) as exc:
            last_err = str(exc)[:1200]
            log.warning("structured() attempt %d did not validate: %s", attempt + 1, last_err)
            if not raw.strip():
                # Empty completion: reasoning models can spend the whole budget
                # thinking. More room, no constrained decoding.
                json_mode, max_tokens = False, int(max_tokens * 1.5)
                continue
            messages += [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": f"That did not validate:\n{last_err}\n\nReturn corrected JSON only.",
                },
            ]

    raise LLMError(f"Model never produced valid {schema.__name__}. Last error: {last_err}")


def _rate_limit_help(exc: APIStatusError) -> str:
    detail = str(exc)
    if "tokens per minute" in detail or exc.status_code == 413:
        return (
            "The provider's per-minute token limit rejected this request even after "
            "backing off. Either the document is very long, or the free tier is too "
            "small for this model — try RECAST_MODEL_SMART=openai/gpt-oss-20b, or "
            "split the input."
        )
    return f"Provider is rate-limiting or unavailable: {detail[:300]}"


def _call(
    messages: list[dict[str, Any]],
    *,
    task: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    kwargs: dict[str, Any] = {
        "model": settings.model_for(task),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if settings.reasoning_effort:
        # Ignored by providers that don't do reasoning; keeps gpt-oss from burning
        # the token budget thinking about a schema fill.
        kwargs["extra_body"] = {"reasoning_effort": settings.reasoning_effort}

    resp = client().chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    # Some models prepend chatter; take the outermost JSON object.
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end > start else t
