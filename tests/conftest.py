"""Keep the developer's .env out of the test run.

`recast.config` calls `load_dotenv()` at import, so without this the suite picks
up whatever is in .env — and .env is a working deployment. That meant tests ran
against the real Supabase Postgres: `test_profile_round_trip` read the
developer's actual resume and `test_status_update_and_delete` deleted real
applications trying to get to an empty list.

python-dotenv never overwrites a key that is already set, so blanking them here
is enough to win, and it works because this file is imported before any test
module pulls in `recast`. Blank rather than absent is deliberate: `os.getenv`
returns the empty string instead of falling back to a default, which is exactly
the "not configured" branch each of these guards.

Anything a test does want configured, it sets itself — see the `signed_in`
fixture in test_api.py.
"""

from __future__ import annotations

import os

# Storage: force the local file backend, which every fixture already assumes.
os.environ["DATABASE_URL"] = ""

# Auth: force the open, unauthenticated branch.
os.environ["SUPABASE_URL"] = ""
os.environ["NEXT_PUBLIC_SUPABASE_URL"] = ""
os.environ["SUPABASE_JWT_SECRET"] = ""

# Not blanked but removed: an empty RECAST_USER would become the user id itself
# rather than falling back to DEFAULT_USER.
os.environ.pop("RECAST_USER", None)
