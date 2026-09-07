"use client";

/**
 * Tailor Resume — screens 2 and 3 of App.dc.html.
 *
 * Two inputs side by side (your profile, the posting), then the progress card
 * while the pipeline runs. The steps advance on a timer, as they do in the
 * mockup: the API is one synchronous call, so this narrates the order the work
 * happens in rather than reporting measured progress. The last step holds until
 * the response lands.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  IconAlert,
  IconCheck,
  IconFile,
  IconSparkle,
  IconSpark,
  Spinner,
  SpinnerSmall,
} from "@/components/icons";
import { profileBullets, useProfile } from "@/components/useProfile";
import { api } from "@/lib/api";

const STEPS: [string, string][] = [
  ["Reading your profile", "Every bullet you have written, with its tags"],
  ["Understanding the job description", "Pulling out requirements and the words they use"],
  ["Matching relevant experience", "Scoring each of your bullets against the posting"],
  ["Optimizing keywords", "Rephrasing inside your own claims — no new facts"],
  ["Preparing your tailored resume", "Rendering, then reading the PDF back to check it"],
];

export default function TailorPage() {
  const router = useRouter();
  const { profile, loading } = useProfile();

  const [raw, setRaw] = useState("");
  const [wantCover, setWantCover] = useState(false);
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");

  // Walk the narration while the request is in flight, but stop on the last
  // step — pretending to finish before the server has is a lie the user pays
  // for when the screen sits there afterwards.
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!running) return;
    timer.current = setInterval(
      () => setStep((n) => Math.min(n + 1, STEPS.length - 1)),
      2600,
    );
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [running]);

  const ready = !!profile && raw.trim().length > 40;

  async function run() {
    if (!ready) return;
    setRunning(true);
    setStep(0);
    setError("");
    try {
      const { job } = await api.create(raw);
      router.push(`/a/${job.id}${wantCover ? "?tab=cover" : ""}`);
    } catch (e) {
      setError((e as Error).message);
      setRunning(false);
    }
  }

  /* ── the progress card ─────────────────────────────────────────────────── */
  if (running) {
    return (
      <AppShell>
        <div className="fadein grid flex-1 place-items-center p-6 lg:p-10">
          <div className="card w-[560px] max-w-full px-6 pt-8 pb-7 lg:px-[34px]">
            <div className="flex items-center gap-3.5">
              <span className="grid size-[38px] flex-none place-items-center">
                <Spinner />
              </span>
              <div className="min-w-0">
                <h2 className="m-0 text-[19px] font-[640] tracking-[-0.018em]">
                  Recasting your resume…
                </h2>
                <p className="mt-1 text-[13px] text-muted">
                  This usually takes under a minute.
                </p>
              </div>
            </div>

            <div className="mt-6 mb-1 h-1 overflow-hidden rounded-full bg-[#e9edf1]">
              <div
                className="bar-live h-full rounded-full transition-[width] duration-500"
                style={{
                  background: "var(--accent)",
                  width: `${Math.round(((step + 1) / STEPS.length) * 100)}%`,
                }}
              />
            </div>

            <div className="mt-5 flex flex-col gap-0.5">
              {STEPS.map(([label, detail], k) => {
                const done = k < step;
                const active = k === step;
                return (
                  <div key={label} className="flex items-start gap-3 py-[9px]">
                    <span
                      className={`sdot ${done ? "done" : active ? "active" : ""} mt-px grid size-[19px] flex-none place-items-center rounded-full`}
                    >
                      {done && <IconCheck size={11} strokeWidth={3.2} className="text-white" />}
                      {active && <SpinnerSmall />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={`stext ${k <= step ? "on" : ""}`}>{label}</span>
                      {active && (
                        <span className="fade mt-[3px] block text-[11.5px] text-muted">{detail}</span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>

            <p className="mt-5 border-t border-line pt-[18px] text-xs leading-[1.55] text-muted">
              Nothing is final. You&rsquo;ll see every change next to your original wording, and you
              can revert any of it.
            </p>
          </div>
        </div>
      </AppShell>
    );
  }

  /* ── the form ──────────────────────────────────────────────────────────── */
  return (
    <AppShell>
      <div className="scroll fade flex-1 px-5 py-6 lg:px-10 lg:pt-9 lg:pb-12">
        <div className="mx-auto max-w-[1040px]">
          <h1 className="m-0 text-[22px] font-[640] tracking-[-0.026em] lg:text-[26px]">
            Tailor your resume
          </h1>
          <p className="mt-2 text-[13.5px] text-muted lg:text-[14.5px]">
            Give us your resume and the job description. We&rsquo;ll do the matching.
          </p>

          <div className="mt-6 grid gap-5 lg:mt-7 lg:grid-cols-2">
            {/* ── your resume ───────────────────────────────────────────── */}
            <div className="card flex flex-col p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="m-0 text-[15px] font-[640]">Your Resume</h2>
                <span className={`chip ${profile ? "c-move" : "c-edit"}`}>
                  {loading ? "checking…" : profile ? "ready" : "not yet"}
                </span>
              </div>
              <p className="mt-1.5 mb-4 text-[13px] text-muted">
                Everything on a tailored resume comes from here.
              </p>

              {!profile ? (
                <Link
                  href="/profile"
                  className="drop flex min-h-[186px] flex-1 flex-col items-center justify-center gap-3 p-5 text-center"
                >
                  <span
                    className="grid size-11 place-items-center rounded border border-line bg-surface"
                    style={{ color: "var(--accent)" }}
                  >
                    <IconFile size={21} strokeWidth={1.5} />
                  </span>
                  <span>
                    <span className="block text-[13.5px] font-semibold text-ink">
                      No master profile yet
                    </span>
                    <span className="mt-[3px] block text-xs text-muted">
                      PDF or DOCX · up to 8 MB
                    </span>
                  </span>
                  <span className="btn btn-primary">Upload Resume</span>
                </Link>
              ) : (
                <div className="fade flex min-h-[186px] flex-1 flex-col rounded border border-line bg-ground p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-[46px] w-[38px] flex-none flex-col items-center justify-center gap-0.5 rounded-[3px] border border-line bg-surface">
                      <IconFile size={15} className="text-muted" />
                      <span
                        className="text-[7.5px] font-bold tracking-[.05em]"
                        style={{ color: "var(--bad)" }}
                      >
                        {(profile.source_filename?.split(".").pop() ?? "doc").toUpperCase()}
                      </span>
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13.5px] font-semibold">
                        {profile.contact.name}
                      </div>
                      <div className="num mt-[3px] text-xs text-muted">
                        {profile.source_filename ?? "built by hand"}
                      </div>
                    </div>
                    <Link href="/profile" className="btn btn-ghost btn-xs">
                      Replace
                    </Link>
                  </div>

                  <div className="mt-3.5 h-1 overflow-hidden rounded-full bg-[#e3e8ed]">
                    <div className="h-full w-full rounded-full" style={{ background: "var(--good)" }} />
                  </div>

                  <div className="mt-3 flex items-start gap-2" style={{ color: "var(--good)" }}>
                    <IconCheck size={15} className="mt-px flex-none" />
                    <span className="text-[12.5px] font-semibold">
                      Parsed — {profile.experience.length} role
                      {profile.experience.length === 1 ? "" : "s"}, {profile.projects.length} project
                      {profile.projects.length === 1 ? "" : "s"}, {profileBullets(profile)} bullets
                    </span>
                  </div>
                  <p className="mt-1.5 ml-[23px] text-[11.5px] leading-[1.55] text-muted">
                    This is your master profile. Nothing outside it reaches a resume.
                  </p>
                  <Link href="/profile" className="mt-auto ml-[23px] text-xs font-semibold">
                    Review what we read →
                  </Link>
                </div>
              )}
            </div>

            {/* ── job description ───────────────────────────────────────── */}
            <div className="card flex flex-col p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="m-0 text-[15px] font-[640]">Job Description</h2>
                <span className="chip c-edit">{raw.trim() ? "pasted" : "empty"}</span>
              </div>
              <p className="mt-1.5 mb-4 text-[13px] text-muted">
                Paste the whole posting — the boilerplate gets thrown away.
              </p>

              <textarea
                className="ta min-h-[186px] flex-1"
                placeholder="Paste the job description here."
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
              />
              <div className="mt-2.5 flex items-center justify-between gap-3">
                <span className="num text-[11.5px] text-muted">
                  {raw.trim() ? `${raw.trim().length.toLocaleString()} characters` : "Nothing yet"}
                </span>
                <span className="text-[11.5px] text-muted">
                  {raw.trim().length > 40 ? "Long enough to read" : "Paste the full posting"}
                </span>
              </div>
            </div>
          </div>

          {/* ── cover letter + CTA ──────────────────────────────────────── */}
          <div className="card mt-5 p-5">
            <button
              onClick={() => setWantCover((v) => !v)}
              className="flex w-full cursor-pointer items-start gap-3 border-none bg-transparent p-0 text-left"
            >
              <span className={`cbox ${wantCover ? "on" : ""} mt-px`}>
                <IconCheck size={12} strokeWidth={3} className="text-white" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink">
                  Generate a cover letter too
                </span>
                <span className="mt-1 block text-[12.5px] leading-[1.55] text-muted">
                  Written off the tailored resume, so it never claims more than the resume does.
                </span>
              </span>
            </button>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5">
              <p className="m-0 max-w-[420px] text-[12.5px] text-muted">
                {!profile
                  ? "Upload your resume first — there is nothing to tailor from yet."
                  : raw.trim().length > 40
                    ? "Company and job title are read straight out of the posting."
                    : "Paste the posting to get started."}
              </p>
              <button className="btn btn-primary btn-lg" disabled={!ready} onClick={run}>
                <IconSparkle size={18} />
                Tailor My Resume
              </button>
            </div>
          </div>

          {error && (
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
                    We couldn&rsquo;t tailor this one
                  </div>
                  <p className="mt-[7px] text-[12.5px] leading-[1.6]" style={{ color: "#5a4444" }}>
                    {error}
                  </p>
                  <div className="mt-3.5 flex flex-wrap gap-2">
                    <button className="btn btn-primary" onClick={run}>
                      Try again
                    </button>
                    <Link href="/profile" className="btn btn-ghost">
                      Check my profile
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}

          <p className="mt-5 flex items-center justify-center gap-1.5 text-[11.5px] text-muted">
            <IconSpark size={12} />
            Every bullet traces back to one you wrote.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
