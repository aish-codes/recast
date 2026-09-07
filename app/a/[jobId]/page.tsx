"use client";

/**
 * The editor — screen 4 of App.dc.html.
 *
 * Three panes: your original resume on the left (read only, straight from the
 * master profile), the recast one in the middle where every line is editable,
 * and the match rail on the right. The middle pane marks what changed — a left
 * bar on touched lines, highlights on keywords the posting asked for — so a
 * rewrite is never something you have to take on trust.
 *
 * On a phone the three panes become one, switched by a segmented control.
 */

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  IconArrowLeft,
  IconBrackets,
  IconCheck,
  IconChevronDown,
  IconDownload,
  IconInfo,
  IconWarning,
  Spinner,
} from "@/components/icons";
import { useProfile } from "@/components/useProfile";
import { api } from "@/lib/api";
import {
  STATUSES,
  STATUS_LABEL,
  type Analysis,
  type Application,
  type Ats,
  type Bullet,
  type CoverLetter,
  type Job,
  type Profile,
  type Resume,
} from "@/lib/types";

/* ── helpers ─────────────────────────────────────────────────────────────── */

/**
 * Guard flags arrive as "name" or "name: detail" ("length_drift: 35% shorter"),
 * so everything here matches on the name and keeps the detail for the chip.
 */
const HARD_FLAGS = ["invented_metric", "invented_entity"];

const FLAG_LABEL: Record<string, string> = {
  invented_metric: "number not in your original",
  invented_entity: "term you never claimed",
  length_drift: "length drifted",
  keyword_stuffing: "keyword repeated",
};

function flagName(flag: string) {
  return flag.split(":")[0].trim();
}

function flagText(flag: string) {
  const [name, ...rest] = flag.split(":");
  const label = FLAG_LABEL[name.trim()] ?? name.trim();
  const detail = rest.join(":").trim();
  return detail ? `${label} — ${detail}` : label;
}

function isHard(flag: string) {
  return HARD_FLAGS.includes(flagName(flag));
}

/** Split a bullet on the keywords it hit, so they can carry the .mk mark. */
function marked(text: string, keywords: string[]) {
  const terms = keywords.filter((k) => k.trim().length > 1);
  if (!terms.length) return [{ t: text, hit: false }];

  const escaped = terms
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .sort((a, b) => b.length - a.length)
    .join("|");
  const re = new RegExp(`(${escaped})`, "gi");

  return text
    .split(re)
    .filter((part) => part !== "")
    .map((part) => ({ t: part, hit: re.test(part) && terms.some((k) => k.toLowerCase() === part.toLowerCase()) }));
}

function allBullets(r: Resume): Bullet[] {
  return [
    ...(r.summary ? [r.summary] : []),
    ...r.experience.flatMap((e) => e.bullets),
    ...r.projects.flatMap((p) => p.bullets),
  ];
}

/* ── one editable line ───────────────────────────────────────────────────── */

function BulletRow({
  bullet,
  onChange,
  onRevert,
  onSetAside,
  bare = false,
}: {
  bullet: Bullet;
  onChange: (text: string) => void;
  onRevert: () => void;
  onSetAside?: () => void;
  /** The summary is a paragraph, not a list item — no leading dot. */
  bare?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const changed = bullet.text.trim() !== bullet.original.trim();
  const hard = bullet.flags.filter(isHard);
  const soft = bullet.flags.filter((f) => !isHard(f));

  return (
    <div className={`brow ${hard.length ? "flagged" : changed ? "changed" : ""}`}>
      <div className="flex gap-[9px]">
        {!bare && <span className="flex-none text-[13px] leading-[1.62] text-[#b6c1cc]">•</span>}
        <div className="min-w-0 flex-1">
          {editing ? (
            <textarea
              className="ta"
              rows={3}
              autoFocus
              value={bullet.text}
              onChange={(e) => onChange(e.target.value)}
              onBlur={() => setEditing(false)}
            />
          ) : (
            <div className="btext" onClick={() => setEditing(true)}>
              {marked(bullet.text, bullet.keywords_hit).map((p, i) => (
                <span key={i} className={p.hit ? "mk" : undefined}>
                  {p.t}
                </span>
              ))}
            </div>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {bullet.keywords_hit.length > 0 && (
              <span className="chip c-kw">
                {bullet.keywords_hit.length} keyword{bullet.keywords_hit.length === 1 ? "" : "s"}
              </span>
            )}
            {changed && <span className="chip c-edit">rephrased</span>}
            {hard.map((f) => (
              <span key={f} className="chip c-bad">
                {flagText(f)}
              </span>
            ))}
            {soft.map((f) => (
              <span key={f} className="chip c-emph">
                {flagText(f)}
              </span>
            ))}
            {changed && (
              <button
                className="btn btn-quiet btn-xs h-[19px] px-[5px] text-[10.5px] font-semibold"
                onClick={() => setShowOriginal((v) => !v)}
              >
                {showOriginal ? "hide original" : "show original"}
              </button>
            )}
            {changed && (
              <button
                className="btn btn-quiet btn-xs h-[19px] px-[5px] text-[10.5px] font-semibold"
                onClick={onRevert}
              >
                revert
              </button>
            )}
            {onSetAside && (
              <button
                className="btn btn-quiet btn-xs h-[19px] px-[5px] text-[10.5px] font-semibold"
                onClick={onSetAside}
              >
                set aside
              </button>
            )}
          </div>

          {showOriginal && (
            <p className="fade mt-[7px] border-l-2 border-line pl-2.5 text-xs leading-[1.6] text-muted">
              {bullet.original}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── the original, read only ─────────────────────────────────────────────── */

function OriginalPane({ profile }: { profile: Profile | null }) {
  if (!profile) {
    return <p className="p-6 text-[13px] text-muted">No master profile to compare against.</p>;
  }
  const c = profile.contact;
  return (
    <div className="max-w-[520px] text-[#41505e]">
      <div className="text-base font-[640] tracking-[-0.02em] text-ink">{c.name}</div>
      <div className="mt-1 text-[11.5px] text-muted">
        {[c.location, c.email, c.phone].filter(Boolean).join(" · ")}
      </div>

      {profile.summaries.length > 0 && (
        <>
          <div className="eyebrow mt-6 border-b border-line pb-1.5">Summary</div>
          {profile.summaries.map((s) => (
            <p key={s.id} className="mt-2.5 text-[13px] leading-[1.62]">
              {s.text}
            </p>
          ))}
        </>
      )}

      {profile.experience.length > 0 && (
        <div className="eyebrow mt-6 border-b border-line pb-1.5">Experience</div>
      )}
      {profile.experience.map((e) => (
        <div key={e.id}>
          <div className="mt-3 flex items-baseline justify-between gap-2.5">
            <span className="text-[13px] font-[640] text-ink">
              {e.title}, {e.company}
            </span>
            <span className="flex-none text-[11px] text-muted">
              {e.start} – {e.end ?? "Present"}
            </span>
          </div>
          <ul className="mt-2 flex list-disc flex-col gap-[7px] pl-4">
            {e.bullets.map((b) => (
              <li key={b.id} className="text-[13px] leading-[1.62]">
                {b.text}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {profile.projects.length > 0 && (
        <div className="eyebrow mt-6 border-b border-line pb-1.5">Projects</div>
      )}
      {profile.projects.map((p) => (
        <div key={p.id}>
          <div className="mt-3 text-[13px] font-[640] text-ink">{p.name}</div>
          {p.tech.length > 0 && <div className="mt-0.5 text-[11px] text-muted">{p.tech.join(", ")}</div>}
          <ul className="mt-2 flex list-disc flex-col gap-[7px] pl-4">
            {p.bullets.map((b) => (
              <li key={b.id} className="text-[13px] leading-[1.62]">
                {b.text}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {profile.skills.length > 0 && (
        <>
          <div className="eyebrow mt-6 border-b border-line pb-1.5">Skills</div>
          <p className="mt-2.5 text-[13px] leading-[1.7]">
            {profile.skills.flatMap((g) => g.skills).join(", ")}
          </p>
        </>
      )}
    </div>
  );
}

/* ── the match rail ──────────────────────────────────────────────────────── */

function Ring({ pct }: { pct: number }) {
  const r = 34;
  const circumference = 2 * Math.PI * r;
  const filled = Math.max(0, Math.min(1, pct / 100)) * circumference;
  return (
    <span className="relative size-[78px] flex-none">
      <svg width="78" height="78" viewBox="0 0 80 80" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="40" cy="40" r={r} fill="none" stroke="#e3e8ed" strokeWidth="7" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
      </svg>
      <span className="num absolute inset-0 grid place-items-center text-[21px] font-[650] tracking-[-0.03em]">
        {Math.round(pct)}%
      </span>
    </span>
  );
}

function BreakdownRow({
  label,
  count,
  items,
  tone,
  note,
}: {
  label: string;
  count: number;
  items: string[];
  tone: "a" | "w";
  note?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full cursor-pointer items-center gap-2.5 rounded border-none bg-transparent px-2.5 py-[11px] text-left"
      >
        <span className={`kd-${tone} size-[7px] flex-none rounded-full`} />
        <span className="min-w-0 flex-1 text-[13px] font-semibold">{label}</span>
        <span className="num text-[13px] font-[650] text-muted">{count}</span>
        <span className={`caret ${open ? "on" : ""}`}>
          <IconChevronDown size={13} className="text-[#9aa7b4]" />
        </span>
      </button>
      {open && (
        <div className="fade px-2.5 pt-0.5 pb-3.5 pl-[27px]">
          {items.length ? (
            <div className="flex flex-wrap gap-[5px]">
              {items.map((i) => (
                <span key={i} className={tone === "w" ? "itm itm-w" : "itm"}>
                  {i}
                </span>
              ))}
            </div>
          ) : (
            <p className="m-0 text-[11px] text-muted">Nothing here.</p>
          )}
          {note && <p className="mt-2.5 text-[11px] leading-[1.55] text-muted">{note}</p>}
        </div>
      )}
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────────────────── */

export default function Editor({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const { profile } = useProfile();

  const [resume, setResume] = useState<Resume | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [app, setApp] = useState<Application | null>(null);
  const [ats, setAts] = useState<Ats | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [letter, setLetter] = useState<CoverLetter | null>(null);

  const [tab, setTab] = useState<"resume" | "cover">("resume");
  const [pane, setPane] = useState<"original" | "recast" | "match">("recast");
  const [fmt, setFmt] = useState<"pdf" | "docx">("pdf");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyLetter, setBusyLetter] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tab") === "cover") setTab("cover");
  }, []);

  useEffect(() => {
    api
      .application(jobId)
      .then(({ app, job, resume }) => {
        setApp(app);
        setJob(job);
        setResume(resume);
      })
      .catch((e) => setError((e as Error).message));
    // Both are read-only reports; a failure on either leaves the editor usable.
    api.atsReport(jobId).then(setAts).catch(() => {});
    api.analysis(jobId).then(setAnalysis).catch(() => {});
  }, [jobId]);

  // The cover letter is generated on demand — only fetch when the tab is opened.
  useEffect(() => {
    if (tab !== "cover" || letter || busyLetter) return;
    setBusyLetter(true);
    api
      .getCoverLetter(jobId)
      .then(setLetter)
      .catch(() => {})
      .finally(() => setBusyLetter(false));
  }, [tab, jobId, letter, busyLetter]);

  // Losing an unsaved rewrite to a stray back-navigation is the one mistake this
  // screen can make on the user's behalf.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const update = useCallback((fn: (draft: Resume) => void) => {
    setResume((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
  }, []);

  const save = useCallback(async () => {
    if (!resume) return null;
    setSaving(true);
    setError("");
    try {
      const res = await api.saveResume(jobId, resume);
      setAts(res.ats);
      setDirty(false);
      return res;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }, [jobId, resume]);

  async function download() {
    if (dirty && !(await save())) return;
    window.open(fmt === "pdf" ? api.pdfUrl(jobId) : api.docxUrl(jobId), "_blank");
  }

  async function generateLetter() {
    setBusyLetter(true);
    setError("");
    try {
      setLetter(await api.coverLetter(jobId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyLetter(false);
    }
  }

  /** Put a set-aside bullet back where it came from, not wherever is first. */
  const restore = useCallback(
    (index: number) =>
      update((d) => {
        const [back] = d.trimmed.splice(index, 1);
        const fromExp = profile?.experience.find((e) => e.bullets.some((b) => b.id === back.source_id));
        const fromProj = profile?.projects.find((p) => p.bullets.some((b) => b.id === back.source_id));
        const exp = fromExp && d.experience.find((e) => e.source_id === fromExp.id);
        const proj = fromProj && d.projects.find((p) => p.source_id === fromProj.id);
        (exp?.bullets ?? proj?.bullets ?? d.experience[0]?.bullets)?.push(back);
      }),
    [update, profile],
  );

  // A discarded rewrite (hard flag) and a length wobble are not the same news,
  // so they are counted and coloured separately.
  const hardFlagged = useMemo(
    () => (resume ? allBullets(resume).filter((b) => b.flags.some(isHard)).length : 0),
    [resume],
  );
  const softFlagged = useMemo(
    () =>
      resume
        ? allBullets(resume).filter((b) => b.flags.length && !b.flags.some(isHard)).length
        : 0,
    [resume],
  );
  const changed = useMemo(
    () =>
      resume
        ? allBullets(resume).filter((b) => b.text.trim() !== b.original.trim()).length
        : 0,
    [resume],
  );

  if (error && !resume) {
    return (
      <AppShell>
        <div className="grid flex-1 place-items-center p-10">
          <div className="max-w-[340px] text-center">
            <p className="m-0 text-sm font-semibold">We couldn&rsquo;t open this application</p>
            <p className="mt-1.5 text-[12.5px] leading-[1.6] text-muted">{error}</p>
            <Link href="/applications" className="btn btn-ghost mt-4">
              Back to applications
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!resume || !job) {
    return (
      <AppShell>
        <div className="grid flex-1 place-items-center p-10">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  const coverage = ats?.keyword_coverage ?? app?.keyword_coverage ?? null;
  const match = analysis ? analysis.overall * 100 : coverage != null ? coverage * 100 : 0;
  const musts = resume.gaps.filter((g) => g.kind === "must");

  return (
    <AppShell bareMobileHeader>
      <div className="flex min-h-0 flex-1 flex-col">
        {/* ── topbar ──────────────────────────────────────────────────── */}
        <div className="flex flex-none flex-wrap items-center gap-x-3.5 gap-y-2 border-b border-line bg-surface px-3 py-2.5 lg:h-16 lg:flex-nowrap lg:py-0 lg:pr-5">
          <Link href="/applications" className="btn btn-quiet btn-xs">
            <IconArrowLeft size={15} />
          </Link>
          <div className="min-w-0 flex-1 lg:flex-none">
            <div className="truncate text-[14.5px] font-[640] tracking-[-0.012em]">
              {job.role ?? "Untitled role"}
            </div>
            <div className="truncate text-xs text-muted">{job.company ?? "—"}</div>
          </div>

          <div className="seg order-3 lg:order-none lg:ml-[18px]">
            <button className={tab === "resume" ? "on" : ""} onClick={() => setTab("resume")}>
              Resume
            </button>
            <button className={tab === "cover" ? "on" : ""} onClick={() => setTab("cover")}>
              Cover Letter
            </button>
          </div>

          <div className="ml-auto flex items-center gap-2.5">
            <span className="hidden items-center gap-1.5 text-[11.5px] text-muted lg:inline-flex">
              {dirty ? (
                <>Unsaved changes</>
              ) : (
                <>
                  <IconCheck size={13} style={{ color: "var(--good)" }} />
                  All changes saved
                </>
              )}
            </span>
            {dirty && (
              <button className="btn btn-ghost" onClick={save} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            )}
            <div className="seg hidden lg:inline-flex">
              <button className={fmt === "pdf" ? "on" : ""} onClick={() => setFmt("pdf")}>
                PDF
              </button>
              <button className={fmt === "docx" ? "on" : ""} onClick={() => setFmt("docx")}>
                DOCX
              </button>
            </div>
            <button className="btn btn-primary" onClick={download} disabled={saving}>
              <IconDownload size={15} strokeWidth={1.8} />
              Download
            </button>
          </div>
        </div>

        {error && (
          <p
            className="border-b border-line px-4 py-2 text-[13px]"
            style={{ background: "var(--badt)", color: "var(--bad)" }}
          >
            {error}
          </p>
        )}

        {/* ── mobile pane switch ──────────────────────────────────────── */}
        {tab === "resume" && (
          <div className="flex flex-none items-center justify-center border-b border-line bg-surface py-2 lg:hidden">
            <div className="seg">
              <button className={pane === "original" ? "on" : ""} onClick={() => setPane("original")}>
                Original
              </button>
              <button className={pane === "recast" ? "on" : ""} onClick={() => setPane("recast")}>
                Recast
              </button>
              <button className={pane === "match" ? "on" : ""} onClick={() => setPane("match")}>
                Match
              </button>
            </div>
          </div>
        )}

        {/* ── body ────────────────────────────────────────────────────── */}
        <div className="flex min-h-0 flex-1">
          {tab === "resume" ? (
            <>
              {/* original */}
              <div
                className={`min-w-0 flex-1 flex-col border-r border-line ${pane === "original" ? "flex" : "hidden"} lg:flex`}
              >
                <div className="flex h-11 flex-none items-center justify-between gap-2.5 border-b border-line bg-ground px-[22px]">
                  <span className="text-[12.5px] font-[640]">Your Original Resume</span>
                  <span className="chip c-edit">read only</span>
                </div>
                <div className="scroll flex-1 bg-ground px-[22px] pt-6 pb-10">
                  <OriginalPane profile={profile} />
                </div>
              </div>

              {/* recast */}
              <div
                className={`min-w-0 flex-[1.12] flex-col ${pane === "recast" ? "flex" : "hidden"} lg:flex`}
              >
                <div className="flex h-11 flex-none items-center justify-between gap-2.5 border-b border-line bg-surface px-[22px]">
                  <span className="text-[12.5px] font-[640]">Your Recast Resume</span>
                  <div className="flex items-center gap-[7px]">
                    <span className="chip c-kw">{changed} changed</span>
                    {hardFlagged > 0 && <span className="chip c-bad">{hardFlagged} flagged</span>}
                    {softFlagged > 0 && <span className="chip c-emph">{softFlagged} to check</span>}
                    <span className="tip">
                      <span className="chip c-edit cursor-help">
                        <IconInfo size={11} />
                        how to read this
                      </span>
                      <span className="tipbody">
                        Highlighted words are keywords from the posting. A left bar marks a line we
                        touched — click any line to edit it, or open the original to compare.
                      </span>
                    </span>
                  </div>
                </div>

                <div className="scroll flex-1 bg-surface px-[22px] pt-6 pb-10">
                  <div className="max-w-[560px]">
                    <div className="mb-1.5 flex flex-wrap gap-[7px] border-b border-line pb-[18px]">
                      <span className="chip c-kw">keyword from the posting</span>
                      <span className="chip c-edit">rephrased</span>
                      <span className="chip c-bad">flagged</span>
                    </div>

                    <div className="text-base font-[640] tracking-[-0.02em]">
                      {resume.contact.name}
                    </div>
                    <div className="mt-1 text-[11.5px] text-muted">
                      {[resume.contact.location, resume.contact.email, resume.contact.phone]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>

                    {resume.summary && (
                      <>
                        <div className="eyebrow mt-6 border-b border-line pb-1.5">Summary</div>
                        <div className="mt-2">
                          <BulletRow
                            bare
                            bullet={resume.summary}
                            onChange={(t) =>
                              update((d) => {
                                d.summary!.text = t;
                                d.summary!.locked = true;
                              })
                            }
                            onRevert={() => update((d) => (d.summary!.text = d.summary!.original))}
                          />
                        </div>
                      </>
                    )}

                    {resume.experience.length > 0 && (
                      <div className="eyebrow mt-6 mb-3.5 border-b border-line pb-1.5">Experience</div>
                    )}
                    {resume.experience.map((exp, ei) => (
                      <div key={exp.source_id} className="mt-3.5">
                        <div className="flex items-baseline justify-between gap-2.5">
                          <span className="text-[13px] font-[640]">
                            {exp.title}, {exp.company}
                          </span>
                          <span className="flex-none text-[11px] text-muted">
                            {exp.start} – {exp.end ?? "Present"}
                          </span>
                        </div>
                        <div className="mt-1.5 flex flex-col gap-0.5">
                          {exp.bullets.map((b, bi) => (
                            <BulletRow
                              key={b.source_id}
                              bullet={b}
                              onChange={(t) =>
                                update((d) => {
                                  d.experience[ei].bullets[bi].text = t;
                                  d.experience[ei].bullets[bi].locked = true;
                                })
                              }
                              onRevert={() =>
                                update((d) => {
                                  const x = d.experience[ei].bullets[bi];
                                  x.text = x.original;
                                })
                              }
                              onSetAside={() =>
                                update((d) => {
                                  const [cut] = d.experience[ei].bullets.splice(bi, 1);
                                  d.trimmed.push(cut);
                                })
                              }
                            />
                          ))}
                        </div>
                      </div>
                    ))}

                    {resume.projects.length > 0 && (
                      <div className="eyebrow mt-6 mb-3.5 border-b border-line pb-1.5">Projects</div>
                    )}
                    {resume.projects.map((p, pi) => (
                      <div key={p.source_id} className="mt-3.5">
                        <div className="flex items-baseline justify-between gap-2.5">
                          <span className="text-[13px] font-[640]">{p.name}</span>
                          <span className="flex-none text-[11px] text-muted">{p.tech.join(", ")}</span>
                        </div>
                        <div className="mt-1.5 flex flex-col gap-0.5">
                          {p.bullets.map((b, bi) => (
                            <BulletRow
                              key={b.source_id}
                              bullet={b}
                              onChange={(t) =>
                                update((d) => {
                                  d.projects[pi].bullets[bi].text = t;
                                  d.projects[pi].bullets[bi].locked = true;
                                })
                              }
                              onRevert={() =>
                                update((d) => {
                                  const x = d.projects[pi].bullets[bi];
                                  x.text = x.original;
                                })
                              }
                              onSetAside={() =>
                                update((d) => {
                                  const [cut] = d.projects[pi].bullets.splice(bi, 1);
                                  d.trimmed.push(cut);
                                })
                              }
                            />
                          ))}
                        </div>
                      </div>
                    ))}

                    {resume.skills.length > 0 && (
                      <>
                        <div className="eyebrow mt-6 border-b border-line pb-1.5">Skills</div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {resume.skills.flatMap((g) =>
                            g.skills.map((s) => (
                              <span
                                key={`${g.name}-${s}`}
                                className={`sk ${job.keywords.some((k) => k.toLowerCase() === s.toLowerCase()) ? "sk-on" : ""}`}
                              >
                                {s}
                              </span>
                            )),
                          )}
                        </div>
                      </>
                    )}

                    {resume.trimmed.length > 0 && (
                      <div className="card mt-6 bg-ground px-4 py-3.5">
                        <div className="flex items-center justify-between gap-2.5">
                          <span className="text-[12.5px] font-[640]">
                            Set aside ({resume.trimmed.length})
                          </span>
                          <span className="text-[11px] text-muted">Nothing is deleted</span>
                        </div>
                        <div className="mt-2.5 flex flex-col gap-[9px]">
                          {resume.trimmed.map((b, i) => (
                            <div
                              key={`${b.source_id}-${i}`}
                              className="flex items-start gap-2.5 border-t border-line pt-[9px]"
                            >
                              <p className="m-0 flex-1 text-[12.5px] leading-[1.55] text-muted">
                                {b.text}
                              </p>
                              <button className="btn btn-ghost btn-xs" onClick={() => restore(i)}>
                                Put back
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            /* ── cover letter ──────────────────────────────────────────── */
            <div className="fade flex min-w-0 flex-1 flex-col bg-ground">
              <div className="flex h-11 flex-none items-center justify-between gap-2.5 border-b border-line bg-surface px-[26px]">
                <span className="truncate text-[12.5px] font-[640]">
                  Cover letter · {job.role ?? "this role"}
                  {job.company ? `, ${job.company}` : ""}
                </span>
                {letter && (
                  <button className="btn btn-ghost btn-xs" onClick={generateLetter} disabled={busyLetter}>
                    {busyLetter ? "Writing…" : "Rewrite"}
                  </button>
                )}
              </div>
              <div className="scroll flex-1 px-5 py-8 lg:px-[26px]">
                <div className="card mx-auto max-w-[640px] p-7 lg:p-10">
                  {busyLetter && !letter ? (
                    <div className="grid place-items-center py-10">
                      <Spinner />
                    </div>
                  ) : letter ? (
                    <>
                      <p className="m-0 text-[13.5px] leading-[1.75]">{letter.greeting}</p>
                      {letter.paragraphs.map((p, i) => (
                        <p key={i} className="mt-4 text-[13.5px] leading-[1.75]">
                          {p}
                        </p>
                      ))}
                      <p className="mt-6 text-[13.5px] leading-[1.75]">{letter.signoff}</p>
                      <p className="mt-1 text-[13.5px] leading-[1.75] font-semibold">{letter.name}</p>
                    </>
                  ) : (
                    <div className="py-8 text-center">
                      <p className="m-0 text-[15px] font-[640]">No cover letter yet</p>
                      <p className="mx-auto mt-[7px] max-w-[380px] text-[12.5px] leading-[1.6] text-muted">
                        It gets written off the tailored resume, so it never claims anything the
                        resume doesn&rsquo;t.
                      </p>
                      <button className="btn btn-primary mt-4" onClick={generateLetter} disabled={busyLetter}>
                        {busyLetter ? "Writing…" : "Write a cover letter"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── match rail ────────────────────────────────────────────── */}
          <div
            className={`scroll w-full flex-none border-l border-line bg-surface px-[18px] pt-5 pb-8 lg:w-[300px] ${pane === "match" && tab === "resume" ? "block" : "hidden"} lg:block`}
          >
            <div className="card bg-ground p-[18px]">
              <div className="flex items-center gap-4">
                <Ring pct={match} />
                <div className="min-w-0">
                  <div className="text-sm font-[640]">Resume Match</div>
                  <div className="mt-1 text-[11.5px] leading-[1.5] text-muted">
                    How much of this posting your resume now speaks to.
                  </div>
                </div>
              </div>
              <p className="mt-3.5 border-t border-line pt-3 text-[11px] leading-[1.55] text-muted">
                An optimisation indicator, not a promise. No score can guarantee any particular ATS
                passes your resume through.
              </p>
            </div>

            <div className="mt-[18px] flex flex-col gap-0.5">
              <BreakdownRow
                label="Keywords on the page"
                count={ats?.keyword_hits.length ?? analysis?.keywords_hit.length ?? 0}
                items={ats?.keyword_hits ?? analysis?.keywords_hit ?? []}
                tone="a"
              />
              <BreakdownRow
                label="Keywords missing"
                count={ats?.keyword_misses.length ?? analysis?.keywords_missed.length ?? 0}
                items={ats?.keyword_misses ?? analysis?.keywords_missed ?? []}
                tone="w"
                note="Missing is not always wrong — a keyword you cannot evidence should stay off."
              />
              {analysis && (
                <BreakdownRow
                  label="Requirements matched"
                  count={analysis.matches.filter((m) => m.verdict !== "absent").length}
                  items={analysis.matches
                    .filter((m) => m.verdict !== "absent")
                    .map((m) => m.requirement)}
                  tone="a"
                />
              )}
              <BreakdownRow
                label="Gaps"
                count={musts.length}
                items={musts.map((g) => g.requirement)}
                tone="w"
                note={
                  musts.length
                    ? "The job asks for these and your profile can't evidence them yet. `recast fill` walks through them and turns your answers into bullets."
                    : undefined
                }
              />
            </div>

            <div className="card mt-[18px] p-3.5">
              <div className="flex items-center gap-2">
                <IconBrackets size={15} style={{ color: "var(--good)" }} />
                <span className="text-[12.5px] font-[640]">What a parser sees</span>
              </div>
              {ats ? (
                <p className="mt-2 text-[11.5px] leading-[1.6] text-muted">
                  We render the PDF, read it back, and check.{" "}
                  <span
                    style={{
                      color: ats.missing_bullets.length ? "var(--warn)" : "var(--good)",
                      fontWeight: 600,
                    }}
                  >
                    {ats.missing_bullets.length === 0
                      ? "Every bullet extracts cleanly"
                      : `${ats.missing_bullets.length} bullets don't extract`}
                  </span>
                  . {ats.pages} page{ats.pages === 1 ? "" : "s"}.
                </p>
              ) : (
                <p className="mt-2 text-[11.5px] leading-[1.6] text-muted">Checking the render…</p>
              )}
              {ats?.warnings.map((w) => (
                <p key={w} className="mt-2 flex items-start gap-1.5 text-[11px] leading-[1.5] text-muted">
                  <IconWarning size={13} style={{ color: "var(--warn)", flex: "0 0 auto" }} />
                  {w}
                </p>
              ))}
            </div>

            <div className="card mt-[18px] p-3.5">
              <label className="lbl" htmlFor="status">
                Application status
              </label>
              <select
                id="status"
                className="inp"
                value={app?.status ?? "draft"}
                onChange={async (e) => {
                  try {
                    setApp(await api.setStatus(jobId, e.target.value));
                  } catch (err) {
                    setError((err as Error).message);
                  }
                }}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-[11px] leading-[1.5] text-muted">
                Moves this role along your pipeline on the dashboard.
              </p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
