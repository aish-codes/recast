import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { supabaseConfigured } from "@/lib/supabase/config";

/**
 * Where Google sends the user back to.
 *
 * Supabase runs the OAuth dance and redirects here with a one-time code. The
 * exchange has to happen server-side because it needs to write the session
 * cookies, and it has to happen on our origin because the PKCE verifier was
 * stored in a cookie scoped to it.
 *
 * Nothing in here is allowed to throw. This route is the last hop of the sign-in
 * redirect, so an unhandled exception is not a stack trace someone will see in
 * a console — it is a bare "Internal Server Error" page shown to a user who was
 * halfway through logging in, with no way forward and nothing on screen saying
 * what went wrong. Every failure is caught and turned into a redirect back to
 * the login page carrying a message; the detail goes to the server log.
 */

/** The origin the browser actually used, which is not the one this code sees. */
function publicOrigin(request: Request, fallback: string): string {
  const forwarded = request.headers.get("x-forwarded-host");
  if (process.env.NODE_ENV === "development" || !forwarded) return fallback;

  // A request through more than one proxy carries a comma-separated list, and
  // the browser's own host is the first entry. Pasting the whole list into a URL
  // is a TypeError, which is a 500 — the thing this route must never do.
  const host = forwarded.split(",")[0].trim();
  const proto = (request.headers.get("x-forwarded-proto") ?? "https").split(",")[0].trim();

  try {
    return new URL(`${proto}://${host}`).origin;
  } catch {
    return fallback;
  }
}

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const base = publicOrigin(request, origin);

  const fail = (message: string) =>
    NextResponse.redirect(`${base}/login?error=${encodeURIComponent(message)}`);

  try {
    const code = searchParams.get("code");

    // Google's own failures (consent denied, app blocked) come back as query
    // params rather than as a failed request, so they are read out here and
    // shown on the login page instead of surfacing as a blank "no code" error.
    const oauthError = searchParams.get("error_description") ?? searchParams.get("error");

    // Open redirects are the classic bug in this handler: `next` comes from the
    // query string, so only a same-origin absolute path is allowed through.
    const requested = searchParams.get("next") ?? "/";
    const next = requested.startsWith("/") && !requested.startsWith("//") ? requested : "/";

    if (oauthError) {
      console.error("[auth/callback] provider returned an error:", oauthError);
      return fail(oauthError);
    }
    if (!code) return fail("That sign-in link was incomplete. Try again.");

    // Unset environment variables are a deployment problem, not a user problem,
    // so the log gets the specifics and the user gets a sentence they can act
    // on. Checked before createClient() so the message names the actual cause.
    if (!supabaseConfigured) {
      console.error(
        "[auth/callback] Supabase is not configured: set NEXT_PUBLIC_SUPABASE_URL and " +
          "NEXT_PUBLIC_SUPABASE_ANON_KEY on this deployment and redeploy. Note that " +
          "NEXT_PUBLIC_ values are inlined at build time, so adding them without a " +
          "rebuild leaves the browser bundle empty.",
      );
      return fail("Sign-in isn't configured on this deployment.");
    }

    const supabase = await createClient();
    if (!supabase) return fail("Sign-in isn't configured on this deployment.");

    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) {
      console.error("[auth/callback] code exchange failed:", error.message);
      return fail(error.message);
    }

    // The exchange can come back clean with nothing in it — a code that was
    // already spent, most often, from a double-submitted redirect. Landing on
    // the app in that state means the middleware bounces straight back to
    // /login with no explanation, so it is caught here instead.
    if (!data?.session) {
      console.error("[auth/callback] exchange returned no session");
      return fail("That sign-in link had already been used. Try again.");
    }

    return NextResponse.redirect(`${base}${next}`);
  } catch (err) {
    // Anything left: a Supabase URL that parses but does not resolve, a network
    // failure mid-exchange, a cookie jar that refuses a write.
    console.error("[auth/callback] unhandled failure:", err);
    return fail("Something went wrong signing you in. Please try again.");
  }
}
