import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { App } from "./App";
import { installFakeBridge } from "./test/fakeBridge";

afterEach(() => useBridge(null));

test("opens on a new reel and switches pages from the side bar", async () => {
  installFakeBridge();
  render(<App />);
  expect(screen.getByRole("heading", { name: "Pick your demos" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Your reels" }));
  expect(screen.getByRole("heading", { name: "Your reels" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Your reels" })).toHaveAttribute("aria-current", "page");
});
