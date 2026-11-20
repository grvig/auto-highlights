import { api } from "./api";
import { useAsync } from "./hooks";
import type { Plan, PlanOptions } from "./types";

interface Props {
  paths: string[];
  steamid: string;
  options: PlanOptions;
  onOptions: (options: PlanOptions) => void;
  onBack: () => void;
  onNext: () => void;
}

export const LENGTHS = [
  { label: "1 min", seconds: 60 },
  { label: "2 min", seconds: 120 },
  { label: "3 min", seconds: 180 },
  { label: "All", seconds: 0 },
];

const TYPE_LABELS: Record<string, string> = {
  kill: "Kill",
  multi_kill: "Multi-kill",
  ace: "Ace",
  clutch: "Clutch",
  death: "Death",
  utility: "Utility",
};

export function PlaysStep({ paths, steamid, options, onOptions, onBack, onNext }: Props) {
  const plan = useAsync<Plan>(
    () => api.plan(paths, steamid, options),
    [paths.join("|"), steamid, options.seconds, options.all, options.order],
  );
  const length = options.all ? 0 : options.seconds ?? 120;

  return (
    <>
      <div className="toolbar">
        <button onClick={onBack}>Back</button>
        <button className="primary" disabled={!plan.data?.count || plan.loading} onClick={onNext}>
          Next
        </button>
        <span className="segmented" role="group" aria-label="Length">
          {LENGTHS.map((choice) => (
            <button
              key={choice.label}
              aria-pressed={length === choice.seconds}
              onClick={() =>
                onOptions(choice.seconds ? { ...options, seconds: choice.seconds, all: false } : { ...options, all: true })
              }
            >
              {choice.label}
            </button>
          ))}
        </span>
        <span className="segmented" role="group" aria-label="Order">
          <button aria-pressed={options.order !== "chronological"} onClick={() => onOptions({ ...options, order: "montage" })}>
            Best last
          </button>
          <button aria-pressed={options.order === "chronological"} onClick={() => onOptions({ ...options, order: "chronological" })}>
            Match order
          </button>
        </span>
        <span className="spacer" />
        {plan.data && <span className="muted">{summary(plan.data)}</span>}
      </div>
      <div className="body">
        {plan.error && <p className="error">{plan.error}</p>}
        {plan.data?.missing_from.length ? (
          <p className="error warn">Not in {plan.data.missing_from.join(", ")}</p>
        ) : null}
        {plan.loading && !plan.data && <p className="empty">Finding plays…</p>}
        {plan.data && plan.data.count === 0 && <p className="empty">No plays</p>}
        {plan.data && plan.data.count > 0 && (
          <table className="grid" aria-label="Plays" aria-busy={plan.loading}>
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Type</th>
                <th>Play</th>
                <th className="num">Round</th>
                <th className="num">Time</th>
                {paths.length > 1 && <th>Demo</th>}
                <th className="num">Length</th>
              </tr>
            </thead>
            <tbody>
              {plan.data.moments.map((play) => (
                <tr key={play.number}>
                  <td className="num muted">{play.number}</td>
                  <td className="type">{TYPE_LABELS[play.type] ?? play.type}</td>
                  <td className="wide">
                    {play.description}
                    {play.tags.length > 0 && <span className="muted"> · {play.tags.join(", ")}</span>}
                  </td>
                  <td className="num">{play.round}</td>
                  <td className="num">{play.time}</td>
                  {paths.length > 1 && <td className="muted">{play.demo}</td>}
                  <td className="num">{play.seconds.toFixed(0)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function summary(plan: Plan): string {
  const minutes = Math.floor(plan.seconds / 60);
  const seconds = Math.round(plan.seconds % 60);
  return `${plan.count} ${plan.count === 1 ? "play" : "plays"} · ${minutes}:${String(seconds).padStart(2, "0")}`;
}
