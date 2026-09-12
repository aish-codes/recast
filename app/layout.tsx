import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

export const metadata: Metadata = {
  title: "recast",
  description: "Tailor a resume to a job description without inventing anything.",
};

// Vercel Web Analytics: page views and Web Vitals, per route. Cookieless —
// visitors are told apart by a hash that Vercel derives per day and discards,
// so nothing here identifies a person and nothing needs a consent banner. The
// component is a no-op outside Vercel (nothing to send to), so local dev and
// the test build are unaffected. It is listed as a processor in the privacy
// policy; keep the two in step.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
