import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { NewReel } from "./NewReel";
import { installFakeBridge } from "./test/fakeBridge";

afterEach(() => useBridge(null));

test("the whole flow plans with the length saved in settings", async () => {
  const bridge = installFakeBridge({
    settings: async () => ({ configured: true, target_seconds: 90 }),
    find_demos: async () => ({
      demos: [{ path: "R:/a.dem", name: "a.dem", folder: "R:", megabytes: 300, modified: "2026-11-18T20:10" }],
    }),
    analyze: async () => ({
      matches: [{ path: "R:/a.dem", file: "a.dem", map: "de_nuke", gotv: false, rounds: 24 }],
      players: [{ steamid: "1", name: "semi", matches: 1, kills: 27, deaths: 14, you: true }],
    }),
  });
  const plan = vi.spyOn(bridge, "plan");
  render(<NewReel />);
  await userEvent.click(await screen.findByRole("checkbox", { name: /a\.dem/ }));
  await userEvent.click(screen.getByRole("button", { name: "Read demos" }));
  await vi.waitFor(() => expect(screen.getByRole("radio", { name: "semi" })).toBeChecked());
  await userEvent.click(screen.getByRole("button", { name: "Find plays" }));
  await vi.waitFor(() => expect(plan).toHaveBeenCalledWith(["R:/a.dem"], "1", { seconds: 90, order: "montage" }));
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Plays");
});
