// One place that knows the API lives at /api/py.
//
// No token handling here on purpose: the session cookie is httpOnly and
// same-origin, so the browser attaches it and page JavaScript never sees the
// secret. `credentials: "include"` is what makes that happen on every call.

const BASE = "/api/py";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail.slice(0, 300) || `${res.status} ${res.statusText}`);
  }
  return res.headers.get("content-type")?.includes("json")
    ? ((await res.json()) as T)
    : ((await res.text()) as unknown as T);
}

import type { Application, Ats, Job, ParseResult, Profile, Resume } from "./types";

export const api = {
  applications: () => req<Application[]>("/applications"),

  profile: () => req<Profile>("/profile"),

  saveProfile: (profile: Profile) =>
    req<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) }),

  // Multipart — must not set Content-Type, the browser adds the boundary.
  uploadResume: async (file: File): Promise<ParseResult> => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/py/resumes", { method: "POST", body, credentials: "include" });
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Session expired.");
    }
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

  coverLetter: (id: string) =>
    req<{ paragraphs: string[]; greeting: string; signoff: string; name: string }>(
      `/applications/${id}/cover-letter`,
      { method: "POST" },
    ),

  pdfUrl: (id: string) => `${BASE}/applications/${id}/resume.pdf`,
  docxUrl: (id: string) => `${BASE}/applications/${id}/resume.docx`,
};
