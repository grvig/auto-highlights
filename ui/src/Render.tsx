import { useState } from "react";
import { api } from "./api";
import { message, useJob } from "./hooks";
import type { PlanOptions, RenderResult } from "./types";

interface Props {
  paths: string[];
  steamid: string;
  playerName: string;
  options: PlanOptions;
  onBack: () => void;
  onAnother: () => void;
}

const STAGES: Record<string, string> = {
  record: "Recording",
  edit: "Editing",
  export: "Exporting",
};

export function RenderStep({ paths, steamid, playerName, options, onBack, onAnother }: Props) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const job = useJob<RenderResult>(jobId);

  const start = async () => {
    setStartError(null);
    setStopping(false);
    try {
      setJobId(await api.render(paths, steamid, options));
    } catch (e) {
      setStartError(message(e));
    }
  };

  const stop = async () => {
    if (jobId && (await api.cancel(jobId))) setStopping(true);
  };

  const running = jobId !== null && (!job || job.state === "queued" || job.state === "running");

  if (job?.state === "done" && job.result) {
    return <Finished result={job.result} onAnother={onAnother} />;
  }

  const percent = Math.round((job?.fraction ?? 0) * 100);
  return (
    <>
      <div className="toolbar">
        <button onClick={onBack} disabled={running}>
          Back
        </button>
        {running ? (
          <button onClick={stop} disabled={stopping}>
            Stop
          </button>
        ) : (
          <button className="primary" onClick={start}>
            {job ? "Try again" : "Record"}
          </button>
        )}
        <span className="spacer" />
        <span className="muted">{playerName}</span>
      </div>
      <div className="body">
        {startError && <p className="error">{startError}</p>}
        {job?.state === "failed" && (
          <p className="error">
            {job.error}
            <button onClick={() => api.openLogs().catch(() => {})}>Open logs</button>
          </p>
        )}
        {job?.state === "cancelled" && <p className="error warn">Stopped</p>}
        {!running && !job && <p className="empty">CS2 is used for recording until this finishes.</p>}
        {running && (
          <>
            <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
              <div style={{ width: `${percent}%` }} />
            </div>
            <div className="status-line">
              <span>
                {stopping ? "Stopping after the current clip…" : STAGES[job?.stage ?? ""] ?? "Starting…"}
                <span className="muted"> {job?.message}</span>
              </span>
              <span className="muted">{percent}%</span>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function Finished({ result, onAnother }: { result: RenderResult; onAnother: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const run = (action: (video: string) => Promise<unknown>) => async () => {
    setError(null);
    try {
      if (result.video) await action(result.video);
    } catch (e) {
      setError(message(e));
    }
  };
  const plays = result.plays ?? result.recorded;
  return (
    <>
      <div className="toolbar">
        <button className="primary" onClick={run(api.play)} disabled={!result.video}>
          Play
        </button>
        <button onClick={run(api.showInFolder)} disabled={!result.video}>
          Show in folder
        </button>
        <button onClick={onAnother}>New reel</button>
      </div>
      <div className="body">
        {error && <p className="error">{error}</p>}
        <table className="grid details">
          <tbody>
            <tr>
              <td className="muted">File</td>
              <td className="wide">{fileName(result.video ?? "")}</td>
            </tr>
            <tr>
              <td className="muted">Plays</td>
              <td className="wide">
                {plays}
                {result.failed ? <span className="muted"> ({result.failed} clips failed)</span> : null}
              </td>
            </tr>
            {result.shape && (
              <tr>
                <td className="muted">Shape</td>
                <td className="wide">{result.shape}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function fileName(path: string): string {
  return path.slice(Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/")) + 1);
}
