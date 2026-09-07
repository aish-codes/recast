"use client";

/**
 * The landing page — Main.dc.html on desktop, MobileLanding.dc.html below the
 * 900px break, with one substitution: where the mockup signs you in with
 * Google, this build has a shared password, so the password field takes the
 * primary CTA's place. Everything else — the pipeline diagram, the three steps,
 * the trust row, the deep-ground closer — is the design as drawn.
 *
 * This doubles as the sign-in screen because middleware sends every
 * unauthenticated request here.
 */

import { useEffect, useRef, useState } from "react";
import {
  IconArrowRight,
  IconBrackets,
  IconChevronDown,
  IconFile,
  IconLock,
  IconMail,
  IconPencil,
  IconSend,
  IconSliders,
  IconSpark,
  IconShield,
  IconTarget,
  IconUpload,
} from "@/components/icons";

const STAGES = [
  {
    icon: <IconFile size={15} />,
    title: "Your resume",
    note: "Parsed once into your master profile",
  },
  {
    icon: <IconTarget size={15} />,
    title: "Analysis",
    note: "Every requirement read out of the posting",
  },
  {
    icon: <IconPencil size={15} />,
    title: "Recast resume",
    note: "Reordered, re-emphasised — nothing invented",
  },
  {
    icon: <IconSend size={15} />,
    title: "Application",
    note: "Tracked from saved through to offer",
  },
];

export default function Landing() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(-1);
  const field = useRef<HTMLInputElement>(null);

  // Walk the pipeline diagram slowly so it is never dead on arrival.
  useEffect(() => {
    const id = setInterval(() => setStage((s) => (s + 1) % 5), 1600);
    return () => clearInterval(id);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (res.ok) window.location.href = "/";
    else setError("That password didn't match.");
  }

  function focusField() {
    window.scrollTo({ top: 0, behavior: "smooth" });
    field.current?.focus();
  }

  return (
    <div className="min-h-screen">
      {/* ── nav ─────────────────────────────────────────────────────────── */}
      <header
        className="sticky top-0 z-50 border-b border-line"
        style={{ background: "rgba(255,255,255,.86)", backdropFilter: "blur(8px)" }}
      >
        <div className="wrap flex h-[72px] items-center justify-between gap-8">
          <span className="text-xl font-[640] tracking-[-0.03em]">recast</span>
          <nav className="hidden items-center gap-7 md:flex">
            <a className="navlink" href="#how">
              How it works
            </a>
            <a className="navlink" href="#why">
              Why Recast
            </a>
            <a className="navlink" href="#privacy">
              Privacy
            </a>
          </nav>
          <button className="btn btn-primary" onClick={focusField}>
            Get started
          </button>
        </div>
      </header>

      {/* ── hero ────────────────────────────────────────────────────────── */}
      <section className="pt-14 pb-16 lg:pt-[88px] lg:pb-[84px]">
        <div className="wrap flex flex-col items-center text-center">
          <span
            className="inline-flex items-center gap-2 rounded px-3 py-1.5 text-[12.5px] font-semibold"
            style={{
              background: "var(--tint)",
              border: "1px solid var(--aline)",
              color: "var(--accent)",
            }}
          >
            <IconSpark size={13} />
            One resume. Tailored for every opportunity.
          </span>

          <h1 className="mt-6 max-w-[880px] text-[33px] leading-[1.08] font-[650] tracking-[-0.032em] lg:text-[60px] lg:leading-[1.05]">
            Your resume. Recast for the job you actually want.
          </h1>

          <p className="mt-4 max-w-[640px] text-[15px] leading-[1.6] text-muted lg:mt-[22px] lg:text-[18px]">
            Upload your resume and a job description. Recast intelligently tailors your resume to
            match the role — while keeping your experience authentic.
          </p>

          {/* the sign-in card, where the mockup puts its Google button */}
          <form onSubmit={submit} className="mt-8 flex w-full max-w-[380px] flex-col gap-2.5">
            <label className="lbl sr-only" htmlFor="password">
              Password
            </label>
            <div className="flex flex-col gap-2.5 sm:flex-row">
              <input
                id="password"
                ref={field}
                type="password"
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Your password"
                className="inp h-12 flex-1 text-[15px]"
              />
              <button className="btn btn-primary btn-md" disabled={busy || !password}>
                {busy ? "Checking…" : "Enter"}
                <IconArrowRight size={17} />
              </button>
            </div>
            {error && (
              <p className="m-0 text-[13px]" style={{ color: "var(--bad)" }}>
                {error}
              </p>
            )}
          </form>

          <p className="mt-4 text-[13px] text-muted">
            PDF or DOCX · Every bullet traces back to one you wrote
          </p>
        </div>

        {/* pipeline infographic */}
        <div className="wrap mt-10 lg:mt-[60px]">
          <div className="card px-5 py-6 lg:px-7">
            <div className="mb-5 flex items-center justify-between gap-4">
              <span className="eyebrow">The whole journey</span>
              <span className="hidden text-xs text-muted sm:inline">
                Four stages — you review every one
              </span>
            </div>

            <div className="flex flex-col lg:flex-row">
              {STAGES.map((s, i) => (
                <div key={s.title} className="contents">
                  <div className={`stage ${stage === i ? "on" : ""} min-w-0 flex-1`}>
                    <div className="mb-3 flex items-center gap-2">
                      <span
                        className="grid size-[26px] place-items-center rounded"
                        style={{ background: "var(--tint2)", color: "var(--accent)" }}
                      >
                        {s.icon}
                      </span>
                      <span className="text-[13px] font-semibold">{s.title}</span>
                    </div>
                    <div className="flex flex-col gap-[7px] rounded-[3px] border border-line bg-ground p-3">
                      {i === 1 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {["Python", "SQL", "A/B testing", "Airflow"].map((k, n) => (
                            <span
                              key={k}
                              className="rounded-[3px] border px-[7px] py-[3px] text-[11px]"
                              style={
                                n === 2
                                  ? {
                                      background: "var(--tint2)",
                                      borderColor: "var(--aline)",
                                      color: "var(--accent)",
                                      fontWeight: 600,
                                    }
                                  : { background: "#fff", borderColor: "var(--line)" }
                              }
                            >
                              {k}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <>
                          <div className="ln-d w-[52%]" />
                          <div className={i === 2 ? "ln-a w-[92%]" : "ln w-[88%]"} />
                          <div className="ln w-[76%]" />
                          <div className={i === 2 ? "ln-a w-[84%]" : "ln w-[82%]"} />
                          <div className="ln w-[64%]" />
                        </>
                      )}
                    </div>
                    <p className="mt-2.5 text-[11.5px] text-muted">{s.note}</p>
                  </div>
                  {i < STAGES.length - 1 && (
                    <span className="grid h-8 flex-none place-items-center text-[#c3ccd6] lg:h-auto lg:w-11">
                      <span className="rotate-90 lg:rotate-0">
                        <IconArrowRight size={18} />
                      </span>
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── how it works ────────────────────────────────────────────────── */}
      <section id="how" className="border-y border-line bg-surface py-16 lg:py-24">
        <div className="wrap">
          <span className="eyebrow">How it works</span>
          <h2 className="h2 mt-3.5 max-w-[640px]">Three steps. Nothing rewritten from scratch.</h2>
          <p className="lede mt-3.5 max-w-[560px]">
            You bring the experience. Recast decides what to put forward for this particular job.
          </p>

          <div className="mt-8 grid gap-5 lg:mt-12 lg:grid-cols-3 lg:gap-6">
            {[
              {
                n: "01",
                icon: <IconUpload size={20} strokeWidth={1.5} />,
                title: "Upload",
                body: "Upload your existing resume and the job description.",
              },
              {
                n: "02",
                icon: <IconTarget size={20} strokeWidth={1.5} />,
                title: "Tailor",
                body: "Recast analyzes the posting and adapts your resume to emphasize the relevant skills, experience and keywords.",
              },
              {
                n: "03",
                icon: <IconSend size={20} strokeWidth={1.5} />,
                title: "Apply",
                body: "Review, edit and download your tailored resume. Optionally generate a matching cover letter.",
              },
            ].map((s) => (
              <div key={s.n} className="card lift p-[26px]">
                <div className="flex items-center justify-between">
                  <span
                    className="grid size-10 place-items-center rounded"
                    style={{
                      background: "var(--tint)",
                      border: "1px solid var(--aline)",
                      color: "var(--accent)",
                    }}
                  >
                    {s.icon}
                  </span>
                  <span
                    className="num text-[34px] font-[650] tracking-[-0.03em]"
                    style={{ color: "#ccd5de" }}
                  >
                    {s.n}
                  </span>
                </div>
                <h3 className="mt-5 mb-0 text-[17px] font-[640] tracking-[-0.012em]">{s.title}</h3>
                <p className="mt-2 text-sm leading-[1.6] text-muted">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── why recast ──────────────────────────────────────────────────── */}
      <section id="why" className="py-16 lg:py-24">
        <div className="wrap">
          <span className="eyebrow">Why Recast</span>
          <h2 className="h2 mt-3.5 max-w-[660px]">
            Built for people who are tired of rewriting the same resume.
          </h2>

          <div className="mt-8 grid gap-5 lg:mt-11 lg:grid-cols-2">
            {[
              {
                icon: <IconFile size={19} strokeWidth={1.5} />,
                title: "JD-specific resume",
                body: "Tailor your resume to the exact role you're applying for.",
                foot: "Bullets are selected, ordered and rephrased — never written from nothing.",
              },
              {
                icon: <IconBrackets size={19} strokeWidth={1.5} />,
                title: "ATS-friendly",
                body: "Identify the keywords that matter and keep the structure a parser can read.",
                foot: "We read the finished PDF back with a parser and show you what didn't survive.",
              },
              {
                icon: <IconSliders size={19} strokeWidth={1.5} />,
                title: "You stay in control",
                body: "Review and edit every change before downloading.",
                foot: "Nothing is deleted — anything trimmed is set aside, one click from coming back.",
              },
              {
                icon: <IconMail size={19} strokeWidth={1.5} />,
                title: "Cover letter in one click",
                body: "Generate a role-specific cover letter alongside your tailored resume.",
                foot: "Written off the same tailored resume, so it never claims more than the resume does.",
              },
            ].map((c) => (
              <div key={c.title} className="card lift bg-ground p-7">
                <span
                  className="grid size-9 place-items-center rounded"
                  style={{ background: "var(--tint2)", color: "var(--accent)" }}
                >
                  {c.icon}
                </span>
                <h3 className="mt-[18px] mb-0 text-[17px] font-[640] tracking-[-0.012em]">
                  {c.title}
                </h3>
                <p className="mt-2 text-sm leading-[1.6] text-muted">{c.body}</p>
                <p className="mt-3 border-t border-line pt-3 text-[12.5px] leading-[1.55] text-muted">
                  {c.foot}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── trust ───────────────────────────────────────────────────────── */}
      <section id="privacy" className="border-t border-line bg-surface py-16 lg:py-[88px]">
        <div className="wrap">
          <div className="flex flex-wrap items-end justify-between gap-8">
            <div>
              <span className="eyebrow">Your documents</span>
              <h2 className="h2 mt-3.5 max-w-[520px]">Your resume stays yours.</h2>
            </div>
            <p className="lede max-w-[400px] text-[14.5px]">
              Recast is deliberately conservative about what it will do to a document you are going
              to sign your name to.
            </p>
          </div>

          <div className="card mt-9 grid overflow-hidden lg:grid-cols-3">
            {[
              {
                icon: <IconLock size={20} />,
                title: "Your resume remains yours",
                body: "Everything on a tailored resume comes from the profile you uploaded. Nothing else gets invented.",
              },
              {
                icon: <IconPencil size={20} strokeWidth={1.5} />,
                title: "You control every edit",
                body: "Every rewrite shows the original one click away. Revert it, or edit the line yourself.",
              },
              {
                icon: <IconShield size={20} />,
                title: "Checked, not trusted",
                body: "Every rewrite is verified against your own words by a check with no model in the loop.",
              },
            ].map((c, i) => (
              <div
                key={c.title}
                className={`px-7 py-[30px] ${i > 0 ? "border-t border-line lg:border-t-0 lg:border-l" : ""}`}
              >
                <span className="block" style={{ color: "var(--accent)" }}>
                  {c.icon}
                </span>
                <h3 className="mt-4 mb-0 text-[15px] font-[640]">{c.title}</h3>
                <p className="mt-2 text-[13.5px] leading-[1.6] text-muted">{c.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── closer ──────────────────────────────────────────────────────── */}
      <section className="py-20 lg:py-[104px]" style={{ background: "var(--deep)" }}>
        <div className="wrap flex flex-col items-center text-center">
          <h2 className="m-0 max-w-[720px] text-[30px] leading-[1.12] font-[640] tracking-[-0.028em] text-white lg:text-[42px]">
            Ready to make every application count?
          </h2>
          <p className="mt-[18px] text-[17px]" style={{ color: "rgba(255,255,255,.7)" }}>
            One resume. Tailored for every opportunity.
          </p>
          <button className="btn btn-light btn-md mt-8" onClick={focusField}>
            Sign in to Recast
            <IconChevronDown size={17} className="rotate-180" />
          </button>
          <p className="mt-[18px] text-[13px]" style={{ color: "rgba(255,255,255,.55)" }}>
            PDF or DOCX in. PDF or DOCX out.
          </p>
        </div>
      </section>

      {/* ── footer ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-line bg-surface py-8">
        <div className="wrap flex flex-wrap items-center justify-between gap-6">
          <span className="text-[15px] font-[640] tracking-[-0.03em]">recast</span>
          <div className="flex items-center gap-6">
            <a className="navlink" href="#privacy">
              Privacy
            </a>
            <a className="navlink" href="#how">
              How it works
            </a>
            <a className="navlink" href="#why">
              Why Recast
            </a>
          </div>
          <span className="text-[12.5px] text-muted">© {new Date().getFullYear()} Recast</span>
        </div>
      </footer>
    </div>
  );
}
