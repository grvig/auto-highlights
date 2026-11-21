import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { PlayerStep } from "./Player";
import { installFakeBridge } from "./test/fakeBridge";
import type { Analysis } from "./types";

afterEach(() => useBridge(null));

const ANALYSIS: Analysis = {
  matches: [{ path: "a.dem", file: "a.dem", map: "Nuke", gotv: false, rounds: 24 }],
  players: [
    { steamid: "1", name: "semi", matches: 1, kills: 27, deaths: 14, you: true },
    { steamid: "2", name: "ICECUBE", matches: 1, kills: 19, deaths: 20, you: false },
  ],
};

function setup(steamid: string | null = null) {
  const onPick = vi.fn();
  const onNext = vi.fn();
  render(<PlayerStep paths={["a.dem"]} steamid={steamid} onPick={onPick} onBack={() => {}} onNext={onNext} />);
  return { onPick, onNext };
}

test("players are listed with the map and the signed-in player is picked", async () => {
  installFakeBridge({ analyze: async () => ANALYSIS });
  const { onPick } = setup();
  expect(await screen.findByText("Nuke · 24 rounds")).toBeInTheDocument();
  expect(screen.getByText("YOU")).toBeInTheDocument();
  expect(onPick).toHaveBeenCalledWith("1", "semi");
});

test("another player can be chosen", async () => {
  installFakeBridge({ analyze: async () => ANALYSIS });
  const { onPick, onNext } = setup("1");
  await userEvent.click(await screen.findByRole("radio", { name: "ICECUBE" }));
  expect(onPick).toHaveBeenLastCalledWith("2", "ICECUBE");
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(onNext).toHaveBeenCalled();
});

test("a demo that cannot be read says why", async () => {
  installFakeBridge({ analyze: async () => ({ error: "Demo is corrupt" }) });
  setup();
  expect(await screen.findByText("Demo is corrupt")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
});
