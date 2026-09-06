"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Application } from "@/lib/types";

export default function Home() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.applications().then(setApps).catch((e) => setError(String(e.message)));
  }, []);

  async function tailor() {
    if (!raw.trim()) return;
    setBusy(true);
    setError("");
    try {
      const { job } = await api.create(raw);
      window.location.href = `/a/${job.id}`;
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-10 p-6 sm:p-10">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">recast</h1>
        <div className="flex items-baseline gap-4 text-xs text-muted">
          {apps && <span>{apps.length} application{apps.length === 1 ? "" : "s"}</span>}
          <a href="/profile" className="hover:text-ink">profile</a>
        </div>
      </header>

      <section className="space-y-3">
        <label htmlFor="jd" className="block text-sm font-medium">
          Paste a job description
        </label>
        <textarea
          id="jd"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          rows={8}
          placeholder="Paste the whole posting — the boilerplate gets thrown away."
          className="w-full resize-y rounded border border-line bg-surface p-3 text-sm
                     outline-none focus:border-accent"
        />
        <div className="flex items-center gap-3">
          <button
            onClick={tailor}
            disabled={busy || !raw.trim()}
            className="rounded bg-accent px-4 py-2 text-sm font-medium text-white
                       disabled:opacity-40"
          >
            {busy ? "Tailoring…" : "Tailor my resume"}
          </button>
          {busy && <span className="text-xs text-muted">Parsing, scoring, rewording…</span>}
        </div>
        {error && <p className="text-sm text-bad">{error}</p>}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Applications</h2>
        {apps === null && <p className="text-sm text-muted">Loading…</p>}
        {apps?.length === 0 && (
          <p className="text-sm text-muted">Nothing yet. Paste a posting above.</p>
        )}
        <ul className="divide-y divide-line overflow-hidden rounded border border-line
                       bg-surface">
          {apps?.map((a) => (
            <li key={a.job_id}>
              <a
                href={`/a/${a.job_id}`}
                className="flex items-center gap-4 px-4 py-3 hover:bg-ground"
              >
                <span className="w-24 shrink-0 text-xs tabular-nums text-muted">{a.updated}</span>
                <span className="w-24 shrink-0 text-xs">{a.status}</span>
                <span className="min-w-0 flex-1 truncate text-sm">
                  <span className="font-medium">{a.role ?? "Untitled role"}</span>
                  {a.company && <span className="text-muted"> · {a.company}</span>}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted">
                  {a.keyword_coverage != null ? `${Math.round(a.keyword_coverage * 100)}%` : "—"}
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
