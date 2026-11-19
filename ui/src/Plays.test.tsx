import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { useBridge } from "./api";
import { PlaysStep } from "./Plays";
import { installFakeBridge } from "./test/fakeBridge";
import type { Plan, PlanOptions } from "./types";

afterEach(() => useBridge(null));

const PLAN: Plan = {
  count: 2,
  seconds: 95,
  missing_from: [],
  moments: [
    { number: 1, round: 5, time: "08:08", type: "ace", description: "Ace (5 kills)", score: 30, tags: ["swung the round"], seconds: 26, demo: "a.dem" },
    { number: 2, round: 13, time: "19:33", type: "kill", description: "Killed ICECUBE (ak47 headshot)", score: 5, tags: [], seconds: 5, demo: "a.dem" },
  ],
};

function Harness({ onNext = () => {} }: { onNext?: () => void }) {
  const [options, setOptions] = useState<PlanOptions>({ seconds: 120, order: "montage" });
  return <PlaysStep paths={["a.dem"]} steamid="1" options={options} onOptions={setOptions} onBack={() => {}} onNext={onNext} />;
}

test("the planned plays are listed with a summary", async () => {
  installFakeBridge({ plan: async () => PLAN });
  render(<Harness />);
  expect(await screen.findByText("2 plays, about 1:35 of footage")).toBeInTheDocument();
  expect(screen.getByText("Ace")).toBeInTheDocument();
  expect(screen.getByText(/Round 5 · 08:08 · swung the round/)).toBeInTheDocument();
});

test("changing the length or order plans again with those options", async () => {
  const bridge = installFakeBridge({ plan: async () => PLAN });
  const plan = vi.spyOn(bridge, "plan");
  render(<Harness />);
  await screen.findByText("Ace");
  await userEvent.click(screen.getByRole("button", { name: "1 min" }));
  await vi.waitFor(() => expect(plan).toHaveBeenLastCalledWith(["a.dem"], "1", { seconds: 60, order: "montage", all: false }));
  await userEvent.click(screen.getByRole("button", { name: "Every play" }));
  await vi.waitFor(() => expect(plan.mock.lastCall?.[2]).toMatchObject({ all: true }));
  expect(screen.getByRole("button", { name: "Every play" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "Match order" }));
  await vi.waitFor(() => expect(plan.mock.lastCall?.[2]).toMatchObject({ order: "chronological" }));
});

test("no plays means nothing to make", async () => {
  installFakeBridge();
  render(<Harness />);
  expect(await screen.findByText("No plays found for this player.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make the reel" })).toBeDisabled();
});
