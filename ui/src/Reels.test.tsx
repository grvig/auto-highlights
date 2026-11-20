import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { ReelsPage } from "./Reels";
import { installFakeBridge } from "./test/fakeBridge";
import type { Reel } from "./types";

afterEach(() => useBridge(null));

const REEL: Reel = {
  path: "D:\\out\\semi_highlights_2026-11-18_1830.mp4",
  player: "semi",
  made: "2026-11-18T18:30",
  megabytes: 212.4,
  thumbnail: "D:\\out\\semi_highlights_2026-11-18_1830.thumbnail.png",
  chapters: "00:00 QUAD KILL (Round 17)\n00:14 KILLED RYKER (Round 10)",
};

test("reels are listed with their thumbnail, play and folder buttons", async () => {
  const bridge = installFakeBridge({
    reels: async () => ({ reels: [REEL] }),
    thumbnail: async () => ({ url: "data:image/png;base64,UE5H" }),
  });
  const play = vi.spyOn(bridge, "play");
  const { container } = render(<ReelsPage />);
  expect(await screen.findByText("semi_highlights_2026-11-18_1830.mp4")).toBeInTheDocument();
  expect(screen.getByText(/semi · .* · 212.4 MB/)).toBeInTheDocument();
  await vi.waitFor(() => expect(container.querySelector("img")).toHaveAttribute("src", "data:image/png;base64,UE5H"));
  await userEvent.click(screen.getByRole("button", { name: "Play" }));
  expect(play).toHaveBeenCalledWith(REEL.path);
  expect(screen.getByText(/00:14 KILLED RYKER/)).toBeInTheDocument();
});

test("no reels says so", async () => {
  installFakeBridge();
  render(<ReelsPage />);
  expect(await screen.findByText("No reels")).toBeInTheDocument();
});

test("a reel that cannot be opened says why", async () => {
  installFakeBridge({
    reels: async () => ({ reels: [{ ...REEL, thumbnail: null }] }),
    play: async () => ({ error: "That file is not one of your reels." }),
  });
  render(<ReelsPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Play" }));
  expect(await screen.findByText("That file is not one of your reels.")).toBeInTheDocument();
});
