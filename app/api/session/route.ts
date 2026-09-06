import { NextResponse } from "next/server";

// Exchanges the password for an httpOnly cookie. The secret is compared on the
// server and never reaches page JavaScript in either direction.
export async function POST(req: Request) {
  const token = process.env.RECAST_TOKEN;
  if (!token) return NextResponse.json({ ok: true, open: true });

  const { password } = (await req.json().catch(() => ({}))) as { password?: string };
  if (password !== token) {
    return NextResponse.json({ error: "Wrong password." }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("recast_session", token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete("recast_session");
  return res;
}
