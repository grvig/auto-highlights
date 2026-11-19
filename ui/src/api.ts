// Calls into Python through pywebview's bridge (highlights/app/window.py).
//
// Python answers problems with {"error": "..."} instead of raising; here
// those become ApiFailure so a screen can show the message in one place.

import type {
  Analysis, Demo, Job, Plan, PlanOptions, Readiness, Reel, RenderOptions, RenderResult, Settings,
} from "./types";

export interface Bridge {
  version(): Promise<{ version: string }>;
  check(): Promise<Readiness | Failed>;
  setup(): Promise<{ job: string } | Failed>;
  settings(): Promise<Settings>;
  save_settings(changes: Record<string, unknown>): Promise<Settings | Failed>;
  find_demos(): Promise<{ demos: Demo[] }>;
  analyze(paths: string[]): Promise<Analysis | Failed>;
  plan(paths: string[], steamid: string, options?: PlanOptions): Promise<Plan | Failed>;
  render(paths: string[], steamid: string, options?: RenderOptions): Promise<{ job: string } | Failed>;
  job(id: string): Promise<Job | Failed>;
  cancel(id: string): Promise<{ cancelled: boolean }>;
  reels(): Promise<{ reels: Reel[] }>;
  show_in_folder(path: string): Promise<{ shown: string } | Failed>;
  pick_demos(): Promise<{ paths: string[] }>;
  pick_music(): Promise<{ path: string | null }>;
  pick_folder(): Promise<{ path: string | null }>;
}

interface Failed {
  error: string;
}

declare global {
  interface Window {
    pywebview?: { api: Bridge };
  }
}

export class ApiFailure extends Error {}

let override: Bridge | null = null;

/** Use a stand-in bridge (tests, or working on the UI in a plain browser). */
export function useBridge(bridge: Bridge | null): void {
  override = bridge;
}

/** pywebview injects its api after the page loads and says so with an event. */
export function bridge(timeoutMs = 10000): Promise<Bridge> {
  if (override) return Promise.resolve(override);
  if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(
      () => reject(new ApiFailure("The app's Python side did not answer. Restart the app.")),
      timeoutMs,
    );
    window.addEventListener(
      "pywebviewready",
      () => {
        window.clearTimeout(timer);
        resolve(window.pywebview!.api);
      },
      { once: true },
    );
  });
}

function unwrap<T>(answer: T | Failed): T {
  if (answer && typeof answer === "object" && "error" in answer && typeof answer.error === "string") {
    throw new ApiFailure(answer.error);
  }
  return answer as T;
}

export const api = {
  version: async () => (await (await bridge()).version()).version,
  check: async () => unwrap(await (await bridge()).check()),
  setup: async () => unwrap(await (await bridge()).setup()).job,
  settings: async () => (await bridge()).settings(),
  saveSettings: async (changes: Record<string, unknown>) =>
    unwrap(await (await bridge()).save_settings(changes)),
  findDemos: async () => (await (await bridge()).find_demos()).demos,
  analyze: async (paths: string[]) => unwrap(await (await bridge()).analyze(paths)),
  plan: async (paths: string[], steamid: string, options?: PlanOptions) =>
    unwrap(await (await bridge()).plan(paths, steamid, options)),
  render: async (paths: string[], steamid: string, options?: RenderOptions) =>
    unwrap(await (await bridge()).render(paths, steamid, options)).job,
  job: async (id: string) => unwrap(await (await bridge()).job(id)) as Job<RenderResult>,
  cancel: async (id: string) => (await (await bridge()).cancel(id)).cancelled,
  reels: async () => (await (await bridge()).reels()).reels,
  showInFolder: async (path: string) => unwrap(await (await bridge()).show_in_folder(path)),
  pickDemos: async () => (await (await bridge()).pick_demos()).paths,
  pickMusic: async () => (await (await bridge()).pick_music()).path,
  pickFolder: async () => (await (await bridge()).pick_folder()).path,
};
