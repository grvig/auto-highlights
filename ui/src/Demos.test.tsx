import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { NewReel } from "./NewReel";
import { installFakeBridge } from "./test/fakeBridge";
import type { Demo } from "./types";

afterEach(() => useBridge(null));

const DEMOS: Demo[] = [
  { path: "R:/replays/match_382.dem", name: "match_382.dem", folder: "R:/replays", megabytes: 310.2, modified: "2026-11-18T20:10" },
  { path: "R:/replays/match_383.dem", name: "match_383.dem", folder: "R:/replays", megabytes: 280.0, modified: "2026-11-17T19:02" },
];

test("found demos are listed and picking one enables the next step", async () => {
  installFakeBridge({ find_demos: async () => ({ demos: DEMOS }) });
  render(<NewReel />);
  const next = screen.getByRole("button", { name: "Next" });
  expect(next).toBeDisabled();
  await userEvent.click(await screen.findByRole("checkbox", { name: /match_382\.dem/ }));
  expect(screen.getByText("1 selected")).toBeInTheDocument();
  expect(next).toBeEnabled();
});

test("browsed demos are added and picked", async () => {
  installFakeBridge({
    find_demos: async () => ({ demos: DEMOS }),
    pick_demos: async () => ({ paths: ["C:\\Users\\me\\Downloads\\faceit.dem", "R:/replays/match_383.dem"] }),
  });
  render(<NewReel />);
  await screen.findByText("match_382.dem");
  await userEvent.click(screen.getByRole("button", { name: "Browse…" }));
  expect(await screen.findByRole("checkbox", { name: /faceit\.dem/ })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /match_383\.dem/ })).toBeChecked();
  expect(screen.getAllByRole("checkbox")).toHaveLength(3); // the known one is not listed twice
  expect(screen.getByText("2 selected")).toBeInTheDocument();
});

test("an empty search says so", async () => {
  installFakeBridge();
  render(<NewReel />);
  expect(await screen.findByText("No demos found")).toBeInTheDocument();
});
