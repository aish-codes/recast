"use client";

/**
 * The editor.
 *
 * The left column is the resume as a set of decisions — every bullet shows its
 * relevance score, whether it was reworded, and any guard flag, with the original
 * one click away. The right column is a live HTML preview of the same object.
 *
 * Nothing here generates text. Editing mutates the TailoredResume and PUTs it
 * back; the PDF is a pure function of that object, rendered on demand.
 */

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { STATUSES, type Application, type Ats, type Bullet, type Job, type Resume } from "@/lib/types";

export default function Editor({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);

  const [resume, setResume] = useState<Resume | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [app, setApp] = useState<Application | null>(null);
  const [ats, setAts] = useState<Ats | null>(null);
  const [preview, setPreview] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.application(jobId)
      .then(({ app, job, resume }) => { setApp(app); setJob(job); setResume(resume); })
      .catch((e) => setError(e.message));
  }, [jobId]);

  // Debounced live preview. Cheap — it renders HTML, not a PDF.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!resume) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.preview(resume).then(setPreview).catch(() => {});
    }, 350);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [resume]);

  const update = useCallback((fn: (draft: Resume) => void) => {
    setResume((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
  }, []);

  async function save() {
    if (!resume) return;
    setSaving(true);
    setError("");
    try {
      const res = await api.saveResume(jobId, resume);
      setAts(res.ats);
      setDirty(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const flagged = useMemo(
    () => (resume ? allBullets(resume).filter((b) => b.flags.length).length : 0),
    [resume],
  );

  if (error && !resume) return <Shell><p className="text-bad">{error}</p></Shell>;
  if (!resume || !job) return <Shell><p className="text-muted">Loading…</p></Shell>;

  const musts = resume.gaps.filter((g) => g.kind === "must" && g.confidence === "high");
  const unsure = resume.gaps.filter((g) => g.kind === "must" && g.confidence === "low");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-2
                         border-b border-line bg-surface px-4 py-3">
        <a href="/" className="text-sm text-muted hover:text-ink">← all</a>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{job.role ?? "Untitled role"}</div>
          <div className="truncate text-xs text-muted">{job.company ?? "—"}</div>
        </div>

        <Stat label="coverage"
              value={ats ? `${Math.round(ats.keyword_coverage * 100)}%`
                         : app?.keyword_coverage != null
                         ? `${Math.round(app.keyword_coverage * 100)}%` : "—"} />
        <Stat label="pages" value={String(ats?.pages ?? app?.resume_pages ?? "—")} />
        <Stat label="flagged" value={String(flagged)} tone={flagged ? "bad" : undefined} />

        <select
          value={app?.status ?? "draft"}
          onChange={async (e) => setApp(await api.setStatus(jobId, e.target.value))}
          className="rounded border border-line bg-surface px-2 py-1 text-xs"
        >
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <a href={api.pdfUrl(jobId)} target="_blank" rel="noreferrer"
           className="rounded border border-line px-3 py-1.5 text-xs hover:bg-ground">PDF</a>
        <a href={api.docxUrl(jobId)}
           className="rounded border border-line px-3 py-1.5 text-xs hover:bg-ground">DOCX</a>
        <button onClick={save} disabled={!dirty || saving}
                className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white
                           disabled:opacity-40">
          {saving ? "Saving…" : dirty ? "Save" : "Saved"}
        </button>
      </header>

      {error && <p className="border-b border-line bg-surface px-4 py-2 text-sm text-bad">{error}</p>}

      <div className="grid flex-1 gap-6 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {/* ---------------- decisions ---------------- */}
        <div className="space-y-6">
          {resume.summary && (
            <Section title="Summary">
              <BulletRow bullet={resume.summary}
                         onChange={(t) => update((d) => { d.summary!.text = t; d.summary!.locked = true; })}
                         onRevert={() => update((d) => { d.summary!.text = d.summary!.original; })} />
            </Section>
          )}

          {resume.experience.map((exp, ei) => (
            <Section key={exp.source_id}
                     title={`${exp.title}, ${exp.company}`}
                     meta={`${exp.start} – ${exp.end ?? "Present"}`}>
              {exp.bullets.map((b, bi) => (
                <BulletRow
                  key={b.source_id}
                  bullet={b}
                  onChange={(t) => update((d) => {
                    d.experience[ei].bullets[bi].text = t;
                    d.experience[ei].bullets[bi].locked = true;
                  })}
                  onRevert={() => update((d) => {
                    const x = d.experience[ei].bullets[bi];
                    x.text = x.original;
                  })}
                  onRemove={() => update((d) => {
                    const [cut] = d.experience[ei].bullets.splice(bi, 1);
                    d.trimmed.push(cut);
                  })}
                />
              ))}
            </Section>
          ))}

          {resume.projects.map((p, pi) => (
            <Section key={p.source_id} title={p.name} meta={p.tech.join(", ")}>
              {p.bullets.map((b, bi) => (
                <BulletRow key={b.source_id} bullet={b}
                  onChange={(t) => update((d) => {
                    d.projects[pi].bullets[bi].text = t;
                    d.projects[pi].bullets[bi].locked = true;
                  })}
                  onRevert={() => update((d) => {
                    const x = d.projects[pi].bullets[bi];
                    x.text = x.original;
                  })}
                  onRemove={() => update((d) => {
                    const [cut] = d.projects[pi].bullets.splice(bi, 1);
                    d.trimmed.push(cut);
                  })} />
              ))}
            </Section>
          ))}

          {resume.trimmed.length > 0 && (
            <Section title={`Set aside (${resume.trimmed.length})`}>
              <p className="mb-2 text-xs text-muted">
                Nothing is deleted. Put any of these back on the page.
              </p>
              {resume.trimmed.map((b, i) => (
                <div key={b.source_id + i}
                     className="flex items-start gap-2 border-b border-line py-2 last:border-0">
                  <p className="flex-1 text-sm text-muted">{b.text}</p>
                  <button
                    onClick={() => update((d) => {
                      const [back] = d.trimmed.splice(i, 1);
                      d.experience[0]?.bullets.push(back);
                    })}
                    className="shrink-0 rounded border border-line px-2 py-0.5 text-xs
                               hover:bg-ground">
                    restore
                  </button>
                </div>
              ))}
            </Section>
          )}

          {(musts.length > 0 || unsure.length > 0) && (
            <Section title="Gaps">
              {musts.map((g) => (
                <p key={g.requirement} className="border-b border-line py-2 text-sm last:border-0">
                  <span className="mr-2 text-bad">absent</span>{g.requirement}
                </p>
              ))}
              {unsure.map((g) => (
                <p key={g.requirement} className="border-b border-line py-2 text-sm last:border-0">
                  <span className="mr-2 text-muted">unconfirmed</span>{g.requirement}
                </p>
              ))}
              <p className="pt-2 text-xs text-muted">
                Run <code className="rounded bg-ground px-1">recast fill {jobId}</code> to answer
                these — your answers become bullets and are saved to your profile.
              </p>
            </Section>
          )}

          {ats && ats.keyword_misses.length > 0 && (
            <Section title="Keywords not on the page">
              <p className="text-sm text-muted">{ats.keyword_misses.join(" · ")}</p>
            </Section>
          )}
        </div>

        {/* ---------------- preview ---------------- */}
        <div className="lg:sticky lg:top-20 lg:h-[calc(100vh-6rem)]">
          <iframe
            title="Resume preview"
            srcDoc={preview}
            className="h-[70vh] w-full rounded border border-line bg-white lg:h-full"
          />
        </div>
      </div>
    </div>
  );
}

/* ---------------- pieces ---------------- */

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="p-10">{children}</main>;
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "bad" }) {
  return (
    <div className="text-right">
      <div className={`text-sm tabular-nums ${tone === "bad" ? "text-bad" : ""}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
    </div>
  );
}

function Section({ title, meta, children }: {
  title: string; meta?: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded border border-line bg-surface p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        {meta && <span className="shrink-0 text-xs text-muted">{meta}</span>}
      </div>
      {children}
    </section>
  );
}

function BulletRow({ bullet, onChange, onRevert, onRemove }: {
  bullet: Bullet;
  onChange: (text: string) => void;
  onRevert: () => void;
  onRemove?: () => void;
}) {
  const [showOriginal, setShowOriginal] = useState(false);
  const changed = bullet.text.trim() !== bullet.original.trim();

  return (
    <div className="border-b border-line py-3 last:border-0">
      <div className="flex items-start gap-2">
        <span className="mt-1.5 w-8 shrink-0 text-right text-[10px] tabular-nums text-muted">
          {bullet.score.toFixed(2)}
        </span>
        <textarea
          value={bullet.text}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className="min-h-[3rem] flex-1 resize-none rounded bg-transparent px-1 text-sm
                     leading-relaxed outline-none focus:bg-ground"
        />
      </div>

      <div className="ml-10 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
        {bullet.flags.map((f) => (
          <span key={f} className="rounded bg-bad/10 px-1.5 py-0.5 text-bad">{f}</span>
        ))}
        {changed && (
          <button onClick={() => setShowOriginal((v) => !v)} className="text-muted hover:text-ink">
            {showOriginal ? "hide original" : "reworded — show original"}
          </button>
        )}
        {changed && (
          <button onClick={onRevert} className="text-muted hover:text-ink">revert</button>
        )}
        {onRemove && (
          <button onClick={onRemove} className="text-muted hover:text-bad">set aside</button>
        )}
        {bullet.rationale && !changed && (
          <span className="text-muted">{bullet.rationale}</span>
        )}
      </div>

      {showOriginal && (
        <p className="ml-10 mt-1 border-l-2 border-line pl-2 text-xs text-muted">
          {bullet.original}
        </p>
      )}
    </div>
  );
}

function allBullets(r: Resume): Bullet[] {
  return [
    ...(r.summary ? [r.summary] : []),
    ...r.experience.flatMap((e) => e.bullets),
    ...r.projects.flatMap((p) => p.bullets),
  ];
}
