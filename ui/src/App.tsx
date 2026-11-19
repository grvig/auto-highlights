import { useEffect, useState } from "react";
import { api } from "./api";
import { ReadinessPage, StatusButton } from "./Readiness";
import { Shell, type View } from "./Shell";
import type { Readiness } from "./types";

export function App() {
  const [view, setView] = useState<View>("new");
  const [readiness, setReadiness] = useState<Readiness | null>(null);

  useEffect(() => {
    api.check().then(setReadiness, () => setReadiness({ ready: false, checks: [] }));
  }, []);

  return (
    <Shell
      view={view}
      onNavigate={setView}
      status={<StatusButton readiness={readiness} onOpen={() => setView("ready")} />}
    >
      {view === "ready" ? <ReadinessPage onChanged={setReadiness} /> : <h1>{TITLES[view]}</h1>}
    </Shell>
  );
}

const TITLES: Record<View, string> = {
  new: "New reel",
  reels: "Your reels",
  settings: "Settings",
  ready: "Recording readiness",
};
