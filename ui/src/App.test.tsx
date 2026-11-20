import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { App } from "./App";
import { installFakeBridge } from "./test/fakeBridge";

afterEach(() => useBridge(null));

test("opens on a new reel and switches pages from the side bar", async () => {
  installFakeBridge();
  render(<App />);
  expect(screen.getByRole("tab", { name: "Demos" })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("button", { name: "Reels" }));
  expect(screen.getByRole("tab", { name: "Reels" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reels" })).toHaveAttribute("aria-current", "page");
});

test("a reel in progress survives visiting another page", async () => {
  installFakeBridge({
    find_demos: async () => ({
      demos: [{ path: "R:/a.dem", name: "a.dem", folder: "R:", megabytes: 300, modified: "2026-11-18T20:10" }],
    }),
  });
  render(<App />);
  await userEvent.click(await screen.findByRole("checkbox", { name: /a\.dem/ }));
  await userEvent.click(screen.getByRole("button", { name: "Settings" }));
  await userEvent.click(screen.getByRole("button", { name: "New reel" }));
  expect(screen.getByRole("checkbox", { name: /a\.dem/ })).toBeChecked();
});
