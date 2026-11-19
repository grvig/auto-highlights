import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Job } from "./types";

export interface Loaded<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Run an async load when deps change; the latest answer wins. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  const [round, setRound] = useState(0);
  const run = useCallback(load, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let current = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    run().then(
      (data) => current && setState({ data, error: null, loading: false }),
      (error: unknown) => current && setState({ data: null, error: message(error), loading: false }),
    );
    return () => {
      current = false;
    };
  }, [run, round]);

  return { ...state, reload: () => setRound((r) => r + 1) };
}

export const POLL_MS = 500;
const ENDED = new Set(["done", "failed", "cancelled"]);

export function ended(job: Job | null): boolean {
  return job !== null && ENDED.has(job.state);
}

/** Follow a background job until it ends. */
export function useJob<R = unknown>(id: string | null, onEnd?: (job: Job<R>) => void): Job<R> | null {
  const [job, setJob] = useState<Job<R> | null>(null);
  const endRef = useRef(onEnd);
  endRef.current = onEnd;

  useEffect(() => {
    setJob(null);
    if (!id) return;
    let stopped = false;
    let timer = 0;
    const poll = async () => {
      let latest: Job<R>;
      try {
        latest = (await api.job(id)) as unknown as Job<R>;
      } catch (error) {
        latest = {
          id, title: "", state: "failed", stage: "", message: "", fraction: 0, result: null,
          error: message(error),
        };
      }
      if (stopped) return;
      setJob(latest);
      if (ENDED.has(latest.state)) endRef.current?.(latest);
      else timer = window.setTimeout(poll, POLL_MS);
    };
    poll();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [id]);

  return job;
}

export function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
