"""Who is calling.

Supabase issues a JWT per signed-in user and the browser sends it as a bearer
token. This verifies the signature locally and hands back the user id, which is
the partition key for every row the request goes on to touch.

Local is the important word. The project signs with an asymmetric key and
publishes the public half at a JWKS endpoint, so verification costs one cached
HTTP fetch per cold start and nothing after that — no round trip to Supabase per
request, and no shared secret stored on this side at all. Projects still on the
legacy symmetric keys have no JWKS to fetch, so SUPABASE_JWT_SECRET covers that
case; set one or the other, not both.

With SUPABASE_URL unset the gate is open and everything is attributed to the
single local user. That is how `recast serve` and the test suite run, and it is
the same rule the shared token had: unset means open.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from ..store import DEFAULT_USER

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or ""
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Supabase stamps every access token with this audience. Checking it is what
# stops a token minted for some other purpose from being replayed here.
AUDIENCE = "authenticated"

# And this role, on tokens belonging to an actual signed-in person. Same string
# as the audience, different claim and different question — one asks who the
# token was minted for, the other what it is allowed to be. The anon and
# service_role keys are also valid project-signed JWTs, and they carry neither.
USER_ROLE = "authenticated"

_jwks_client = None


def configured() -> bool:
    return bool(SUPABASE_URL)


def _issuer() -> str:
    return f"{SUPABASE_URL.rstrip('/')}/auth/v1"


def _ssl_context():
    """Trust roots for the JWKS fetch.

    PyJWKClient fetches over urllib, which uses the interpreter's own CA store —
    and a python.org build on macOS ships without one, so the fetch fails there
    with CERTIFICATE_VERIFY_FAILED while every other tool on the machine is
    fine. certifi is a declared dependency for that reason, but the import stays
    optional: falling back to the default context is correct on the Linux
    runtime this deploys to, which has system roots either way.
    """
    import ssl

    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _jwks():
    """The project's public signing keys, fetched once and cached.

    PyJWKClient keeps its own TTL cache, so this survives warm invocations and
    re-fetches on its own when Supabase rotates a key. Built lazily because a
    module-level fetch would put a network call in the import path of every
    cold start, including the ones that never verify a token.
    """
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient

        _jwks_client = PyJWKClient(
            f"{_issuer()}/.well-known/jwks.json",
            cache_keys=True,
            # Shorter than the 30s default: a hung JWKS fetch otherwise holds the
            # request open long past the point the user has given up on it.
            timeout=10,
            ssl_context=_ssl_context(),
        )
    return _jwks_client


def verify(token: str) -> str:
    """Return the user id in `token`, or raise 401.

    Every decode failure collapses to the same flat message on purpose. The
    distinction between expired, malformed and wrongly-signed is useful to us
    and useful to someone probing the endpoint, and the client's response is the
    same in all three cases: bounce to the login page.
    """
    import jwt

    options = {"require": ["exp", "sub"]}
    try:
        if JWT_SECRET:
            claims = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=["HS256"],
                audience=AUDIENCE,
                issuer=_issuer(),
                options=options,
            )
        else:
            claims = jwt.decode(
                token,
                _jwks().get_signing_key_from_jwt(token).key,
                algorithms=["ES256", "RS256"],
                audience=AUDIENCE,
                issuer=_issuer(),
                options=options,
            )
    except Exception as exc:  # noqa: BLE001 — every failure is one 401
        raise HTTPException(401, "Not signed in.") from exc

    user = claims.get("sub")
    if not user:
        raise HTTPException(401, "Not signed in.")

    # An anon-key token carries role "anon" and a null subject; a service-role
    # token carries no user at all. Neither is a person, and neither should be
    # able to read a person's rows.
    if claims.get("role") != USER_ROLE:
        raise HTTPException(401, "Not signed in.")

    return str(user)


def current_user(authorization: Annotated[str, Header()] = "") -> str:
    """FastAPI dependency: the calling user's id.

    This is the single place a request is turned into an identity. Routes take
    it and pass it to the store, so there is no ambient "current user" for a
    handler to forget to scope by — the parameter has to be threaded through.
    """
    if not configured():
        return DEFAULT_USER

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Not signed in.")

    return verify(token)


CurrentUser = Annotated[str, Depends(current_user)]
