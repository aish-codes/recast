import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Where Google sends the user back to.
 *
 * Supabase runs the OAuth dance and redirects here with a one-time code. The
 * exchange has to happen server-side because it needs to write the session
 * cookies, and it has to happen on our origin because the PKCE verifier was
 * stored in a cookie scoped to it.
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  // Google's own failures (consent denied, app blocked) come back as query
  // params rather than as a failed request, so they are read out here and shown
  // on the login page instead of surfacing as a blank "no code" error.
  const oauthError = searchParams.get("error_description") ?? searchParams.get("error");

  // Open redirects are the classic bug in this handler: `next` comes from the
  // query string, so only a same-origin absolute path is allowed through.
  const requested = searchParams.get("next") ?? "/";
  const next = requested.startsWith("/") && !requested.startsWith("//") ? requested : "/";

  // Behind Vercel's proxy `origin` is the internal host. The forwarded host is
  // the one the user's browser actually typed.
  const forwardedHost = request.headers.get("x-forwarded-host");
  const base =
    process.env.NODE_ENV === "development" || !forwardedHost ? origin : `https://${forwardedHost}`;

  const fail = (message: string) =>
    NextResponse.redirect(`${base}/login?error=${encodeURIComponent(message)}`);

  if (oauthError) return fail(oauthError);
  if (!code) return fail("That sign-in link was incomplete. Try again.");

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) return fail(error.message);

  return NextResponse.redirect(`${base}${next}`);
}
