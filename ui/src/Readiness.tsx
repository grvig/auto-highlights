import { useState } from "react";
import { api } from "./api";
import { message, useAsync, useJob } from "./hooks";
import { Tabs } from "./Shell";
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

/** The rail's status square; opens the checks. */
export function StatusButton({ readiness, onOpen }: { readiness: Readiness | null; onOpen: () => void }) {
  const current = level(readiness);
  const label = current ? LABELS[current] : "Checking";
  return (
    <button onClick={onOpen} title={label} aria-label={label}>
      <span className={`dot ${current ?? ""}`} aria-hidden />
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
    <>
      <Tabs tabs={[{ id: "checks", label: "Recording" }]} current="checks" onSelect={() => {}} />
      <div className="toolbar">
        <button className="primary" onClick={runSetup} disabled={jobId !== null}>
          {jobId ? "Setting up…" : "Download missing tools"}
        </button>
        <button onClick={checks.reload} disabled={jobId !== null}>
          Check again
        </button>
        <span className="spacer" />
        {job && <span className="muted">{job.message}</span>}
      </div>
      <div className="body">
        {(error || checks.error) && <p className="error">{error ?? checks.error}</p>}
        <table className="grid">
          <tbody>
            {checks.data?.checks.map((check) => (
              <tr key={check.name}>
                <td className="check">
                  <span className={`dot ${MARKS[check.state]}`} aria-label={check.state} />
                </td>
                <td>{check.name}</td>
                <td className="wide muted">{check.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
