import { useEffect, useState } from "react";
import { api } from "./api";
import { NewReel } from "./NewReel";
import { ReadinessPage, StatusButton } from "./Readiness";
import { ReelsPage } from "./Reels";
import { SettingsPage } from "./SettingsPage";
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
      {view === "ready" && <ReadinessPage onChanged={setReadiness} />}
      {/* Kept mounted so picks and a running render survive a look at other pages. */}
      <div className="page" hidden={view !== "new"}>
        <NewReel />
      </div>
      {view === "reels" && <ReelsPage />}
      {view === "settings" && <SettingsPage />}
    </Shell>
  );
}
