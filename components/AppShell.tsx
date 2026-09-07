"use client";

/**
 * The application chrome from App.dc.html / MobileApp.dc.html.
 *
 * Two shapes of the same navigation: a 232px sidebar on desktop, a bottom tab
 * bar with a raised "tailor" action on mobile. The design's Resume Library and
 * Settings entries are deliberately absent — there is no API behind either, and
 * a nav item that goes nowhere is worse than one that isn't there.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { initials, profileBullets, useProfile } from "./useProfile";
import {
  IconCalendar,
  IconHome,
  IconSparkle,
  IconTarget,
  IconUser,
  IconCheck,
} from "./icons";

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

  const active: NavKey = pathname.startsWith("/tailor")
    ? "tailor"
    : pathname.startsWith("/applications") || pathname.startsWith("/a/")
      ? "apps"
      : pathname.startsWith("/profile")
        ? "profile"
        : "home";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── sidebar (desktop) ───────────────────────────────────────────── */}
      <aside className="hidden w-[232px] flex-none flex-col border-r border-line bg-surface lg:flex">
        <div className="flex h-16 items-center border-b border-line px-[18px]">
          <Link href="/" className="text-[18px] font-[640] tracking-[-0.03em] text-ink">
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

        <div className="mt-auto p-3">
          <div className="card bg-ground p-3">
            <div className="flex items-center gap-[9px]">
              <span
                className="grid size-7 flex-none place-items-center rounded-full text-[11.5px] font-[650]"
                style={{ background: "var(--tint2)", color: "var(--accent)" }}
              >
                {profile ? initials(profile.contact.name) : "–"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-semibold">
                  {profile ? profile.contact.name : "No profile yet"}
                </div>
                <div className="text-[11px] text-muted">
                  {profile
                    ? `Master profile · ${profileBullets(profile)} bullets`
                    : "Upload a resume to start"}
                </div>
              </div>
            </div>
            {profile ? (
              <div className="mt-2.5 flex items-center gap-1.5 border-t border-line pt-2.5 text-[11px] text-good">
                <IconCheck size={13} />
                Up to date
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
          <Link href="/" className="text-[17px] font-[640] tracking-[-0.03em] text-ink">
            recast
          </Link>
          <Link
            href="/profile"
            className="grid size-8 place-items-center rounded-full text-[12px] font-[650]"
            style={{ background: "var(--tint2)", color: "var(--accent)" }}
          >
            {profile ? initials(profile.contact.name) : "–"}
          </Link>
        </header>

        {children}

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
