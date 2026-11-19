import { useBridge, type Bridge } from "../api";
import type { Readiness } from "../types";

export const READY: Readiness = {
  ready: true,
  warnings: 1,
  checks: [
    { name: "CS2 install", state: "OK", detail: "D:\\SteamLibrary\\cs2.exe" },
    { name: "HLAE", state: "WARN", detail: "v2.193.0 - released before the latest CS2 update" },
  ],
};

/** A bridge answering like the Python side; override what a test needs. */
export function installFakeBridge(overrides: Partial<Bridge> = {}): Bridge {
  const bridge: Bridge = {
    version: async () => ({ version: "0.1.0" }),
    check: async () => READY,
    setup: async () => ({ job: "setup" }),
    settings: async () => ({ configured: true }),
    save_settings: async () => ({ configured: true }),
    find_demos: async () => ({ demos: [] }),
    analyze: async () => ({ matches: [], players: [] }),
    plan: async () => ({ moments: [], count: 0, seconds: 0, missing_from: [] }),
    render: async () => ({ job: "render" }),
    job: async (id) => ({
      id, title: "", state: "done", stage: "", message: "", fraction: 1, result: null, error: null,
    }),
    cancel: async () => ({ cancelled: true }),
    reels: async () => ({ reels: [] }),
    show_in_folder: async (path) => ({ shown: path }),
    pick_demos: async () => ({ paths: [] }),
    pick_music: async () => ({ path: null }),
    pick_folder: async () => ({ path: null }),
    ...overrides,
  };
  useBridge(bridge);
  return bridge;
}
