import { useEffect, useState } from "react";
import { api } from "./api";
import { message, useAsync } from "./hooks";
import type { Demo, DemoDescription } from "./types";

interface Props {
  selected: string[];
  onChange: (paths: string[]) => void;
  onNext: () => void;
}

export function DemosStep({ selected, onChange, onNext }: Props) {
  const found = useAsync(() => api.findDemos(), []);
  const [browsed, setBrowsed] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const known = new Set((found.data ?? []).map((d) => d.path));
  const rows = [...browsed.filter((path) => !known.has(path)).map(browsedDemo), ...(found.data ?? [])];
  const descriptions = useDescriptions(rows.map((d) => d.path));

  const toggle = (path: string) =>
    onChange(selected.includes(path) ? selected.filter((p) => p !== path) : [...selected, path]);

  const browse = async () => {
    setError(null);
    try {
      const picked = await api.pickDemos();
      setBrowsed((before) => [...before, ...picked.filter((p) => !before.includes(p))]);
      onChange([...selected, ...picked.filter((p) => !selected.includes(p))]);
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <>
      <div className="toolbar">
        <button className="primary" disabled={!selected.length} onClick={onNext}>
          Next
        </button>
        <button onClick={browse}>Browse…</button>
        <button onClick={found.reload}>Refresh</button>
        <span className="spacer" />
        <span className="muted">{selected.length} selected</span>
      </div>
      <div className="body">
        {(error || found.error) && <p className="error">{error ?? found.error}</p>}
        {found.loading && !rows.length && <p className="empty">Searching…</p>}
        {!found.loading && !rows.length && <p className="empty">No demos found</p>}
        {rows.length > 0 && (
          <table className="grid" aria-label="Demos">
            <thead>
              <tr>
                <th />
                <th>Match</th>
                <th>Date</th>
                <th className="num">Size</th>
                <th>File</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((demo) => {
                const checked = selected.includes(demo.path);
                return (
                  <tr key={demo.path} className={`clickable${checked ? " selected" : ""}`} onClick={() => toggle(demo.path)}>
                    <td className="check">
                      <input
                        type="checkbox"
                        aria-label={demo.name}
                        checked={checked}
                        onChange={() => toggle(demo.path)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                    <td>
                      <MatchName description={descriptions[demo.path]} />
                      {(demo.compressed ?? /\.dem\.(zst|gz)$/i.test(demo.name)) && <span className="tag">packed</span>}
                    </td>
                    <td>{demo.modified ? formatWhen(demo.modified) : ""}</td>
                    <td className="num">{demo.megabytes ? `${demo.megabytes} MB` : ""}</td>
                    <td className="wide muted" title={demo.path}>
                      {demo.name}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

/** Reads each demo's map and score one at a time (about two seconds each,
 * then remembered by the app), filling the list in as they arrive. */
function useDescriptions(paths: string[]): Record<string, DemoDescription | "unknown"> {
  const [found, setFound] = useState<Record<string, DemoDescription | "unknown">>({});
  const key = paths.join("|");
  useEffect(() => {
    let current = true;
    (async () => {
      for (const path of paths) {
        if (!current) return;
        let answer: DemoDescription | "unknown";
        try {
          answer = await api.describeDemo(path);
        } catch {
          answer = "unknown";
        }
        if (current) setFound((before) => ({ ...before, [path]: answer }));
      }
    })();
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return found;
}

export function MatchName({ description }: { description: DemoDescription | "unknown" | undefined }) {
  if (description === undefined) return <span className="muted">Reading…</span>;
  if (description === "unknown") return <span className="muted">Unknown match</span>;
  return (
    <span>
      {description.map}
      {description.score && (
        <>
          {" "}
          <span className="score">
            {description.score[0]}–{description.score[1]}
          </span>{" "}
          <span className={`result ${description.result ?? ""}`}>{description.result}</span>
        </>
      )}
    </span>
  );
}

function browsedDemo(path: string): Demo {
  const cut = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return { path, name: path.slice(cut + 1), folder: path.slice(0, cut), megabytes: 0, modified: "" };
}

export function formatWhen(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  return when.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
