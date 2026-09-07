"use client";

/**
 * Your master profile — upload, then review before anything is saved.
 *
 * The review step is not politeness. PDF extraction is lossy in ways that
 * depend on how the file was produced, and this profile becomes the ground
 * truth every later stage is checked against, so a bullet that is wrong here
 * can never be caught downstream. Nothing persists until you confirm, and
 * anything the parser could not trace back to your document is marked.
 *
 * Styling follows the Tailor screen's upload card and the error card from
 * States.dc.html — a failed parse says what went wrong and what to do instead.
 */

import Link from "next/link";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import {
  IconAlert,
  IconCheck,
  IconFile,
  IconSparkle,
  IconUpload,
  IconWarning,
} from "@/components/icons";
import { loadProfile, profileBullets, useProfile } from "@/components/useProfile";
import { api } from "@/lib/api";
import type { ParseResult, Profile, ProfileBullet } from "@/lib/types";

export default function ProfilePage() {
  const { profile: existing, reload } = useProfile();
  const [parsed, setParsed] = useState<ParseResult | null>(null);
  const [draft, setDraft] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [rejected, setRejected] = useState("");

  async function onFile(file: File) {
    setBusy(true);
    setError("");
    setRejected("");
    setSaved(false);
    try {
      const result = await api.uploadResume(file);
      setParsed(result);
      setDraft(result.profile);
    } catch (e) {
      setRejected(file.name);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      await api.saveProfile(draft);
      await loadProfile(true);
      await reload();
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const unverified = new Set(parsed?.unverified ?? []);

  return (
    <AppShell>
      <div className="scroll fade flex-1 px-5 py-6 lg:px-10 lg:pt-9 lg:pb-12">
        <div className="mx-auto max-w-[820px]">
          <h1 className="m-0 text-[22px] font-[640] tracking-[-0.026em] lg:text-[26px]">
            Your profile
          </h1>
          <p className="mt-2 text-[13.5px] text-muted lg:text-[14.5px]">
            Everything on every tailored resume comes from here. Nothing else gets invented.
          </p>

          {/* ── what's on file ────────────────────────────────────────── */}
          {existing && !parsed && (
            <div
              className="card mt-6 p-5"
              style={{ borderColor: "var(--aline)", background: "var(--tint)" }}
            >
              <div className="flex flex-wrap items-center gap-4">
                <span
                  className="grid size-10 flex-none place-items-center rounded border bg-surface"
                  style={{ borderColor: "var(--aline)", color: "var(--accent)" }}
                >
                  <IconFile size={20} strokeWidth={1.5} />
                </span>
                <div className="min-w-0 flex-1 basis-[200px]">
                  <div className="text-[14.5px] font-[640]">{existing.contact.name}</div>
                  <div className="mt-[3px] text-[12.5px] text-muted">
                    {existing.experience.length} role
                    {existing.experience.length === 1 ? "" : "s"} · {existing.projects.length} project
                    {existing.projects.length === 1 ? "" : "s"} · {profileBullets(existing)} bullets
                    {existing.source_filename && ` — from ${existing.source_filename}`}
                  </div>
                </div>
                <Link href="/tailor" className="btn btn-primary">
                  <IconSparkle size={15} />
                  Tailor a resume
                </Link>
              </div>
            </div>
          )}

          {/* ── what we read, for the "review" link to land on ────────── */}
          {existing && !parsed && (
            <>
              <h2 className="mt-7 mb-3 text-[15px] font-[640]">What we read</h2>
              {existing.experience.map((e) => (
                <div key={e.id} className="card mb-3.5 p-5">
                  <div className="flex items-baseline justify-between gap-2.5">
                    <span className="text-[13px] font-[640]">
                      {e.title}, {e.company}
                    </span>
                    <span className="flex-none text-[11px] text-muted">
                      {e.start} – {e.end ?? "Present"}
                    </span>
                  </div>
                  <ul className="mt-2.5 flex list-disc flex-col gap-[7px] pl-4">
                    {e.bullets.map((b) => (
                      <li key={b.id} className="text-[13px] leading-[1.62]">
                        {b.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {existing.projects.map((p) => (
                <div key={p.id} className="card mb-3.5 p-5">
                  <div className="flex items-baseline justify-between gap-2.5">
                    <span className="text-[13px] font-[640]">{p.name}</span>
                    <span className="flex-none text-[11px] text-muted">{p.tech.join(", ")}</span>
                  </div>
                  <ul className="mt-2.5 flex list-disc flex-col gap-[7px] pl-4">
                    {p.bullets.map((b) => (
                      <li key={b.id} className="text-[13px] leading-[1.62]">
                        {b.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {existing.skills.length > 0 && (
                <div className="card mb-3.5 p-5">
                  <div className="eyebrow">Skills</div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {existing.skills.flatMap((g) =>
                      g.skills.map((s) => (
                        <span key={`${g.name}-${s}`} className="sk">
                          {s}
                        </span>
                      )),
                    )}
                  </div>
                </div>
              )}
              <p className="mt-6 text-[12.5px] text-muted">
                Something wrong? Upload the file again — nothing is saved until you confirm the
                parse.
              </p>
            </>
          )}

          {/* ── upload ────────────────────────────────────────────────── */}
          {!parsed && <Dropzone busy={busy} onFile={onFile} replacing={!!existing} />}

          {/* ── a file we couldn't read ───────────────────────────────── */}
          {error && !parsed && (
            <div
              className="card mt-5 p-[18px]"
              style={{ borderColor: "var(--badl)", background: "var(--badt)" }}
            >
              <div className="flex items-start gap-3">
                <span
                  className="grid size-8 flex-none place-items-center rounded border bg-surface"
                  style={{ borderColor: "var(--badl)", color: "var(--bad)" }}
                >
                  <IconAlert size={17} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-[640]" style={{ color: "var(--bad)" }}>
                    We couldn&rsquo;t read {rejected || "that file"}
                  </div>
                  <p className="mt-[7px] text-[12.5px] leading-[1.6]" style={{ color: "#5a4444" }}>
                    {error}
                  </p>
                  <p className="mt-2 text-[11.5px] leading-[1.6] text-muted">
                    A scan or a photo has no text layer, so a parser — and an employer&rsquo;s ATS —
                    sees an image rather than words. Export a PDF from the original document if you
                    can.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ── review ────────────────────────────────────────────────── */}
          {parsed && draft && (
            <>
              <ParseSummary parsed={parsed} />

              <div className="mt-6 flex items-baseline justify-between gap-3">
                <h2 className="m-0 text-[15px] font-[640]">Check this is right</h2>
                <button
                  className="btn btn-quiet btn-xs"
                  onClick={() => {
                    setParsed(null);
                    setDraft(null);
                  }}
                >
                  Start over
                </button>
              </div>

              <div className="card mt-3 p-5">
                <div className="grid gap-3.5 sm:grid-cols-3">
                  <div>
                    <label className="lbl">Name</label>
                    <input
                      className="inp"
                      value={draft.contact.name}
                      onChange={(e) =>
                        setDraft({ ...draft, contact: { ...draft.contact, name: e.target.value } })
                      }
                    />
                  </div>
                  <div>
                    <label className="lbl">Email</label>
                    <input
                      className="inp"
                      value={draft.contact.email ?? ""}
                      onChange={(e) =>
                        setDraft({ ...draft, contact: { ...draft.contact, email: e.target.value } })
                      }
                    />
                  </div>
                  <div>
                    <label className="lbl">Phone</label>
                    <input
                      className="inp"
                      value={draft.contact.phone ?? ""}
                      onChange={(e) =>
                        setDraft({ ...draft, contact: { ...draft.contact, phone: e.target.value } })
                      }
                    />
                  </div>
                </div>
              </div>

              {draft.experience.map((exp, ei) => (
                <div key={exp.id} className="card mt-3.5 p-5">
                  <div className="flex items-baseline justify-between gap-2.5">
                    <div className="text-[13px] font-[640]">
                      {exp.title}, {exp.company}
                    </div>
                    <div className="flex-none text-[11px] text-muted">
                      {exp.start} – {exp.end ?? "Present"}
                    </div>
                  </div>
                  <div className="mt-2.5 flex flex-col gap-0.5">
                    {exp.bullets.map((b, bi) => (
                      <BulletEdit
                        key={b.id}
                        bullet={b}
                        flagged={unverified.has(b.text)}
                        onChange={(text) => {
                          const next = structuredClone(draft);
                          next.experience[ei].bullets[bi].text = text;
                          setDraft(next);
                        }}
                        onRemove={() => {
                          const next = structuredClone(draft);
                          next.experience[ei].bullets.splice(bi, 1);
                          setDraft(next);
                        }}
                      />
                    ))}
                    {exp.bullets.length === 0 && (
                      <p className="text-[12px]" style={{ color: "var(--bad)" }}>
                        No bullets found for this role — the layout probably confused the parser.
                      </p>
                    )}
                  </div>
                </div>
              ))}

              {draft.projects.map((p, pi) => (
                <div key={p.id} className="card mt-3.5 p-5">
                  <div className="flex items-baseline justify-between gap-2.5">
                    <div className="text-[13px] font-[640]">{p.name}</div>
                    <div className="flex-none text-[11px] text-muted">{p.tech.join(", ")}</div>
                  </div>
                  <div className="mt-2.5 flex flex-col gap-0.5">
                    {p.bullets.map((b, bi) => (
                      <BulletEdit
                        key={b.id}
                        bullet={b}
                        flagged={unverified.has(b.text)}
                        onChange={(text) => {
                          const next = structuredClone(draft);
                          next.projects[pi].bullets[bi].text = text;
                          setDraft(next);
                        }}
                        onRemove={() => {
                          const next = structuredClone(draft);
                          next.projects[pi].bullets.splice(bi, 1);
                          setDraft(next);
                        }}
                      />
                    ))}
                  </div>
                </div>
              ))}

              {draft.skills.length > 0 && (
                <div className="card mt-3.5 p-5">
                  <div className="eyebrow">Skills</div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {draft.skills.flatMap((g) =>
                      g.skills.map((s) => (
                        <span key={`${g.name}-${s}`} className="sk">
                          {s}
                        </span>
                      )),
                    )}
                  </div>
                </div>
              )}

              {draft.education.length > 0 && (
                <div className="card mt-3.5 p-5">
                  <div className="eyebrow">Education</div>
                  {draft.education.map((ed, i) => (
                    <p key={i} className="mt-2 text-[13px] text-muted">
                      <span className="text-ink">{ed.degree}</span>
                      {ed.field && `, ${ed.field}`} — {ed.institution}
                    </p>
                  ))}
                </div>
              )}

              {error && (
                <p className="mt-4 text-[13px]" style={{ color: "var(--bad)" }}>
                  {error}
                </p>
              )}

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button className="btn btn-primary btn-lg" onClick={save} disabled={busy || saved}>
                  {saved ? "Saved" : busy ? "Saving…" : "Looks right — save my profile"}
                </button>
                {saved && (
                  <Link href="/tailor" className="btn btn-ghost btn-lg">
                    Tailor a resume →
                  </Link>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

/* ── pieces ──────────────────────────────────────────────────────────────── */

function Dropzone({
  busy,
  onFile,
  replacing,
}: {
  busy: boolean;
  onFile: (f: File) => void;
  replacing: boolean;
}) {
  const [over, setOver] = useState(false);
  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`drop ${over ? "over" : ""} mt-5 flex min-h-[200px] cursor-pointer flex-col items-center justify-center gap-3 p-6 text-center`}
    >
      <input
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,text/plain"
        className="sr-only"
        disabled={busy}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
      <span
        className="grid size-11 place-items-center rounded border border-line bg-surface"
        style={{ color: "var(--accent)" }}
      >
        <IconUpload size={21} strokeWidth={1.5} />
      </span>
      <span>
        <span className="block text-[13.5px] font-semibold text-ink">
          {busy
            ? "Reading and structuring…"
            : replacing
              ? "Drop a new resume to replace this one"
              : "Drop your resume here"}
        </span>
        <span className="mt-[3px] block text-xs text-muted">
          PDF, DOCX or plain text · up to 8 MB
        </span>
      </span>
      {!busy && <span className="btn btn-primary">Choose a file</span>}
    </label>
  );
}

function ParseSummary({ parsed }: { parsed: ParseResult }) {
  const pct = Math.round(parsed.confidence * 100);
  const tone = pct >= 90 ? "var(--good)" : pct >= 70 ? "var(--warn)" : "var(--bad)";

  return (
    <div className="card mt-5 p-[18px]">
      <div className="flex items-center gap-4">
        <span className="num text-[28px] leading-none font-[650] tracking-[-0.03em]" style={{ color: tone }}>
          {pct}%
        </span>
        <div className="min-w-0">
          <div className="text-sm font-[640]">
            {pct >= 90 ? "Parsed cleanly" : pct >= 70 ? "Parsed, with caveats" : "Parsed poorly"}
          </div>
          <div className="num mt-1 text-[11.5px] text-muted">
            {parsed.extracted_chars.toLocaleString()} characters from {parsed.pages} page
            {parsed.pages === 1 ? "" : "s"}
          </div>
        </div>
      </div>

      {parsed.warnings.map((w) => (
        <p key={w} className="mt-2.5 flex items-start gap-2 text-[11.5px] leading-[1.55] text-muted">
          <IconWarning size={13} style={{ color: "var(--warn)", flex: "0 0 auto" }} />
          {w}
        </p>
      ))}

      {parsed.unverified.length > 0 ? (
        <div
          className="mt-3.5 rounded p-3"
          style={{ background: "var(--badt)", border: "1px solid var(--badl)" }}
        >
          <p className="m-0 text-[12px] font-semibold" style={{ color: "var(--bad)" }}>
            {parsed.unverified.length} line{parsed.unverified.length === 1 ? "" : "s"} could not be
            matched to your document
          </p>
          <p className="mt-1 text-[11.5px] leading-[1.55] text-muted">
            They may have been reworded while parsing. Check them word by word — this profile is what
            everything downstream is verified against.
          </p>
        </div>
      ) : (
        <p className="mt-3 flex items-center gap-2 text-[11.5px]" style={{ color: "var(--good)" }}>
          <IconCheck size={13} />
          Every line traces back to your document.
        </p>
      )}
    </div>
  );
}

function BulletEdit({
  bullet,
  flagged,
  onChange,
  onRemove,
}: {
  bullet: ProfileBullet;
  flagged: boolean;
  onChange: (text: string) => void;
  onRemove: () => void;
}) {
  return (
    <div className={`brow ${flagged ? "flagged" : ""}`}>
      <div className="flex items-start gap-2">
        <textarea
          value={bullet.text}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className="min-h-11 flex-1 resize-none bg-transparent text-[13px] leading-[1.62] outline-none"
        />
        <button className="btn btn-quiet btn-xs flex-none" onClick={onRemove}>
          remove
        </button>
      </div>
      {flagged && (
        <p className="mt-1 text-[11px]" style={{ color: "var(--bad)" }}>
          not found in your original document — verify this
        </p>
      )}
    </div>
  );
}
