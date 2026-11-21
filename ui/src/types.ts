// The shapes the Python side returns (highlights/app/api.py and serialize.py).

export interface Check {
  name: string;
  state: "OK" | "WARN" | "FAIL";
  detail: string;
}

export interface Readiness {
  ready: boolean;
  warnings?: number;
  checks: Check[];
}

export interface Demo {
  path: string;
  name: string;
  folder: string;
  megabytes: number;
  modified: string; // ISO date and time, to the minute
  compressed?: boolean; // FACEIT .dem.zst / .dem.gz, unpacked when read
}

export interface DemoDescription {
  path: string;
  map: string;
  score: [number, number] | null; // the signed-in player's rounds first
  result: "W" | "L" | "T" | null;
}

export interface MatchInfo {
  path: string;
  file: string;
  map: string;
  gotv: boolean;
  rounds: number;
}

export interface Player {
  steamid: string;
  name: string;
  matches: number;
  kills: number;
  deaths: number;
  you: boolean; // the Steam account signed in on this PC
}

export interface Analysis {
  matches: MatchInfo[];
  players: Player[];
}

export interface Play {
  number: number;
  round: number;
  time: string; // mm:ss into the demo
  type: string;
  description: string;
  score: number;
  tags: string[];
  seconds: number;
  demo: string | null;
}

export interface Plan {
  moments: Play[];
  count: number;
  seconds: number;
  missing_from: string[];
}

export interface PlanOptions {
  seconds?: number;
  order?: "montage" | "chronological";
  types?: string;
  all?: boolean;
}

export interface RenderOptions extends PlanOptions {
  aspect?: string;
  music?: string | null;
  plain?: boolean;
  dry_run?: boolean;
  resume?: boolean;
}

export type JobState = "queued" | "running" | "done" | "failed" | "cancelled";

export interface RenderResult {
  video?: string;
  shape?: string;
  chapters?: string | null;
  thumbnail?: string | null;
  recorded: number; // clips; one play can be several clips
  plays?: number;
  failed: number;
}

export interface Job<Result = unknown> {
  id: string;
  title: string;
  state: JobState;
  stage: string;
  message: string;
  fraction: number;
  result: Result | null;
  error: string | null;
}

export interface Reel {
  path: string;
  player: string;
  made: string;
  megabytes: number;
  thumbnail: string | null;
  chapters: string | null;
}

export interface Settings {
  configured: boolean;
  output_dir?: string;
  clips_dir?: string;
  aspect?: string;
  hud?: string;
  recorder?: string;
  music?: string | null;
  music_start?: number;
  transition?: string;
  target_seconds?: number;
}
