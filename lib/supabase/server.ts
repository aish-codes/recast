// Server-side Supabase client, for route handlers and server components.
//
// The cookie adapter is the whole point: reads come from the request, writes go
// back out on the response, so the refreshed session survives the round trip.
// Server components cannot set cookies at all, hence the swallowed throw — there
// the middleware has already refreshed the session, so a failed write is a
// no-op rather than a bug.
//
// Returns null when Supabase is unconfigured, mirroring the browser client.
// `createServerClient("", "")` throws, and a throw inside a route handler is a
// bare 500 with the reason buried in the platform logs — which is exactly how a
// missing environment variable used to present itself at the end of the Google
// sign-in redirect. Callers handle the null and say something useful instead.

import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { SUPABASE_ANON_KEY, SUPABASE_URL, supabaseConfigured } from "./config";

export async function createClient(): Promise<SupabaseClient | null> {
  if (!supabaseConfigured) return null;

  const store = await cookies();

  return createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (written) => {
        try {
          written.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // Called from a server component. The middleware refreshes instead.
        }
      },
    },
  });
}
