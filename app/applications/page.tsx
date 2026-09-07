"use client";

/**
 * My Applications — the filtered tracker from App.dc.html (screen 5,
 * "isAppsList"). The stage strip on Home links in here with ?stage=…, so the
 * filter is addressable and survives a reload.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import ApplicationsTable from "@/components/ApplicationsTable";
import { IconSparkle } from "@/components/icons";
import { api } from "@/lib/api";
import { PIPELINE, STATUS_LABEL, type Application } from "@/lib/types";

function ApplicationsBody() {
  const router = useRouter();
  const params = useSearchParams();
  const stage = params.get("stage");

  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .applications()
      .then((list) => setApps([...list].sort((a, b) => (a.updated < b.updated ? 1 : -1))))
      .catch((e) => setError((e as Error).message));
  }, []);

  const all = apps ?? [];
  const rows = stage ? all.filter((a) => a.status === stage) : all;
  const count = (s: string) => all.filter((a) => a.status === s).length;

  return (
    <AppShell appCount={apps?.length}>
      <div className="scroll fade flex-1 px-5 py-6 lg:px-9 lg:pt-8 lg:pb-12">
        <div className="mx-auto max-w-[1120px]">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <h1 className="m-0 text-[22px] font-[640] tracking-[-0.026em] lg:text-[26px]">
                My Applications
              </h1>
              <p className="mt-2 text-[13.5px] text-muted lg:text-[14.5px]">
                Every role you&rsquo;ve tailored for, and what happens next.
              </p>
            </div>
            <Link href="/tailor" className="btn btn-primary">
              <IconSparkle size={15} />
              Tailor a resume
            </Link>
          </div>

          <div className="mt-5 flex flex-wrap gap-[7px]">
            <button
              className={`fchip ${!stage ? "on" : ""}`}
              onClick={() => router.replace("/applications")}
            >
              All
              <span className="num ml-1.5 opacity-60">{all.length}</span>
            </button>
            {PIPELINE.map((s) => (
              <button
                key={s}
                className={`fchip ${stage === s ? "on" : ""}`}
                onClick={() =>
                  router.replace(stage === s ? "/applications" : `/applications?stage=${s}`)
                }
              >
                {STATUS_LABEL[s]}
                <span className="num ml-1.5 opacity-60">{count(s)}</span>
              </button>
            ))}
          </div>

          {error && (
            <div
              className="card mt-5 p-4 text-[13px]"
              style={{ borderColor: "var(--badl)", background: "var(--badt)", color: "var(--bad)" }}
            >
              {error}
            </div>
          )}

          {apps === null && !error ? (
            <p className="mt-8 text-[13px] text-muted">Loading…</p>
          ) : (
            <ApplicationsTable
              title={stage ? `${STATUS_LABEL[stage]} applications` : "All applications"}
              rows={rows}
              onClearFilter={stage ? () => router.replace("/applications") : undefined}
              emptyTitle={stage ? "Nothing at this stage yet." : "No applications yet."}
              emptyBody={
                stage
                  ? "Move an application here from its status menu, or clear the filter."
                  : "Tailor a resume to a posting and the tracker starts itself."
              }
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense fallback={<AppShell>{<div className="flex-1" />}</AppShell>}>
      <ApplicationsBody />
    </Suspense>
  );
}
