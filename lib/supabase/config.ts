// The two public Supabase values, in one place.
//
// Both are `NEXT_PUBLIC_` and both are meant to be in the browser bundle: the
// URL is a hostname and the anon key is a claim-less token that grants nothing
// on its own — row-level security on the tables is what actually gates data.
//
// Unset means "no Supabase configured", which is how local development and the
// test suite run: the middleware stops gating and the Python API attributes
// everything to the single local user. Same rule the old shared password had —
// unset is open — so `npm run dev` against a file-backed store still needs no
// setup at all.

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
