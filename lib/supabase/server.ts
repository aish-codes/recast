// Server-side Supabase client, for route handlers and server components.
//
// The cookie adapter is the whole point: reads come from the request, writes go
// back out on the response, so the refreshed session survives the round trip.
// Server components cannot set cookies at all, hence the swallowed throw — there
// the middleware has already refreshed the session, so a failed write is a
// no-op rather than a bug.

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { SUPABASE_ANON_KEY, SUPABASE_URL } from "./config";

export async function createClient() {
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
