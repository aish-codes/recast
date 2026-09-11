// One place that knows the API lives at /api/py.
//
// Every call carries the Supabase access token as a bearer header, and the
// Python function verifies it and reads the user id out of it. The token is
// fetched per request rather than held in a variable: supabase-js rotates it in
// the background, and a captured one goes stale while the tab is open.
//
// `getSession()` is right here even though the middleware uses `getUser()`. This
// is the token's owner reading its own token to send it onward, so a round trip
// to revalidate would buy nothing — the server it is being sent to verifies it
// anyway, which is the check that counts.

import { getSupabase } from "./supabase/client";

const BASE = "/api/py";

async function authHeaders(): Promise<Record<string, string>> {
  const supabase = getSupabase();
  if (!supabase) return {}; // Unconfigured: the API is open, as in local dev.
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

/** 401 means the session is gone for good — supabase-js already tried to refresh. */
function bounce(): never {
  window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  throw new Error("Session expired.");
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) bounce();
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail.slice(0, 300) || `${res.status} ${res.statusText}`);
  }
  return res.headers.get("content-type")?.includes("json")
    ? ((await res.json()) as T)
    : ((await res.text()) as unknown as T);
}

/**
 * Fetch a rendered document and hand the browser a blob URL for it.
 *
 * A plain <a href> or window.open cannot carry an Authorization header, so the
 * PDF and DOCX endpoints have to be fetched rather than navigated to. The URL is
 * revoked on the next tick: long enough for the tab or the download to have
 * taken it, short enough not to pin the file in memory for the session.
 */
async function fetchDoc(path: string): Promise<string> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: await authHeaders(),
  });
  if (res.status === 401) bounce();
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail.slice(0, 300) || `${res.status} ${res.statusText}`);
  }
  return URL.createObjectURL(await res.blob());
}

function release(url: string) {
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

import type { Analysis, Application, Ats, CoverLetter, Job, ParseResult, Profile, Resume } from "./types";

export const api = {
  applications: () => req<Application[]>("/applications"),

  profile: () => req<Profile>("/profile"),

  saveProfile: (profile: Profile) =>
    req<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) }),

  // Multipart — must not set Content-Type, the browser adds the boundary.
  uploadResume: async (file: File): Promise<ParseResult> => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/py/resumes", {
      method: "POST",
      body,
      credentials: "include",
      headers: await authHeaders(),
    });
    if (res.status === 401) bounce();
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      throw new Error(detail?.detail ?? `Upload failed (${res.status})`);
    }
    return res.json();
  },

  application: (id: string) =>
    req<{ app: Application; job: Job; resume: Resume }>(`/applications/${id}`),

  create: (raw: string) =>
    req<{ job: Job; resume: Resume; app: Application; ats: Ats }>("/applications", {
      method: "POST",
      body: JSON.stringify({ raw }),
    }),

  saveResume: (id: string, resume: Resume) =>
    req<{ pages: number; trimmed: unknown[]; ats: Ats }>(`/applications/${id}/resume`, {
      method: "PUT",
      body: JSON.stringify(resume),
    }),

  setStatus: (id: string, status: string, note = "") =>
    req<Application>(`/applications/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status, note }),
    }),

  remove: (id: string) => req<{ deleted: string }>(`/applications/${id}`, { method: "DELETE" }),

  preview: (resume: Resume) =>
    req<string>("/preview", { method: "POST", body: JSON.stringify(resume) }),

  atsText: (id: string) => req<string>(`/applications/${id}/ats`),

  // What a parser pulls out of the rendered PDF. Rendered on demand, so this is
  // a fresh read of the resume as it stands rather than a stored number.
  atsReport: (id: string) => req<Ats>(`/applications/${id}/ats.json`),

  // The match dashboard's data: subscores with their inputs, requirement
  // matches with evidence, gaps. Served from cache unless the profile or the
  // ruleset moved on.
  analysis: (id: string) => req<Analysis>(`/applications/${id}/analysis`),

  coverLetter: (id: string) =>
    req<CoverLetter>(`/applications/${id}/cover-letter`, { method: "POST" }),

  getCoverLetter: (id: string) => req<CoverLetter>(`/applications/${id}/cover-letter`),

  /** Open the rendered resume in a new tab. */
  openResume: async (id: string, fmt: "pdf" | "docx" = "pdf") => {
    const url = await fetchDoc(`/applications/${id}/resume.${fmt}`);
    window.open(url, "_blank", "noopener");
    release(url);
  },

  /** Save the rendered resume to disk, named after the application. */
  downloadResume: async (id: string, fmt: "pdf" | "docx" = "pdf") => {
    const url = await fetchDoc(`/applications/${id}/resume.${fmt}`);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${id}.${fmt}`;
    a.click();
    release(url);
  },
};
