import { useEffect, useState } from "react";
import { api } from "./api";
import { message, useAsync } from "./hooks";
import { Tabs } from "./Shell";
import type { Settings } from "./types";

export const SHAPES = [
  { value: "stretched", label: "4:3 stretched to 16:9" },
  { value: "4:3", label: "4:3" },
  { value: "pillarbox", label: "4:3 with black bars" },
  { value: "16:9", label: "16:9 (cropped)" },
  { value: "vertical", label: "9:16 vertical" },
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

  const changes = loaded.data && draft ? changed(loaded.data, draft) : {};
  const dirty = Object.keys(changes).length > 0;

  const set = (field: Field, value: unknown) => {
    setNote(null);
    if (draft) setDraft({ ...draft, [field]: value });
  };

  const save = async () => {
    setSaving(true);
    try {
      setDraft(await api.saveSettings(changes));
      loaded.reload();
      setNote({ kind: "ok", text: "Saved" });
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
    <>
      <Tabs tabs={[{ id: "settings", label: "Settings" }]} current="settings" onSelect={() => {}} />
      <div className="toolbar">
        <button className="primary" onClick={save} disabled={!dirty || saving}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button onClick={() => setDraft(loaded.data)} disabled={!dirty || saving}>
          Undo
        </button>
        <span className="spacer" />
        {note && <span className={note.kind === "fail" ? "fail-text" : "muted"}>{note.text}</span>}
      </div>
      <div className="body">
        {loaded.error && <p className="error">{loaded.error}</p>}
        {draft && !draft.configured && <p className="empty">Not set up yet. Run setup from the status light.</p>}
        {draft?.configured && (
          <div className="form">
            <span>Output folder</span>
            <span className="path-field">
              <input readOnly value={draft.output_dir ?? ""} aria-label="Output folder" />
              <button onClick={() => browse(api.pickFolder, "output_dir")}>Change…</button>
            </span>

            <span>Reel shape</span>
            <select aria-label="Reel shape" value={draft.aspect} onChange={(e) => set("aspect", e.target.value)}>
              {SHAPES.map((shape) => (
                <option key={shape.value} value={shape.value}>
                  {shape.label}
                </option>
              ))}
            </select>

            <span>Default length (s)</span>
            <input
              type="number"
              aria-label="Default length"
              min={15}
              max={600}
              step={15}
              value={draft.target_seconds ?? 120}
              onChange={(e) => set("target_seconds", Number(e.target.value))}
            />

            <span>HUD</span>
            <select aria-label="HUD" value={draft.hud} onChange={(e) => set("hud", e.target.value)}>
              <option value="clean">Kill feed only</option>
              <option value="full">Full spectator HUD</option>
            </select>

            <span>Recorder</span>
            <select aria-label="Recorder" value={draft.recorder} onChange={(e) => set("recorder", e.target.value)}>
              <option value="hlae">HLAE</option>
              <option value="window">Window capture</option>
            </select>

            <span>Music</span>
            <span className="path-field">
              <input readOnly value={draft.music ?? ""} placeholder="None" aria-label="Music file" />
              <button onClick={() => browse(api.pickMusic, "music")}>Choose…</button>
              {draft.music && <button onClick={() => set("music", "")}>Remove</button>}
            </span>

            {draft.music && (
              <>
                <span>Music starts at (s)</span>
                <input
                  type="number"
                  aria-label="Music start"
                  min={0}
                  step={1}
                  value={draft.music_start ?? 0}
                  onChange={(e) => set("music_start", Number(e.target.value))}
                />
              </>
            )}
          </div>
        )}
      </div>
    </>
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
