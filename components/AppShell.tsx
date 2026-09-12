"use client";

/**
 * The application chrome from App.dc.html / MobileApp.dc.html.
 *
 * Two shapes of the same navigation: a 232px sidebar on desktop, a bottom tab
 * bar with a raised "tailor" action on mobile. The design's Resume Library and
 * Settings entries are deliberately absent — there is no API behind either, and
 * a nav item that goes nowhere is worse than one that isn't there.
 *
 * Home is reachable from three places on every screen: the wordmark, the Home
 * nav item, and the Home tab on mobile. All of them are <Link>s, so getting
 * back to the dashboard is a client-side transition — no reload, nothing
 * refetched, and the session cookie never touched.
 */

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AppFooter } from "./SiteFooter";
import { initials, profileBullets, useProfile } from "./useProfile";
import { signOut, useSession, type Account } from "./useSession";
import {
  IconCalendar,
  IconHome,
  IconSignOut,
  IconSparkle,
  IconTarget,
  IconUser,
  IconCheck,
} from "./icons";

/**
 * Google's picture when there is one, initials when there isn't.
 *
 * The image can 404 — Google rotates these URLs and the one in the JWT is a
 * snapshot from sign-in time — so a failure falls back to the initials rather
 * than leaving a broken frame in the sidebar.
 */
function Avatar({
  account,
  name,
  size,
}: {
  account: Account | null;
  name: string | null;
  size: number;
}) {
  const [broken, setBroken] = useState(false);
  const label = name ?? account?.name ?? "";

  if (account?.avatar && !broken) {
    return (
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={account.avatar}
        alt=""
        width={size}
        height={size}
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className="flex-none rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <span
      className="grid flex-none place-items-center rounded-full font-[650]"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.41,
        background: "var(--tint2)",
        color: "var(--accent)",
      }}
    >
      {label ? initials(label) : "–"}
    </span>
  );
}

type NavKey = "home" | "tailor" | "apps" | "profile";

const NAV: { key: NavKey; href: string; label: string; icon: typeof IconHome }[] = [
  { key: "home", href: "/", label: "Home", icon: IconHome },
  { key: "tailor", href: "/tailor", label: "Tailor Resume", icon: IconTarget },
  { key: "apps", href: "/applications", label: "My Applications", icon: IconCalendar },
  { key: "profile", href: "/profile", label: "Profile", icon: IconUser },
];

export default function AppShell({
  children,
  appCount,
  /** The editor brings its own mobile header; two stacked bars eat a phone. */
  bareMobileHeader = false,
}: {
  children: React.ReactNode;
  appCount?: number;
  bareMobileHeader?: boolean;
}) {
  const pathname = usePathname();
  // A missing profile is the day-one state, not an error — the shell shows the
  // prompt to build one instead of a name.
  const { profile } = useProfile();
  // Who Google says you are. Used for the name and picture until a profile is
  // uploaded, and for the account row's email either way.
  const { account } = useSession();
  const displayName = profile?.contact.name ?? account?.name ?? null;

  // "home" is an exact match, not the fallthrough it used to be — otherwise any
  // page outside the four below (the policy pages, reached from the footer)
  // lights up the Home tab while sitting somewhere else entirely.
  const active: NavKey | null = pathname.startsWith("/tailor")
    ? "tailor"
    : pathname.startsWith("/applications") || pathname.startsWith("/a/")
      ? "apps"
      : pathname.startsWith("/profile")
        ? "profile"
        : pathname === "/"
          ? "home"
          : null;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── sidebar (desktop) ───────────────────────────────────────────── */}
      <aside className="hidden w-[232px] flex-none flex-col border-r border-line bg-surface lg:flex">
        <div className="flex h-16 items-center border-b border-line px-[18px]">
          <Link
            href="/"
            aria-label="Recast home"
            className="text-[18px] font-[640] tracking-[-0.03em] text-ink"
          >
            recast
          </Link>
        </div>

        <nav className="flex flex-col gap-0.5 px-3 py-3.5">
          {NAV.map(({ key, href, label, icon: Icon }) => (
            <Link key={key} href={href} className={`nav-item ${active === key ? "on" : ""}`}>
              <Icon size={17} />
              {label}
              {key === "apps" && appCount != null && (
                <span className="num ml-auto text-[11.5px] font-semibold text-muted">{appCount}</span>
              )}
            </Link>
          ))}
        </nav>

        {/* Account card. Top row is identity — who Google signed in, and the way
            out. Bottom row is the state of the master profile, which is a
            different thing entirely and used to be conflated with it. */}
        <div className="mt-auto p-3">
          <div className="card bg-ground p-3">
            <div className="flex items-center gap-[9px]">
              <Avatar account={account} name={displayName} size={28} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-semibold">
                  {displayName ?? "Signed in"}
                </div>
                <div className="truncate text-[11px] text-muted">
                  {account?.email ?? "Local development"}
                </div>
              </div>
              {account && (
                <span className="tip">
                  <button
                    type="button"
                    onClick={signOut}
                    className="btn btn-quiet btn-xs w-[26px] flex-none p-0"
                    aria-label="Sign out"
                  >
                    <IconSignOut size={15} strokeWidth={1.7} />
                  </button>
                  <span className="tipbody w-[92px]">Sign out</span>
                </span>
              )}
            </div>
            {profile ? (
              <div className="mt-2.5 flex items-center gap-1.5 border-t border-line pt-2.5 text-[11px] text-good">
                <IconCheck size={13} />
                Master profile · {profileBullets(profile)} bullets
              </div>
            ) : (
              <Link
                href="/profile"
                className="mt-2.5 block border-t border-line pt-2.5 text-[11px] font-semibold"
              >
                Build your profile →
              </Link>
            )}
          </div>
        </div>
      </aside>

      {/* ── main ────────────────────────────────────────────────────────── */}
      <div className="relative flex min-w-0 flex-1 flex-col">
        {/* mobile top bar */}
        <header
          className={`h-14 flex-none items-center justify-between border-b border-line bg-surface px-[18px] lg:hidden ${bareMobileHeader ? "hidden" : "flex"}`}
        >
          <Link
            href="/"
            aria-label="Recast home"
            className="text-[17px] font-[640] tracking-[-0.03em] text-ink"
          >
            recast
          </Link>
          <div className="flex items-center gap-1.5">
            <Link href="/profile" aria-label="Profile">
              <Avatar account={account} name={displayName} size={32} />
            </Link>
            {account && (
              <button
                type="button"
                onClick={signOut}
                className="btn btn-quiet btn-xs w-[30px] p-0"
                aria-label="Sign out"
              >
                <IconSignOut size={16} strokeWidth={1.7} />
              </button>
            )}
          </div>
        </header>

        {children}

        {/* Privacy and Terms, on every screen of the app. Follows the header's
            lead on mobile: the editor is tight enough there that a second bar
            costs more than the links are worth, and the tab bar below still
            reaches Home. */}
        <AppFooter className={bareMobileHeader ? "hidden lg:flex" : "flex"} />

        {/* mobile bottom tabs */}
        <nav className="flex flex-none items-stretch border-t border-line bg-surface px-1.5 pt-1 pb-2.5 lg:hidden">
          <Link href="/" className={`tab ${active === "home" ? "on" : ""}`}>
            <IconHome size={20} strokeWidth={1.7} />
            Home
          </Link>
          <Link href="/applications" className={`tab ${active === "apps" ? "on" : ""}`}>
            <IconCalendar size={20} strokeWidth={1.7} />
            Applications
          </Link>
          <Link href="/tailor" className="tab flex-none basis-[76px]" aria-label="Tailor a resume">
            <span
              className="grid size-12 place-items-center rounded text-white"
              style={{
                background: "var(--accent)",
                boxShadow:
                  "0 1px 2px rgba(19,28,37,.14), 0 10px 22px -14px color-mix(in oklab, var(--accent) 85%, transparent)",
              }}
            >
              <IconSparkle size={22} />
            </span>
          </Link>
          <Link href="/profile" className={`tab ${active === "profile" ? "on" : ""}`}>
            <IconUser size={20} strokeWidth={1.7} />
            Profile
          </Link>
        </nav>
      </div>
    </div>
  );
}
