import { useState } from "react";
import { Shell, type View } from "./Shell";

export function App() {
  const [view, setView] = useState<View>("new");
  return (
    <Shell view={view} onNavigate={setView} status={null}>
      <h1>{TITLES[view]}</h1>
    </Shell>
  );
}

const TITLES: Record<View, string> = {
  new: "New reel",
  reels: "Your reels",
  settings: "Settings",
  ready: "Recording readiness",
};
