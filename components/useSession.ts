"use client";

import { useEffect, useState } from "react";
import { getSupabase } from "@/lib/supabase/client";

/**
 * The signed-in Google account.
 *
 * Distinct from `useProfile`, and the distinction matters: the profile is the
 * resume you uploaded and can edit, this is the identity Google vouched for and
 * you cannot. The shell shows the profile name when there is one and falls back
 * to this, so day one — signed in, nothing uploaded yet — still has a name on it.
 *
 * `null` account means signed out; it is also what you get when Supabase is not
 * configured, which is the local-dev case where nothing is gated anyway.
 */
export type Account = {
  id: string;
  email: string;
  name: string;
  avatar: string | null;
};

export function useSession() {
  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setLoading(false);
      return;
    }

    // Subscribe before the first read so a sign-out landing mid-fetch is not
    // missed. onAuthStateChange also fires once with the current session, which
    // is what populates the state on mount.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      const user = session?.user;
      setAccount(
        user
          ? {
              id: user.id,
              email: user.email ?? "",
              // Google supplies these on the identity; a provider that doesn't
              // leaves the email as the only thing to show.
              name: (user.user_metadata?.full_name as string) ?? user.email ?? "",
              avatar: (user.user_metadata?.avatar_url as string) ?? null,
            }
          : null,
      );
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  return { account, loading };
}

/**
 * Sign out and go back to the landing page.
 *
 * A hard navigation rather than a router push: the middleware has to see the
 * cleared cookies to stop letting the pages render, and every cached profile
 * response in memory belongs to the account that just left.
 */
export async function signOut() {
  await getSupabase()?.auth.signOut();
  window.location.href = "/login";
}
