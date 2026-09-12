"use client";

/**
 * "Resumes recast" — the running total for this account.
 *
 * Its own component and its own request, deliberately. The number could be
 * derived from the applications list the home screen already loads, but that
 * list counts job descriptions pasted rather than resumes produced, and the two
 * drift apart the moment someone starts an application and does not finish it.
 * `/stats` answers the question with a count query instead.
 *
 * Three states, all of which happen on a real account: loading (a placeholder
 * the same height as the number, so nothing jumps when it arrives), zero (day
 * one — a prompt rather than a bare 0), and a figure.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { IconSparkle } from "./icons";

export default function RecastCount() {
  const [count, setCount] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    api
      .stats()
      .then((s) => live && setCount(s.recasted))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

  // A count that will not load is not worth an error banner on the home screen —
  // the applications list below carries the same failure louder. Take the tile
  // away rather than showing a wrong number or a red box.
  if (failed) return null;

  const loading = count === null;
  const none = count === 0;

  return (
    <div className="card mt-5 flex flex-wrap items-center gap-x-5 gap-y-3 p-[18px]">
      <span
        className="grid size-10 flex-none place-items-center rounded"
        style={{
          background: "var(--tint)",
          border: "1px solid var(--aline)",
          color: "var(--accent)",
        }}
      >
        <IconSparkle size={19} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] font-semibold text-muted">Resumes recast</div>
        {/* The live region is the visible text itself rather than a duplicate
            sr-only copy of it, so the number is announced once when it lands
            and not twice. */}
        <div className="mt-1.5 flex items-baseline gap-2.5" aria-live="polite" aria-busy={loading}>
          {loading ? (
            <span
              className="block h-[30px] w-[52px] rounded-[3px]"
              style={{ background: "#eef1f4" }}
              aria-hidden
            />
          ) : (
            <span className="num text-[32px] leading-none font-[650] tracking-[-0.03em]">
              {count}
            </span>
          )}
          <span className="text-[12.5px] text-muted">
            {loading
              ? "Counting…"
              : none
                ? "None yet — the first one takes a paste and a minute."
                : `Tailored to ${count === 1 ? "a specific posting" : "specific postings"}, all time.`}
          </span>
        </div>
      </div>

      {none && (
        <Link href="/tailor" className="btn btn-ghost flex-none">
          Recast one
        </Link>
      )}
    </div>
  );
}
