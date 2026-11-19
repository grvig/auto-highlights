import { useEffect, useState } from "react";
import { api } from "./api";
import { message, useAsync } from "./hooks";
import type { Settings } from "./types";

export const SHAPES = [
  { value: "stretched", label: "4:3 stretched to 16:9" },
  { value: "4:3", label: "4:3" },
  { value: "pillarbox", label: "4:3 with black bars" },
  { value: "16:9", label: "16:9 (cropped)" },
  { value: "vertical", label: "Vertical 9:16 (Shorts, TikTok)" },
];

// What the page edits, and the config key each one is saved under.
const KEYS = {
  output_dir: "paths.output_dir",
  aspect: "recording.aspect",
  hud: "recording.hud",
  recorder: "recording.recorder",
  target_seconds: "editing.target_seconds",
  music: "editing.music",
  music_start: "editing.music_start",
} as const;
type Field = keyof typeof KEYS;

export function SettingsPage() {
  const loaded = useAsync(() => api.settings(), []);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [note, setNote] = useState<{ kind: "ok" | "fail"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => setDraft(loaded.data), [loaded.data]);

  if (loaded.error) return <p className="notice fail">{loaded.error}</p>;
  if (!draft) return <p className="muted">Loading settings…</p>;
  if (!draft.configured) {
    return <p className="notice">Nothing is set up yet. Open the readiness page from the side bar and run setup.</p>;
  }

  const set = (field: Field, value: unknown) => {
    setNote(null);
    setDraft({ ...draft, [field]: value });
  };
  const changes = changed(loaded.data!, draft);

  const save = async () => {
    setSaving(true);
    try {
      const saved = await api.saveSettings(changes);
      setDraft(saved);
      loaded.reload();
      setNote({ kind: "ok", text: "Saved." });
    } catch (e) {
      setNote({ kind: "fail", text: message(e) });
    } finally {
      setSaving(false);
    }
  };

  const browse = async (pick: () => Promise<string | null>, field: Field) => {
    const chosen = await pick();
    if (chosen) set(field, chosen);
  };

  return (
    <section className="page">
      <header className="page-head">
        <h1>Settings</h1>
      </header>

      <div className="form">
        <label>
          <span>Reels are saved in</span>
          <span className="path-field">
            <input readOnly value={draft.output_dir ?? ""} aria-label="Output folder" />
            <button onClick={() => browse(api.pickFolder, "output_dir")}>Change…</button>
          </span>
        </label>

        <label>
          <span>Reel shape</span>
          <select value={draft.aspect} onChange={(e) => set("aspect", e.target.value)}>
            {SHAPES.map((shape) => (
              <option key={shape.value} value={shape.value}>
                {shape.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Usual reel length (seconds)</span>
          <input
            type="number"
            min={15}
            max={600}
            step={15}
            value={draft.target_seconds ?? 120}
            onChange={(e) => set("target_seconds", Number(e.target.value))}
          />
        </label>

        <label>
          <span>HUD while recording</span>
          <select value={draft.hud} onChange={(e) => set("hud", e.target.value)}>
            <option value="clean">Clean: crosshair and kill feed only</option>
            <option value="full">Full spectator HUD</option>
          </select>
        </label>

        <label>
          <span>Recorder</span>
          <select value={draft.recorder} onChange={(e) => set("recorder", e.target.value)}>
            <option value="hlae">HLAE (frame-perfect)</option>
            <option value="window">Window capture (when HLAE does not work)</option>
          </select>
        </label>

        <label>
          <span>Music (optional, your own file)</span>
          <span className="path-field">
            <input readOnly value={draft.music ?? ""} placeholder="No music: game sound only" aria-label="Music file" />
            <button onClick={() => browse(api.pickMusic, "music")}>Choose…</button>
            {draft.music && <button onClick={() => set("music", "")}>Remove</button>}
          </span>
        </label>

        {draft.music && (
          <label>
            <span>Start the music at (seconds into the track)</span>
            <input
              type="number"
              min={0}
              step={1}
              value={draft.music_start ?? 0}
              onChange={(e) => set("music_start", Number(e.target.value))}
            />
          </label>
        )}
      </div>

      {note && <p className={`notice ${note.kind === "fail" ? "fail" : ""}`}>{note.text}</p>}

      <footer className="page-foot">
        <button onClick={() => setDraft(loaded.data)} disabled={!Object.keys(changes).length || saving}>
          Undo changes
        </button>
        <button className="primary" onClick={save} disabled={!Object.keys(changes).length || saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </footer>
    </section>
  );
}

/** "section.key": value for every field that differs from what was loaded. */
export function changed(before: Settings, after: Settings): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of Object.keys(KEYS) as Field[]) {
    const old = before[field] ?? (field === "music" ? "" : undefined);
    const now = after[field] ?? (field === "music" ? "" : undefined);
    if (now !== old && now !== undefined) out[KEYS[field]] = now;
  }
  return out;
}
