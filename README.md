# recast

Tailor a resume to a job description without inventing anything, then check that a
machine can actually read the result.

Python end to end. The eventual UI talks to it over HTTP; the CLI is the whole tool
today.

---

## The one decision everything else follows from

The source of truth is **structured JSON**, never a text blob or a PDF.

```
MasterProfile (JSON) ─┐
                      ├─> tailoring engine ─> TailoredResume (JSON) ─> renderer ─> PDF / DOCX
JobDescription ───────┘                              ↑
                                                user edits here
```

The model is allowed to do exactly three things: **select** bullets, **order** them,
and **rephrase** them within constraints. It never writes a resume. Every bullet on
the page carries a `source_id` pointing back at a bullet the user wrote, so:

- you can diff what changed and why,
- the editor is a structured form rather than a fragile rich-text blob,
- and the model cannot give you a Kubernetes migration you never did.

The renderer is deterministic. Layout is never a model decision.

## Guard rails

Telling the model "don't invent things" is necessary and insufficient. Every rewrite
is checked afterwards, with no model in the loop
([`pipeline/guard.py`](src/recast/pipeline/guard.py)):

| flag | meaning |
|---|---|
| `invented_metric` | a numeric claim appears that the original didn't make |
| `invented_entity` | a technology or proper noun the user never claimed *anywhere* in their profile |
| `length_drift` | the rewrite is materially longer or shorter than the original |
| `keyword_stuffing` | a term repeated past plausibility |

Numbers are compared **by value**, so `40M` → `40 million` and `zero` → `0%` are
honest restatements, while `40M` → `40B` is caught. Entity checking is against the
user's *whole profile*, so reusing a skill they listed is fine; a new one is not.

The first two are hard flags: the rewrite is discarded and the user's own wording
ships instead, with the flag kept so the UI can say what happened. Nothing is
silently changed and nothing is silently dropped.

## What the ATS sees

After rendering, the PDF is read back with `pypdf` and checked
([`ats/check.py`](src/recast/ats/check.py)): did every bullet survive extraction, the
email, the phone, the section headings, the JD's keywords. The extracted text is
written to `ats.txt` — that is roughly what a parser gets.

This caught two real bugs during development: the PDF was embedding `fi` ligatures
(`first` → `ﬁrst`), and the model was emitting non-breaking hyphens (`cross‑team`).
Both extract as tokens that match nothing. Both are fixed at the source now.

## Gaps are filled by asking you

When the job wants something your profile can't evidence, `recast run` asks:
*have you actually worked on something matching this?*

- **Yes** — it asks for the specifics (scope, stack, outcome, numbers) and composes a
  bullet **from your answers**. The model phrases; you supply every fact, and the
  fabrication guard runs against your own notes rather than the profile, so it cannot
  add anything you didn't say. The bullet is saved to your master profile, so you
  answer once and every future application has it.
- **No, but something adjacent** — it reframes real work toward the requirement.
  Re-emphasis, not relabelling: if the bullet is about Airflow and the job wants
  Terraform, it returns the original unchanged. Refusing is the expected answer.
- **No** — the gap stays in the report and nothing goes on the resume.

There is deliberately no fourth path. A bullet with no source is a claim an employer
acts on and a background check can test, and a warning shown to you never reaches
the person reading the resume.

## Page count

The renderer never restructures your content to hit a page count — a resume that
runs to a second page is a fine resume. Page caps are opt-in (`--pages 1`), and even
then anything dropped lands in `resume.trimmed` rather than disappearing.

Short sections are kept whole across page breaks, so you never get three stranded
lines of Skills on page two.

---

## Run it locally

You need Python 3.11+, Node 18+, and a Groq API key (free, no card:
<https://console.groq.com/keys>).

```bash
uv venv && uv pip install -e .     # pure Python — no browser, no OS packages
npm install                        # only if you want the web UI
cp .env.example .env               # then paste your key into RECAST_API_KEY
```

### Try it without an API key

`baseline` renders your profile as-is — no job, no model calls. Good first check
that rendering works:

```bash
.venv/bin/recast baseline
open out/baseline/resume.pdf
```

### The CLI, end to end

```bash
# 1. turn your real resume into a master profile
.venv/bin/recast import ~/Documents/my-cv.pdf --profile data/profiles/me.json

# 2. save a job posting to a file, then tailor to it
.venv/bin/recast run job.txt --profile data/profiles/me.json
.venv/bin/recast run "$(pbpaste)" --profile data/profiles/me.json   # or paste it

# everything lands in out/<job_id>/
.venv/bin/recast ats <job_id> --text     # what a parser actually reads
.venv/bin/recast list                    # every application so far
```

`run` asks about anything the job wants that your profile can't evidence, and asks
whether you want a cover letter. Add `--no-fill --no-cover` to skip both.

### The web UI

Two terminals. The API on 8000, Next.js on 3000; `next.config.mjs` proxies
`/api/py/*` to the API so the browser code is identical to production.

```bash
# terminal 1
.venv/bin/uvicorn recast.api.main:api --port 8000 --reload

# terminal 2
npm run dev
```

Then <http://localhost:3000>. Both are up in about five seconds.

- `/profile` — drop in a PDF or DOCX, review what was parsed, save it
- `/` — paste a job description, get a tailored resume
- `/a/<job_id>` — the editor: every bullet with its relevance score, guard flags,
  "reworded — show original", revert, and a live preview

No login locally: with `SUPABASE_URL` unset the middleware stops gating pages and
the API attributes everything to one local user. Set it, plus the two
`NEXT_PUBLIC_SUPABASE_*` values, and both halves start enforcing Google sign-in —
see [Sign-in](#sign-in) below.

To point the API at a different profile:

```bash
RECAST_PROFILE=data/profiles/me.json .venv/bin/uvicorn recast.api.main:api --port 8000
```

### Where things go

By default everything is plain files under `out/<job_id>/` — `job.json`,
`resume.json`, `analysis.json`, `resume.pdf`, `ats.txt`, `app.json`. Diff them,
version them, edit `resume.json` and run `recast render <job_id>` to reprint for
free.

Set `DATABASE_URL` and it uses Postgres instead; `recast initdb` creates the tables.

The CLI writes as `me`, which is fine against files and rejected by Postgres —
there `user_id` is a uuid with a foreign key to `auth.users`. Set `RECAST_USER` to
your Supabase user id (`select id, email from auth.users;`) to have the CLI write
into the same rows the web app reads.

### Sign-in

Google, through Supabase Auth. Four environment variables and one migration.

| Variable | Where | What it does |
| --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | browser + server | project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | browser + server | anon/publishable key |
| `SUPABASE_URL` | Python function | same URL; the JWKS endpoint hangs off it |
| `SUPABASE_JWT_SECRET` | Python function | **legacy projects only** — omit it if the project uses asymmetric signing keys |

In the Supabase dashboard: enable Google under Authentication → Providers with a
client id and secret from Google Cloud, add
`https://<ref>.supabase.co/auth/v1/callback` as the authorised redirect URI on the
Google side, and add your deployed origin to the redirect allow-list on the
Supabase side.

Then run `migrations/0001_google_auth.sql` in the SQL editor. It moves `user_id`
from `text` to a uuid keyed on `auth.users`, and turns on row-level security —
**read the top of that file first**, it asks you to choose whether the existing
single-user rows are reassigned to your account or deleted.

How it fits together:

- The browser holds the session in cookies, via `@supabase/ssr`.
- `middleware.ts` refreshes it on every page request and redirects strangers to
  `/login`. It is not the security boundary.
- `lib/api.ts` sends the access token as a bearer header on every API call.
- `src/recast/api/auth.py` verifies that token against the project's published
  JWKS — locally, no round trip to Supabase — and hands the `sub` claim to the
  store as the user id. That is the boundary.
- Row-level security is a second wall, in front of PostgREST rather than in front
  of us: the Python function connects as the table owner and bypasses it.

### If something breaks

```bash
.venv/bin/recast models     # your provider's live model list — catalogs drift
.venv/bin/python -m pytest tests -q   # 104 tests, no API key or network needed
```

Groq's free tier is 8,000 tokens/minute, which a long resume can exceed. The client
backs off and retries; if it still fails, set `RECAST_MODEL_SMART=openai/gpt-oss-20b`.

## Model routing

One OpenAI-compatible interface for every call, so switching provider is a
`RECAST_BASE_URL` change and nothing else.

| task | model | why |
|---|---|---|
| JD parsing, bullet scoring | `fast` | high volume, structured, low quality bar |
| bullet rewriting | `smart` | quality is visible to the user here |
| cover letter | `prose` | the one place prose *is* the product |

Roughly 10–15k tokens per application — fractions of a cent.

`structured()` handles the realities: providers reject their own JSON mode, and
reasoning models sometimes spend the entire token budget thinking and return
nothing. It falls back and retries rather than failing the run.

## Layout

```
src/recast/
  models/       profile.py · job.py · tailored.py   <- the schema, start here
  llm/client.py one call site for every model request
  pipeline/     parse_jd · select · rewrite · guard · tailor · elicit · cover_letter
  render/       pdf.py (ReportLab) · docx.py · html.py + templates/ (live preview)
  ats/check.py  read our own PDF back the way a parser would
  store.py      one directory per application
  api/main.py   HTTP surface for the editor
  cli.py
```

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

50 tests, no API key or network needed — the model is stubbed. Everything that
matters for correctness here is deterministic: selection order, the guard, gap
detection, page fitting, ATS round-tripping, CSS escaping, and the editor's
API round trip.

## Not done yet

- **Resume import.** Onboarding is hand-writing `profile.json` today. A guided
  wizard beats PDF import; PDF import is lossy and should be best-effort only.
- **Editor UI.** The API is there. Next.js + TypeScript, sharing types with the
  browser extension so there's one component library across both.
- **Answer bank.** The schema holds it ([`AnswerBankEntry`](src/recast/models/profile.py));
  nothing tailors or serves it yet. This is the genuinely soul-crushing part of
  applying, and the highest-value thing left. The `elicit` module is the pattern to
  reuse — ask, don't invent.
- **Browser extension** for JD capture and form autofill — populate the fields, let
  the user review and click submit themselves.
- **Selection by marginal coverage.** Bullets are picked by individual score, so a
  bullet that's the *only* evidence for an uncovered requirement can lose to a
  higher-scoring duplicate. Greedy set-cover would fix it.

On auto-submission: automated submission to LinkedIn and Indeed while logged in
violates their terms, and it's the user's account at risk. Extension-based autofill
on the user's own machine, with the user clicking submit, is the version of this
that's both defensible and honest.
