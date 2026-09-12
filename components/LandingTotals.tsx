"use client";

/**
 * The counter band on the landing page — the "live counter" section of
 * Main.dc.html, between the hero and "How it works".
 *
 * The design shows one big figure and a row of smaller ones underneath. Two of
 * those are real numbers the API can stand behind — resumes the pipeline has
 * produced, and accounts that have signed in — so those two are shown, side by
 * side and at equal weight, and the rest of the row is left out rather than
 * filled with placeholders. The design's counter also ticked upward on a timer
 * to look alive; these are actual totals, so they do not.
 *
 * Fetched on the client after the page renders, which is what lets the landing
 * page stay static. While the request is out, boxes the size of the numbers
 * hold the layout so nothing shifts when they arrive. If it fails, the band
 * goes away: a landing page with a broken stat on it is worse than one without.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Totals } from "@/lib/types";

const fmt = (n: number) => n.toLocaleString("en-US");

export default function LandingTotals() {
  const [totals, setTotals] = useState<Totals | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    api
      .totals()
      .then((t) => live && setTotals(t))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

  if (failed) return null;

  const figures: { value: number | null; label: string }[] = [
    { value: totals?.recasted ?? null, label: "Resumes recast" },
    { value: totals?.users ?? null, label: "Job seekers signed up" },
  ];

  return (
    <section className="border-t border-line bg-surface py-12 lg:py-16" aria-label="Recast so far">
      <div className="wrap">
        <div className="mx-auto grid max-w-[720px] grid-cols-2" aria-live="polite" aria-busy={totals === null}>
          {figures.map((f, i) => (
            <div
              key={f.label}
              className={`px-2 py-2 text-center ${i > 0 ? "border-l border-line" : ""}`}
            >
              {f.value === null ? (
                <span
                  className="mx-auto block h-[42px] w-[96px] rounded-[3px] lg:h-[56px] lg:w-[132px]"
                  style={{ background: "#eef1f4" }}
                  aria-hidden
                />
              ) : (
                <div className="num text-[42px] leading-none font-[650] tracking-[-0.035em] lg:text-[56px]">
                  {fmt(f.value)}
                </div>
              )}
              <div className="mt-3 text-[13px] text-muted lg:text-[14.5px]">{f.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
