// Mirrors src/recast/models/*.py. The client never invents shapes — it round-trips
// the same TailoredResume the pipeline produced.

export type Bullet = {
  source_id: string;
  text: string;
  original: string;
  score: number;
  rationale: string;
  keywords_hit: string[];
  flags: string[];
  locked: boolean;
};

export type Experience = {
  source_id: string;
  company: string;
  title: string;
  location: string | null;
  start: string;
  end: string | null;
  bullets: Bullet[];
};

export type Project = {
  source_id: string;
  name: string;
  url: string | null;
  tech: string[];
  bullets: Bullet[];
};

export type Gap = {
  requirement: string;
  kind: "must" | "nice";
  confidence: "high" | "low";
  suggestion: string;
};

export type Resume = {
  job_id: string;
  company: string | null;
  role: string | null;
  contact: {
    name: string;
    email: string | null;
    phone: string | null;
    location: string | null;
    links: Record<string, string>;
  };
  summary: Bullet | null;
  experience: Experience[];
  projects: Project[];
  skills: { name: string; skills: string[] }[];
  education: unknown[];
  certifications: string[];
  gaps: Gap[];
  trimmed: Bullet[];
};

export type Application = {
  job_id: string;
  company: string | null;
  role: string | null;
  status: string;
  created: string;
  updated: string;
  notes: string[];
  resume_pages: number | null;
  keyword_coverage: number | null;
};

export type Ats = {
  keyword_coverage: number;
  keyword_hits: string[];
  keyword_misses: string[];
  missing_bullets: string[];
  warnings: string[];
  pages: number;
};

export type Job = {
  id: string;
  company: string | null;
  role: string | null;
  seniority: string;
  requirements: { text: string; kind: "must" | "nice"; skill: string | null }[];
  keywords: string[];
};

// --- master profile (the source of truth) ------------------------------------

export type ProfileBullet = {
  id: string;
  text: string;
  tags: string[];
  metric: string | null;
  pinned: boolean;
  hidden: boolean;
};

export type ProfileExperience = {
  id: string;
  company: string;
  title: string;
  location: string | null;
  start: string;
  end: string | null;
  summary: string | null;
  bullets: ProfileBullet[];
};

export type ProfileProject = {
  id: string;
  name: string;
  url: string | null;
  description: string | null;
  tech: string[];
  bullets: ProfileBullet[];
};

export type ProfileEducation = {
  institution: string;
  degree: string;
  field: string | null;
  start: string | null;
  end: string | null;
  detail: string | null;
};

export type Profile = {
  schema_version: 1;
  origin: "upload" | "wizard" | "manual";
  source_filename: string | null;
  parse_confidence: number | null;
  contact: Resume["contact"];
  headline: string | null;
  summaries: ProfileBullet[];
  experience: ProfileExperience[];
  projects: ProfileProject[];
  education: ProfileEducation[];
  skills: { name: string; skills: string[] }[];
  certifications: string[];
  answer_bank: unknown[];
};

export type ParseResult = {
  profile: Profile;
  confidence: number;
  needs_review: boolean;
  warnings: string[];
  unverified: string[];
  extracted_chars: number;
  pages: number;
};

export const STATUSES = [
  "draft", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn",
] as const;
