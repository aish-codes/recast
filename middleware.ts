import { NextResponse, type NextRequest } from "next/server";

// Gate the pages on a session cookie. The Python API checks the same secret
// itself, so this is about not rendering the app shell to a stranger — it is not
// the only line of defence.
//
// With RECAST_TOKEN unset (local dev) everything is open, which matches the API.
export function middleware(req: NextRequest) {
  const token = process.env.RECAST_TOKEN;
  if (!token) return NextResponse.next();

  if (req.cookies.get("recast_session")?.value === token) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  // /api is excluded: the Python function does its own auth and returns 401,
  // which the client turns into a redirect. Redirecting an XHR would hand the
  // caller an HTML login page instead of an error.
  matcher: ["/((?!api|login|_next/static|_next/image|favicon.ico).*)"],
};
