import { useState } from "react";
import { api } from "./api";
import { message, useAsync } from "./hooks";
import type { Demo } from "./types";

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
  const extra = browsed.filter((path) => !known.has(path));

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
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Pick your demos</h1>
          <p className="muted">
            From CS2's replays folder and your Downloads, newest first. Several demos make one reel.
          </p>
        </div>
        <button onClick={browse}>Browse…</button>
      </header>
      {(error || found.error) && <p className="notice fail">{error ?? found.error}</p>}
      {found.loading && <p className="muted">Looking for demos…</p>}
      {!found.loading && !found.data?.length && !extra.length && (
        <p className="notice">No demos found. Download one from CS2's Watch tab, or browse for it.</p>
      )}
      <ul className="rows" aria-label="Demos">
        {extra.map((path) => (
          <DemoRow key={path} demo={browsedDemo(path)} checked={selected.includes(path)} onToggle={toggle} />
        ))}
        {found.data?.map((demo) => (
          <DemoRow key={demo.path} demo={demo} checked={selected.includes(demo.path)} onToggle={toggle} />
        ))}
      </ul>
      <footer className="page-foot">
        <span className="muted">{countLabel(selected.length)}</span>
        <button className="primary" disabled={!selected.length} onClick={onNext}>
          Read demos
        </button>
      </footer>
    </section>
  );
}

function DemoRow({ demo, checked, onToggle }: { demo: Demo; checked: boolean; onToggle: (p: string) => void }) {
  return (
    <li>
      <label className="row">
        <input type="checkbox" checked={checked} onChange={() => onToggle(demo.path)} />
        <span className="grow">
          <strong>{demo.name}</strong>
          <span className="muted small">{demo.folder}</span>
        </span>
        <span className="muted">{demo.modified ? formatWhen(demo.modified) : ""}</span>
        <span className="muted">{demo.megabytes ? `${demo.megabytes} MB` : ""}</span>
      </label>
    </li>
  );
}

function browsedDemo(path: string): Demo {
  const cut = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return { path, name: path.slice(cut + 1), folder: path.slice(0, cut), megabytes: 0, modified: "" };
}

export function formatWhen(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  return when.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function countLabel(count: number): string {
  if (count === 0) return "No demos picked";
  return count === 1 ? "1 demo picked" : `${count} demos picked`;
}
