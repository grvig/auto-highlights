import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { DemosStep } from "./Demos";
import { PlayerStep } from "./Player";
import { PlaysStep } from "./Plays";
import { RenderStep } from "./Render";
import { Tabs } from "./Shell";
import type { PlanOptions } from "./types";

type Step = "demos" | "player" | "plays" | "record";
const STEPS: { id: Step; label: string }[] = [
  { id: "demos", label: "Demos" },
  { id: "player", label: "Player" },
  { id: "plays", label: "Plays" },
  { id: "record", label: "Record" },
];
const ORDER: Step[] = STEPS.map((s) => s.id);
const DEFAULT_OPTIONS: PlanOptions = { seconds: 120, order: "montage" };

/** Demos, then whose plays, then which plays, then record. */
export function NewReel() {
  const [step, setStep] = useState<Step>("demos");
  const [reached, setReached] = useState(0);
  const [paths, setPaths] = useState<string[]>([]);
  const [player, setPlayer] = useState<{ steamid: string; name: string } | null>(null);
  const [options, setOptions] = useState<PlanOptions>(DEFAULT_OPTIONS);

  // Start from the length saved in settings, unless one was already chosen.
  useEffect(() => {
    let current = true;
    api.settings().then(
      (saved) => {
        if (current && saved.target_seconds) {
          setOptions((o) => (o === DEFAULT_OPTIONS ? { ...o, seconds: saved.target_seconds } : o));
        }
      },
      () => {},
    );
    return () => {
      current = false;
    };
  }, []);

  const go = (next: Step) => {
    setStep(next);
    setReached((r) => Math.max(r, ORDER.indexOf(next)));
  };
  const pickDemos = (next: string[]) => {
    setPaths(next);
    setPlayer(null); // other demos can have other players
    setReached(0);
  };
  const pickPlayer = useCallback((steamid: string, name: string) => {
    setPlayer((before) => {
      if (before && before.steamid !== steamid) setReached((r) => Math.min(r, 1));
      return { steamid, name };
    });
  }, []);

  return (
    <>
      <Tabs tabs={STEPS} current={step} onSelect={go} enabled={(id) => ORDER.indexOf(id) <= reached} />
      {step === "demos" && <DemosStep selected={paths} onChange={pickDemos} onNext={() => go("player")} />}
      {step === "player" && (
        <PlayerStep
          paths={paths}
          steamid={player?.steamid ?? null}
          onPick={pickPlayer}
          onBack={() => go("demos")}
          onNext={() => go("plays")}
        />
      )}
      {step === "plays" && player && (
        <PlaysStep
          paths={paths}
          steamid={player.steamid}
          options={options}
          onOptions={setOptions}
          onBack={() => go("player")}
          onNext={() => go("record")}
        />
      )}
      {step === "record" && player && (
        <RenderStep
          paths={paths}
          steamid={player.steamid}
          playerName={player.name}
          options={options}
          onBack={() => go("plays")}
          onAnother={() => {
            setPaths([]);
            setPlayer(null);
            setReached(0);
            setStep("demos");
          }}
        />
      )}
    </>
  );
}
