"use client";

/**
 * Home — the dashboard from App.dc.html (screen 5, "isHome").
 *
 * Where the job search stands: four counts, the pipeline as a clickable strip,
 * and the most recent applications. Day one has none of that, so it shows the
 * empty state from States.dc.html instead of four zeroes.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import ApplicationsTable from "@/components/ApplicationsTable";
import {
  IconArrowRight,
  IconCalendar,
  IconChat,
  IconClock,
  IconSparkle,
  IconStar,
} from "@/components/icons";
import { firstName, useProfile } from "@/components/useProfile";
import { api } from "@/lib/api";
import { PIPELINE, STATUS_LABEL, type Application } from "@/lib/types";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function Kpi({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
  icon: React.ReactNode;
  tone?: "good";
}) {
  return (
    <div className="card lift p-[18px]">
      <div className="flex items-start justify-between">
        <span className="text-[12.5px] font-semibold text-muted">{label}</span>
        <span style={{ color: "#b6c1cc" }}>{icon}</span>
      </div>
      <div
        className="num mt-2.5 text-[32px] leading-none font-[650] tracking-[-0.03em]"
        style={tone === "good" ? { color: "var(--good)" } : undefined}
      >
        {value}
      </div>
      <div className="mt-2 text-[11.5px] text-muted">{hint}</div>
    </div>
  );
}

export default function Home() {
  const { profile } = useProfile();
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .applications()
      .then((list) =>
        setApps([...list].sort((a, b) => (a.updated < b.updated ? 1 : -1))),
      )
      .catch((e) => setError((e as Error).message));
  }, []);

  const count = (s: string) => (apps ?? []).filter((a) => a.status === s).length;
  const total = apps?.length ?? 0;
  const inProgress = count("applied") + count("screening") + count("interviewing");
  const max = Math.max(1, ...PIPELINE.map(count));

  const name = profile ? firstName(profile.contact.name) : "";

  return (
    <AppShell appCount={apps?.length}>
      <div className="scroll fade flex-1 px-5 py-6 lg:px-9 lg:pt-8 lg:pb-12">
        <div className="mx-auto max-w-[1120px]">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <h1 className="m-0 text-[22px] font-[640] tracking-[-0.026em] lg:text-[26px]">
                {greeting()}
                {name && `, ${name}`}
              </h1>
              <p className="mt-2 text-[13.5px] text-muted lg:text-[14.5px]">
                {total === 0
                  ? "Nothing here yet — let's fix that."
                  : "Here's where your job search stands."}
              </p>
            </div>
            <Link href="/tailor" className="btn btn-primary">
              <IconSparkle size={15} />
              Tailor a resume
            </Link>
          </div>

          {error && (
            <div
              className="card mt-5 p-4 text-[13px]"
              style={{ borderColor: "var(--badl)", background: "var(--badt)", color: "var(--bad)" }}
            >
              {error}
            </div>
          )}

          {apps === null && !error && (
            <p className="mt-8 text-[13px] text-muted">Loading…</p>
          )}

          {/* ── day one ─────────────────────────────────────────────────── */}
          {apps?.length === 0 && (
            <div className="card mt-5 px-7 py-9 text-center">
              <span className="mx-auto flex h-[70px] w-[112px] items-center justify-center gap-2.5">
                <span className="flex h-12 w-[38px] flex-col justify-center gap-1 rounded-[3px] border border-line bg-ground p-[7px]">
                  <span className="h-1 w-[70%] rounded-[2px]" style={{ background: "#d7dee5" }} />
                  <span className="h-[3px] rounded-[2px]" style={{ background: "#e6ebf0" }} />
                  <span className="h-[3px] w-[85%] rounded-[2px]" style={{ background: "#e6ebf0" }} />
                </span>
                <IconArrowRight size={16} className="text-[#c3ccd6]" />
                <span
                  className="flex h-12 w-[38px] flex-col justify-center gap-1 rounded-[3px] p-[7px]"
                  style={{ background: "var(--tint)", border: "1px solid var(--aline)" }}
                >
                  <span className="h-1 w-[70%] rounded-[2px]" style={{ background: "var(--aline)" }} />
                  <span className="h-[3px] rounded-[2px]" style={{ background: "var(--aline)" }} />
                  <span className="h-[3px] w-[85%] rounded-[2px]" style={{ background: "#e6ebf0" }} />
                </span>
              </span>
              <div className="mt-4 text-[15px] font-[640]">No applications yet</div>
              <p className="mx-auto mt-[7px] max-w-[340px] text-[12.5px] leading-[1.6] text-muted">
                Tailor a resume to a posting and Recast starts the tracker for you — the version you
                sent, the date, and what happens next.
              </p>
              <div className="mt-[18px] flex justify-center gap-2.5">
                <Link href="/tailor" className="btn btn-primary">
                  Tailor my first resume
                </Link>
                {!profile && (
                  <Link href="/profile" className="btn btn-ghost">
                    Upload my resume
                  </Link>
                )}
              </div>
            </div>
          )}

          {/* ── the running search ──────────────────────────────────────── */}
          {apps && apps.length > 0 && (
            <>
              <div className="mt-6 grid grid-cols-2 gap-2.5 lg:grid-cols-4 lg:gap-4">
                <Kpi
                  label="Applications"
                  value={total}
                  hint={`${count("draft")} still a draft`}
                  icon={<IconCalendar size={16} strokeWidth={1.7} />}
                />
                <Kpi
                  label="In Progress"
                  value={inProgress}
                  hint={`${count("applied")} awaiting a reply`}
                  icon={<IconClock size={16} strokeWidth={1.7} />}
                />
                <Kpi
                  label="Interviews"
                  value={count("interviewing")}
                  hint={count("interviewing") ? "Keep the notes current" : "None scheduled"}
                  icon={<IconChat size={16} strokeWidth={1.7} />}
                />
                <Kpi
                  label="Offers"
                  value={count("offer")}
                  hint={count("offer") ? "Congratulations" : "Not yet"}
                  icon={<IconStar size={16} strokeWidth={1.7} />}
                  tone={count("offer") ? "good" : undefined}
                />
              </div>

              <div className="card mt-5 p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="m-0 text-sm font-[640]">Pipeline</h2>
                  <span className="text-[11.5px] text-muted">
                    <span className="hidden lg:inline">Pick a stage to filter</span>
                    <span className="lg:hidden">Swipe for more</span>
                  </span>
                </div>
                <div className="mt-4 flex items-stretch gap-2 overflow-x-auto pb-1 lg:gap-0 lg:overflow-visible lg:pb-0">
                  {PIPELINE.map((stage, i) => (
                    <div key={stage} className="contents">
                      <Link
                        href={`/applications?stage=${stage}`}
                        className="stagebox min-w-[104px] flex-none lg:min-w-0 lg:flex-1"
                      >
                        <span className="num block text-[22px] leading-none font-[650] tracking-[-0.028em]">
                          {count(stage)}
                        </span>
                        <span className="mt-1.5 block text-[11.5px] font-semibold text-muted">
                          {STATUS_LABEL[stage]}
                        </span>
                        <span className="mt-[9px] block h-[3px] overflow-hidden rounded-full bg-[#e9edf1]">
                          <span
                            className={`block h-full rounded-full ${stage === "rejected" ? "bar-mut" : "bar"}`}
                            style={{ width: `${Math.round((count(stage) / max) * 100)}%` }}
                          />
                        </span>
                      </Link>
                      {i < PIPELINE.length - 1 && (
                        <span className="hidden w-[22px] flex-none place-items-center text-[#c8d2dc] lg:grid">
                          <IconArrowRight size={14} />
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <ApplicationsTable
                title="Recent applications"
                rows={apps.slice(0, 6)}
                total={apps.length}
              />
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
