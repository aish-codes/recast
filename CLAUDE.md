# Recast

Rewrites a resume against a job description and returns a match score.

## Stack
- Next.js App Router, deployed on Vercel
- Supabase: Google OAuth, Postgres, storage
- Groq for inference

## Hard rules
- Groq key lives only in route handlers. Never in a client component.
- All DB access goes through route handlers using the anon key + the caller's JWT, so RLS applies.
- Service role key only for the keep-alive cron. Nowhere else.
- The Python rewrite service is a pure function: text in, JSON out. No Supabase credentials.
- `reference/recast-artifact.jsx` is the existing UI. Port from it; don't run it.

`reference/design/` is exported design output. Read it for layout,
spacing, type and colour. Rebuild as proper components — do not
import or copy the exported markup.