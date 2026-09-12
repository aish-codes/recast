/**
 * The footer, in the two shapes the app needs.
 *
 * `SiteFooter` is the wide one on the full-page views — the landing page and the
 * policy pages. `AppFooter` is a single slim line pinned to the bottom of the
 * app shell, where vertical space is the scarce thing and the sidebar is already
 * carrying the navigation.
 *
 * Both exist so Privacy and Terms are reachable from every screen, signed in or
 * out, which is the whole point of putting them in a footer rather than on the
 * marketing page alone. Both are server components: nothing here is interactive.
 */

import Link from "next/link";

/** Rendered on the server and on the client; the same year either way. */
const year = () => new Date().getFullYear();

export function SiteFooter({ children }: { children?: React.ReactNode }) {
  return (
    <footer className="border-t border-line bg-surface py-8">
      <div className="wrap flex flex-wrap items-center justify-between gap-6">
        <Link
          href="/"
          className="text-[15px] font-[640] tracking-[-0.03em] text-ink"
          aria-label="Recast home"
        >
          recast
        </Link>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {children}
          <Link className="navlink" href="/privacy">
            Privacy Policy
          </Link>
          <Link className="navlink" href="/terms">
            Terms of Service
          </Link>
        </div>
        <span className="text-[12.5px] text-muted">© {year()} Recast</span>
      </div>
    </footer>
  );
}

export function AppFooter({ className = "flex" }: { className?: string }) {
  return (
    <footer
      className={`${className} flex-none flex-wrap items-center justify-between gap-x-5 gap-y-1 border-t border-line bg-surface px-[18px] py-2 text-[11.5px] text-muted lg:px-9`}
    >
      <span>© {year()} Recast</span>
      <span className="flex items-center gap-5">
        <Link href="/privacy" className="transition-colors hover:text-ink">
          Privacy
        </Link>
        <Link href="/terms" className="transition-colors hover:text-ink">
          Terms
        </Link>
      </span>
    </footer>
  );
}
