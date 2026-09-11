"use client";

// Browser-side Supabase client.
//
// `createBrowserClient` is the @supabase/ssr variant: it persists the session in
// cookies rather than localStorage, which is the only reason the server — the
// middleware, and any server component — can see that you are signed in. A
// plain `createClient` would work in the browser and leave every server render
// thinking you were a stranger.
//
// One instance per tab. The client holds the refresh timer and the auth state
// listeners, so constructing a second one gets you two of each fighting over the
// same cookie.

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL, supabaseConfigured } from "./config";

let instance: SupabaseClient | null = null;

/** Null when Supabase is not configured — every caller has to handle that. */
export function getSupabase(): SupabaseClient | null {
  if (!supabaseConfigured) return null;
  if (!instance) instance = createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  return instance;
}
