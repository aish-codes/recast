import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { SUPABASE_ANON_KEY, SUPABASE_URL, supabaseConfigured } from "@/lib/supabase/config";

// Gate the pages on a Supabase session, and refresh it while we are here.
//
// The refresh is not incidental. Access tokens are short-lived, and only a
// server that can write cookies can rotate one — so running this on every page
// request is what stops a tab that has been open for an hour from bouncing the
// user to the login screen. It is also why `getUser()` is used rather than
// `getSession()`: getUser revalidates against the auth server, getSession
// trusts whatever the cookie says, and a cookie is user-supplied input.
//
// This is not the only line of defence. The Python API verifies the same JWT
// itself, so a request that skips the browser entirely still gets checked.
//
// With Supabase unconfigured (local dev) everything is open, which matches the
// API.

// Reachable signed out. /auth is the OAuth callback, and the two policy pages
// are linked from the footer of every page including the landing one — gating
// them behind a login is both wrong and circular, since the login page is where
// the links promise to explain what signing in agrees to.
const PUBLIC = ["/login", "/auth", "/privacy", "/terms"];

export async function middleware(req: NextRequest) {
  if (!supabaseConfigured) return NextResponse.next();

  // Reassigned by setAll below: cookie writes have to land on the response that
  // is actually returned, and that response is rebuilt once the request carries
  // the refreshed cookies.
  let res = NextResponse.next({ request: req });

  const supabase = createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll: () => req.cookies.getAll(),
      setAll: (written) => {
        written.forEach(({ name, value }) => req.cookies.set(name, value));
        res = NextResponse.next({ request: req });
        written.forEach(({ name, value, options }) => res.cookies.set(name, value, options));
      },
    },
  });

  const { pathname } = req.nextUrl;
  const isPublic = PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`));

  // A throw here is a 500 on *every* page, the login screen included, because
  // the matcher below covers all of them — so a Supabase blip or a malformed
  // URL takes the whole site down rather than one request with it. Treat a
  // failed lookup as "not signed in": the pages it guards fetch through the
  // Python API, which verifies the same JWT itself and answers 401, so falling
  // back to the login redirect loses nothing and stays fail-closed.
  const user = await supabase.auth
    .getUser()
    .then(({ data }) => data.user)
    .catch((err) => {
      console.error("[middleware] could not reach Supabase to verify the session:", err);
      return null;
    });

  if (!user && !isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    // Where they were headed, so the callback can put them back there.
    if (pathname !== "/") url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (user && pathname === "/login") {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return res;
}

export const config = {
  // /api is excluded: the Python function verifies the JWT itself and returns
  // 401, which the client turns into a redirect. Redirecting an XHR would hand
  // the caller an HTML login page instead of an error.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
