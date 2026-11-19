import { useState } from "react";
import { DemosStep } from "./Demos";

const STEPS = ["Demos", "Player", "Plays", "Make it"] as const;
type Step = 0 | 1 | 2 | 3;

/** The new-reel flow: demos, then whose plays, then which plays, then render. */
export function NewReel() {
  const [step, setStep] = useState<Step>(0);
  const [paths, setPaths] = useState<string[]>([]);

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
      {step === 0 && <DemosStep selected={paths} onChange={setPaths} onNext={() => setStep(1)} />}
      {step > 0 && <p className="muted">{paths.length} demos picked.</p>}
    </div>
  );
}
