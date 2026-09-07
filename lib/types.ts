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

// --- analysis (mirrors models/analysis.py) -----------------------------------

export type Evidence = {
  bullet_id: string;
  excerpt: string;
  reason: string;
  score: number;
};

export type RequirementMatch = {
  requirement_id: string;
  requirement: string;
  skill: string | null;
  kind: "must" | "nice";
  verdict: "strong" | "partial" | "weak" | "absent";
  confidence: number;
  evidence: Evidence[];
};

export type SubScore = {
  name: string;
  score: number;
  weight: number;
  detail: string;
  inputs: string[];
};

export type AnalysisGap = {
  requirement_id: string;
  requirement: string;
  kind: "must" | "nice";
  category: "missing" | "underrepresented" | "semantically_equivalent" | "transferable";
  confidence: "high" | "low";
  suggestion: string;
};

export type Analysis = {
  id: string;
  job_id: string;
  overall: number;
  band: "strong" | "partial" | "weak";
  subscores: SubScore[];
  matches: RequirementMatch[];
  gaps: AnalysisGap[];
  keywords_hit: string[];
  keywords_missed: string[];
};

export type CoverLetter = {
  job_id: string;
  greeting: string;
  paragraphs: string[];
  signoff: string;
  name: string;
};

export const STATUSES = [
  "draft", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn",
] as const;

export type Status = (typeof STATUSES)[number];

/** Stage grouping used by the pipeline strip and the KPI cards. */
export const PIPELINE: Status[] = [
  "draft", "applied", "screening", "interviewing", "offer", "rejected",
];

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  applied: "Applied",
  screening: "Screening",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};
