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
  record: "Recording in CS2",
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

  return (
    <section className="page">
      <header className="page-head">
        <h1>{running ? "Making your reel" : `Make ${playerName}'s reel`}</h1>
      </header>

      {!running && (
        <p className="notice">
          CS2 opens and plays your demos while each play is recorded, so leave the PC alone until it
          is done. Your CS2 settings are put back afterwards.
        </p>
      )}

      {running && (
        <div className="progress-block">
          <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((job?.fraction ?? 0) * 100)}>
            <div style={{ width: `${(job?.fraction ?? 0) * 100}%` }} />
          </div>
          <p>
            <strong>{stopping ? "Stopping after the current clip…" : STAGES[job?.stage ?? ""] ?? "Starting…"}</strong>
            <span className="muted"> {job?.message}</span>
          </p>
        </div>
      )}

      {startError && <p className="notice fail">{startError}</p>}
      {job?.state === "failed" && (
        <div className="notice fail">
          <p>The reel could not be made: {job.error}</p>
          <button onClick={() => api.openLogs().catch(() => {})}>Open logs folder</button>
        </div>
      )}
      {job?.state === "cancelled" && <p className="notice">Stopped. Nothing was left running.</p>}

      <footer className="page-foot">
        <button onClick={onBack} disabled={running}>
          Back
        </button>
        {running ? (
          <button onClick={stop} disabled={stopping}>
            Stop
          </button>
        ) : (
          <button className="primary" onClick={start}>
            {job ? "Try again" : "Record and make the reel"}
          </button>
        )}
      </footer>
    </section>
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
  const show = run(api.showInFolder);
  const play = run(api.play);
  return (
    <section className="page">
      <header className="page-head">
        <h1>Your reel is ready</h1>
      </header>
      <p className="notice">
        <strong>{fileName(result.video ?? "")}</strong>
        <br />
        <span className="muted">
          {result.recorded} {result.recorded === 1 ? "play" : "plays"}
          {result.failed ? `, ${result.failed} could not be recorded` : ""}
          {result.shape ? ` · ${result.shape}` : ""}
        </span>
      </p>
      {error && <p className="notice fail">{error}</p>}
      <footer className="page-foot">
        <button onClick={onAnother}>Make another</button>
        <span className="buttons">
          <button onClick={show} disabled={!result.video}>
            Show in folder
          </button>
          <button className="primary" onClick={play} disabled={!result.video}>
            Play
          </button>
        </span>
      </footer>
    </section>
  );
}

export function fileName(path: string): string {
  return path.slice(Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/")) + 1);
}
