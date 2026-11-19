import { useCallback, useState } from "react";
import { DemosStep } from "./Demos";
import { PlayerStep } from "./Player";
import { PlaysStep } from "./Plays";
import type { PlanOptions } from "./types";

const STEPS = ["Demos", "Player", "Plays", "Make it"] as const;
type Step = 0 | 1 | 2 | 3;

/** The new-reel flow: demos, then whose plays, then which plays, then render. */
export function NewReel() {
  const [step, setStep] = useState<Step>(0);
  const [paths, setPaths] = useState<string[]>([]);
  const [player, setPlayer] = useState<{ steamid: string; name: string } | null>(null);
  const [options, setOptions] = useState<PlanOptions>({ seconds: 120, order: "montage" });

  const pickDemos = (next: string[]) => {
    setPaths(next);
    setPlayer(null); // another set of demos can have other players
  };
  const pickPlayer = useCallback((steamid: string, name: string) => setPlayer({ steamid, name }), []);

  return (
    <div className="flow">
      <ol className="steps" aria-label="Steps">
        {STEPS.map((label, index) => (
          <li key={label} aria-current={index === step ? "step" : undefined} className={index < step ? "done" : ""}>
            <span>{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      {step === 0 && <DemosStep selected={paths} onChange={pickDemos} onNext={() => setStep(1)} />}
      {step === 1 && (
        <PlayerStep
          paths={paths}
          steamid={player?.steamid ?? null}
          onPick={pickPlayer}
          onBack={() => setStep(0)}
          onNext={() => setStep(2)}
        />
      )}
      {step === 2 && player && (
        <PlaysStep
          paths={paths}
          steamid={player.steamid}
          options={options}
          onOptions={setOptions}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      )}
      {step === 3 && <p className="muted">{player?.name}</p>}
    </div>
  );
}
