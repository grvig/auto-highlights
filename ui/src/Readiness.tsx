import { useState } from "react";
import { api } from "./api";
import { message, useAsync, useJob } from "./hooks";
import type { Check, Readiness } from "./types";

type Level = "ok" | "warn" | "fail";

export function level(readiness: Readiness | null): Level | null {
  if (!readiness) return null;
  if (!readiness.ready) return "fail";
  return readiness.warnings ? "warn" : "ok";
}

const LABELS: Record<Level, string> = {
  ok: "Ready to record",
  warn: "Ready, with warnings",
  fail: "Not ready to record",
};

/** The side bar's one-line summary; opens the full list. */
export function StatusButton({ readiness, onOpen }: { readiness: Readiness | null; onOpen: () => void }) {
  const current = level(readiness);
  return (
    <button onClick={onOpen}>
      <span className={`dot ${current ?? ""}`} aria-hidden />
      {current ? LABELS[current] : "Checking…"}
    </button>
  );
}

const MARKS: Record<Check["state"], Level> = { OK: "ok", WARN: "warn", FAIL: "fail" };

export function ReadinessPage({ onChanged }: { onChanged: (r: Readiness) => void }) {
  const checks = useAsync(async () => {
    const answer = await api.check();
    onChanged(answer);
    return answer;
  }, []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const job = useJob(jobId, (finished) => {
    if (finished.state === "failed") setError(finished.error);
    setJobId(null);
    checks.reload();
  });

  const runSetup = async () => {
    setError(null);
    try {
      setJobId(await api.setup());
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <section className="page">
      <header className="page-head">
        <h1>Recording readiness</h1>
        <button className="primary" onClick={runSetup} disabled={jobId !== null}>
          {jobId ? "Setting up…" : "Set up missing tools"}
        </button>
      </header>
      <p className="muted">
        What recording needs: CS2, ffmpeg and HLAE. Setup finds them or downloads them; checking
        launches nothing.
      </p>
      {job && <p className="muted">{job.message || "Working…"}</p>}
      {(error || checks.error) && <p className="notice fail">{error ?? checks.error}</p>}
      <ul className="checks">
        {checks.data?.checks.map((check) => (
          <li key={check.name}>
            <span className={`dot ${MARKS[check.state]}`} aria-label={check.state} />
            <strong>{check.name}</strong>
            <span className="muted">{check.detail}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
