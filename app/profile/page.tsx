"use client";

/**
 * Upload a resume, then review what we understood before it is saved.
 *
 * The review step is not politeness. PDF extraction is lossy in ways that depend
 * on how the file was produced, and this profile becomes the ground truth every
 * later stage is checked against — a bullet that is wrong here can never be caught
 * downstream, because downstream checks *against* it. So nothing is persisted
 * until the user confirms, and anything the parser could not trace back to the
 * original document is shown in red rather than quietly accepted.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ParseResult, Profile, ProfileBullet } from "@/lib/types";

export default function ProfilePage() {
  const [existing, setExisting] = useState<Profile | null>(null);
  const [parsed, setParsed] = useState<ParseResult | null>(null);
  const [draft, setDraft] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.profile().then(setExisting).catch(() => setExisting(null));
  }, []);

  async function onFile(file: File) {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const result = await api.uploadResume(file);
      setParsed(result);
      setDraft(result.profile);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    try {
      await api.saveProfile(draft);
      setSaved(true);
      setExisting(draft);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const unverified = new Set(parsed?.unverified ?? []);

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-6 sm:p-10">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your profile</h1>
          <p className="mt-1 text-sm text-muted">
            Everything on every tailored resume comes from here. Nothing else gets invented.
          </p>
        </div>
        <a href="/" className="shrink-0 text-sm text-muted hover:text-ink">← applications</a>
      </header>

      {existing && !parsed && (
        <div className="rounded border border-line bg-surface p-4 text-sm">
          <div className="font-medium">{existing.contact.name}</div>
          <div className="mt-1 text-muted">
            {existing.experience.length} role(s) ·{" "}
            {existing.experience.reduce((n, e) => n + e.bullets.length, 0)} bullets
            {existing.source_filename && ` · from ${existing.source_filename}`}
          </div>
        </div>
      )}

      <Dropzone busy={busy} onFile={onFile} replacing={!!existing} />
      {error && <p className="text-sm text-bad">{error}</p>}

      {parsed && draft && (
        <>
          <ParseSummary parsed={parsed} />

          <section className="space-y-4">
            <h2 className="text-sm font-medium text-muted">Check this is right</h2>

            <Field label="Name" value={draft.contact.name}
                   onChange={(v) => setDraft({ ...draft, contact: { ...draft.contact, name: v } })} />
            <Field label="Email" value={draft.contact.email ?? ""}
                   onChange={(v) => setDraft({ ...draft, contact: { ...draft.contact, email: v } })} />
            <Field label="Phone" value={draft.contact.phone ?? ""}
                   onChange={(v) => setDraft({ ...draft, contact: { ...draft.contact, phone: v } })} />

            {draft.experience.map((exp, ei) => (
              <div key={exp.id} className="rounded border border-line bg-surface p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <div className="text-sm font-semibold">{exp.title}, {exp.company}</div>
                  <div className="shrink-0 text-xs text-muted">
                    {exp.start} – {exp.end ?? "Present"}
                  </div>
                </div>
                <div className="mt-2 space-y-2">
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
                    <p className="text-xs text-bad">
                      No bullets found for this role — the layout probably confused the parser.
                    </p>
                  )}
                </div>
              </div>
            ))}

            {draft.skills.length > 0 && (
              <div className="rounded border border-line bg-surface p-4 text-sm">
                <div className="mb-2 font-semibold">Skills</div>
                {draft.skills.map((g) => (
                  <p key={g.name} className="text-muted">
                    <span className="text-ink">{g.name}:</span> {g.skills.join(", ")}
                  </p>
                ))}
              </div>
            )}

            {draft.education.length > 0 && (
              <div className="rounded border border-line bg-surface p-4 text-sm">
                <div className="mb-2 font-semibold">Education</div>
                {draft.education.map((ed, i) => (
                  <p key={i} className="text-muted">
                    {ed.degree}{ed.field && `, ${ed.field}`} — {ed.institution}
                  </p>
                ))}
              </div>
            )}
          </section>

          <div className="flex items-center gap-3">
            <button onClick={save} disabled={busy || saved}
                    className="rounded bg-accent px-4 py-2 text-sm font-medium text-white
                               disabled:opacity-40">
              {saved ? "Saved" : busy ? "Saving…" : "Looks right — save"}
            </button>
            {saved && <a href="/" className="text-sm text-accent">Tailor a resume →</a>}
          </div>
        </>
      )}
    </main>
  );
}

function Dropzone({ busy, onFile, replacing }: {
  busy: boolean; onFile: (f: File) => void; replacing: boolean;
}) {
  const [over, setOver] = useState(false);
  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault(); setOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`block cursor-pointer rounded border border-dashed p-8 text-center
                  ${over ? "border-accent bg-surface" : "border-line"}`}
    >
      <input
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,text/plain"
        className="sr-only"
        disabled={busy}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
      <div className="text-sm font-medium">
        {busy ? "Reading and structuring…" : replacing
          ? "Drop a new resume to replace this one"
          : "Drop your resume here, or click to choose"}
      </div>
      <div className="mt-1 text-xs text-muted">PDF, DOCX or plain text · up to 8 MB</div>
    </label>
  );
}

function ParseSummary({ parsed }: { parsed: ParseResult }) {
  const pct = Math.round(parsed.confidence * 100);
  const tone = pct >= 90 ? "good" : pct >= 70 ? "warn" : "bad";
  const toneClass = { good: "text-good", warn: "text-warn", bad: "text-bad" }[tone];

  return (
    <section className="space-y-3 rounded border border-line bg-surface p-4">
      <div className="flex items-baseline gap-3">
        <span className={`text-2xl font-semibold tabular-nums ${toneClass}`}>{pct}%</span>
        <div className="text-sm">
          <div className="font-medium">
            {pct >= 90 ? "Parsed cleanly" : pct >= 70 ? "Parsed, with caveats" : "Parsed poorly"}
          </div>
          <div className="text-xs text-muted">
            {parsed.extracted_chars.toLocaleString()} characters from {parsed.pages} page(s)
          </div>
        </div>
      </div>

      {parsed.warnings.map((w) => (
        <p key={w} className="text-xs text-warn">! {w}</p>
      ))}

      {parsed.unverified.length > 0 && (
        <div className="rounded bg-bad/5 p-3">
          <p className="text-xs font-medium text-bad">
            {parsed.unverified.length} line(s) could not be matched to your document
          </p>
          <p className="mt-1 text-xs text-muted">
            These may have been reworded while parsing. Check them word by word — this
            profile is what everything else is verified against.
          </p>
        </div>
      )}
    </section>
  );
}

function Field({ label, value, onChange }: {
  label: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <label className="flex items-center gap-3 text-sm">
      <span className="w-16 shrink-0 text-muted">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 rounded border border-line bg-surface px-2 py-1.5 outline-none
                   focus:border-accent"
      />
    </label>
  );
}

function BulletEdit({ bullet, flagged, onChange, onRemove }: {
  bullet: ProfileBullet; flagged: boolean;
  onChange: (text: string) => void; onRemove: () => void;
}) {
  return (
    <div className={`rounded border px-2 py-1.5 ${flagged ? "border-bad" : "border-transparent"}`}>
      <div className="flex items-start gap-2">
        <textarea
          value={bullet.text}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className="min-h-[2.75rem] flex-1 resize-none bg-transparent text-sm leading-relaxed
                     outline-none"
        />
        <button onClick={onRemove}
                className="shrink-0 text-xs text-muted hover:text-bad">remove</button>
      </div>
      {flagged && (
        <p className="text-[11px] text-bad">not found in your original document — verify this</p>
      )}
    </div>
  );
}
