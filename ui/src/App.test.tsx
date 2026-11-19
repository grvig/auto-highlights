import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

test("opens on a new reel and switches pages from the side bar", async () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "New reel" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Your reels" }));
  expect(screen.getByRole("heading", { name: "Your reels" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Your reels" })).toHaveAttribute("aria-current", "page");
});
