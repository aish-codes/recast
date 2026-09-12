/**
 * Chrome for the policy pages.
 *
 * A route group, so the URLs stay /privacy and /terms while both pages share
 * this header and footer. Server-rendered and static — there is nothing on
 * these pages that depends on who is reading them, which is also why the
 * middleware lets them through signed out.
 *
 * The wordmark is the way back: someone who arrives here from the footer of the
 * app needs a door home, and these pages are outside the app shell that
 * normally provides one.
 */

import Link from "next/link";
import { SiteFooter } from "@/components/SiteFooter";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-line bg-surface">
        <div className="wrap flex h-[72px] items-center justify-between gap-8">
          <Link
            href="/"
            className="text-xl font-[640] tracking-[-0.03em] text-ink"
            aria-label="Recast home"
          >
            recast
          </Link>
          <Link href="/" className="btn btn-ghost">
            Back to Recast
          </Link>
        </div>
      </header>

      <main className="flex-1 py-12 lg:py-16">
        <div className="wrap max-w-[760px]">{children}</div>
      </main>

      <SiteFooter />
    </div>
  );
}
