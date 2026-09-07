"use client";

/**
 * The application tracker, in both shapes the design specifies: a dense row
 * table on desktop (App.dc.html) and a stack of cards on mobile
 * (MobileApp.dc.html), because a six-column table on a phone is unreadable.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { STATUS_LABEL, type Application } from "@/lib/types";
import { IconArrowRight, IconDownload, IconFile } from "./icons";

const HEAD = "text-[10.5px] font-[650] uppercase tracking-[.07em] text-muted";

function coverage(a: Application) {
  return a.keyword_coverage != null ? `${Math.round(a.keyword_coverage * 100)}%` : "—";
}

function nextStep(a: Application) {
  return a.notes.length ? a.notes[a.notes.length - 1] : "—";
}

function short(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function CompanyTile({ name }: { name: string | null }) {
  return (
    <span className="logo grid size-[22px] flex-none place-items-center rounded text-[10px] font-bold">
      {(name?.trim()[0] ?? "?").toUpperCase()}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={`pill p-${status}`}>
      <span className="dot" />
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export default function ApplicationsTable({
  title,
  rows,
  total,
  onClearFilter,
  emptyTitle = "Nothing at this stage yet.",
  emptyBody = "Move an application here from its detail panel, or clear the filter.",
}: {
  title: string;
  rows: Application[];
  /** When set and larger than rows.length, renders the "view all" footer. */
  total?: number;
  onClearFilter?: () => void;
  emptyTitle?: string;
  emptyBody?: string;
}) {
  const router = useRouter();

  return (
    <div className="card mt-5 overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-line px-[18px] py-[15px]">
        <h2 className="m-0 text-sm font-[640]">{title}</h2>
        <div className="flex items-center gap-2.5">
          {onClearFilter && (
            <button className="btn btn-quiet btn-xs" onClick={onClearFilter}>
              Clear filter
            </button>
          )}
          <span className="num text-[11.5px] text-muted">
            {rows.length} {rows.length === 1 ? "row" : "rows"}
          </span>
        </div>
      </div>

      {/* desktop header */}
      <div className="hidden h-[34px] items-center gap-3.5 border-b border-line bg-ground px-[18px] lg:flex">
        <span className={`min-w-0 flex-1 ${HEAD}`}>Job</span>
        <span className={`flex-none basis-[132px] ${HEAD}`}>Company</span>
        <span className={`flex-none basis-[80px] ${HEAD}`}>Match</span>
        <span className={`flex-none basis-[92px] ${HEAD}`}>Updated</span>
        <span className={`flex-none basis-[124px] ${HEAD}`}>Status</span>
        <span className={`flex-none basis-[168px] ${HEAD}`}>Next step</span>
        <span className="flex-none basis-[62px]" />
      </div>

      {rows.map((a) => (
        <div key={a.job_id}>
          {/* desktop row */}
          <div
            className="trow hidden h-[54px] items-center gap-3.5 border-b border-line px-[18px] lg:flex"
            onClick={() => router.push(`/a/${a.job_id}`)}
          >
            <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold">
              {a.role ?? "Untitled role"}
            </span>
            <span className="flex min-w-0 flex-none basis-[132px] items-center gap-2">
              <CompanyTile name={a.company} />
              <span className="truncate text-[13px]">{a.company ?? "—"}</span>
            </span>
            <span className="num flex-none basis-[80px] text-[12.5px] text-muted">{coverage(a)}</span>
            <span className="num flex-none basis-[92px] text-[12.5px] text-muted">{short(a.updated)}</span>
            <span className="flex-none basis-[124px]">
              <StatusPill status={a.status} />
            </span>
            <span className="min-w-0 flex-none basis-[168px] truncate text-[12.5px] text-muted">
              {nextStep(a)}
            </span>
            <span className="acts flex flex-none basis-[62px] justify-end gap-1">
              <span className="tip">
                <Link
                  href={`/a/${a.job_id}`}
                  className="btn btn-quiet btn-xs w-[26px] p-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <IconFile size={14} strokeWidth={1.7} />
                </Link>
                <span className="tipbody w-[140px]">Open the tailored resume</span>
              </span>
              <span className="tip">
                <a
                  href={api.pdfUrl(a.job_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-quiet btn-xs w-[26px] p-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <IconDownload size={14} strokeWidth={1.7} />
                </a>
                <span className="tipbody w-[140px]">Download the PDF</span>
              </span>
            </span>
          </div>

          {/* mobile card */}
          <Link
            href={`/a/${a.job_id}`}
            className="block border-b border-line p-3.5 last:border-0 lg:hidden"
          >
            <div className="flex items-start gap-[11px]">
              <span className="logo grid size-[30px] flex-none place-items-center rounded text-[12px] font-bold">
                {(a.company?.trim()[0] ?? "?").toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-[640] text-ink">{a.role ?? "Untitled role"}</div>
                <div className="num mt-[3px] text-[11.5px] text-muted">
                  {a.company ?? "—"} · {short(a.updated)}
                </div>
              </div>
              <StatusPill status={a.status} />
            </div>
            <div className="mt-[11px] flex items-center justify-between gap-2.5 border-t border-line pt-[11px]">
              <span className="truncate text-[11.5px] text-muted">
                {nextStep(a) === "—" ? "No next step noted" : nextStep(a)}
              </span>
              <span className="num flex-none text-[11.5px] font-[650] text-accent">{coverage(a)}</span>
            </div>
          </Link>
        </div>
      ))}

      {total != null && total > rows.length && (
        <Link
          href="/applications"
          className="flex h-[47px] w-full items-center justify-center gap-[7px] text-[12.5px] font-semibold"
        >
          View all {total} applications
          <IconArrowRight size={14} />
        </Link>
      )}

      {rows.length === 0 && (
        <div className="px-5 py-[52px] text-center">
          <p className="m-0 text-[13.5px] font-semibold">{emptyTitle}</p>
          <p className="mt-1.5 text-[12.5px] text-muted">{emptyBody}</p>
          {onClearFilter && (
            <button className="btn btn-ghost mt-4" onClick={onClearFilter}>
              Show all applications
            </button>
          )}
        </div>
      )}
    </div>
  );
}
