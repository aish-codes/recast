"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

/**
 * The master profile, fetched once per page load and shared.
 *
 * Both the shell and the page body want the user's name, and on the editor the
 * whole original resume comes from here — memoising the promise keeps that to
 * one request instead of one per consumer.
 */
let pending: Promise<Profile | null> | null = null;

export function loadProfile(force = false): Promise<Profile | null> {
  if (force || !pending) pending = api.profile().catch(() => null);
  return pending;
}

export function useProfile() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    loadProfile().then((p) => {
      if (!live) return;
      setProfile(p);
      setLoading(false);
    });
    return () => {
      live = false;
    };
  }, []);

  return { profile, loading, reload: () => loadProfile(true).then(setProfile) };
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function firstName(name: string) {
  return name.trim().split(/\s+/)[0] || "";
}

export function profileBullets(p: Profile) {
  return (
    p.summaries.length +
    p.experience.reduce((n, e) => n + e.bullets.length, 0) +
    p.projects.reduce((n, x) => n + x.bullets.length, 0)
  );
}
