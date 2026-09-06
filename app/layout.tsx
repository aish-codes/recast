import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "recast",
  description: "Tailor a resume to a job description without inventing anything.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
