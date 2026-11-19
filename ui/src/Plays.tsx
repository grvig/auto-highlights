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
  { label: "Every play", seconds: 0 },
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
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Your plays</h1>
          <p className="muted">{plan.data ? summary(plan.data) : "Finding your best plays…"}</p>
        </div>
      </header>

      <div className="options">
        <div className="choice" role="group" aria-label="Length">
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
        </div>
        <div className="choice" role="group" aria-label="Order">
          <button aria-pressed={options.order !== "chronological"} onClick={() => onOptions({ ...options, order: "montage" })}>
            Best last
          </button>
          <button aria-pressed={options.order === "chronological"} onClick={() => onOptions({ ...options, order: "chronological" })}>
            Match order
          </button>
        </div>
      </div>

      {plan.error && <p className="notice fail">{plan.error}</p>}
      {plan.data?.missing_from.length ? (
        <p className="notice warn">Not in: {plan.data.missing_from.join(", ")}. Those demos add nothing.</p>
      ) : null}
      {plan.data && plan.data.count === 0 && <p className="notice">No plays found for this player.</p>}

      <ol className="plays" aria-label="Plays" aria-busy={plan.loading}>
        {plan.data?.moments.map((play) => (
          <li key={play.number}>
            <span className="kind">{TYPE_LABELS[play.type] ?? play.type}</span>
            <span className="grow">
              <strong>{play.description}</strong>
              <span className="muted small">
                Round {play.round} · {play.time}
                {play.demo && paths.length > 1 ? ` · ${play.demo}` : ""}
                {play.tags.length ? ` · ${play.tags.join(", ")}` : ""}
              </span>
            </span>
            <span className="muted num">{play.seconds.toFixed(0)}s</span>
          </li>
        ))}
      </ol>

      <footer className="page-foot">
        <button onClick={onBack}>Back</button>
        <button className="primary" disabled={!plan.data?.count || plan.loading} onClick={onNext}>
          Make the reel
        </button>
      </footer>
    </section>
  );
}

function summary(plan: Plan): string {
  const minutes = Math.floor(plan.seconds / 60);
  const seconds = Math.round(plan.seconds % 60);
  const length = minutes ? `${minutes}:${String(seconds).padStart(2, "0")}` : `${seconds}s`;
  return `${plan.count} ${plan.count === 1 ? "play" : "plays"}, about ${length} of footage`;
}
