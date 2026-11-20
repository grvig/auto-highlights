import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { RenderStep } from "./Render";
import { installFakeBridge } from "./test/fakeBridge";
import type { Job, JobState } from "./types";

afterEach(() => useBridge(null));

function job(state: JobState, extra: Partial<Job> = {}): Job {
  return { id: "r1", title: "semi reel", state, stage: "record", message: "Recording #003", fraction: 0.4, result: null, error: null, ...extra };
}

function setup(onAnother = () => {}) {
  render(
    <RenderStep paths={["a.dem"]} steamid="1" playerName="semi" options={{ seconds: 60 }} onBack={() => {}} onAnother={onAnother} />,
  );
}

test("recording shows progress and the stage, then the finished reel", async () => {
  const answers = [
    job("running"),
    job("done", { fraction: 1, result: { video: "D:\\out\\semi_highlights_2026-11-19_2010.mp4", shape: "stretched", recorded: 14, plays: 8, failed: 0 } }),
  ];
  const bridge = installFakeBridge({ job: async () => answers.shift() ?? answers[0] });
  const render = vi.spyOn(bridge, "render");
  const show = vi.spyOn(bridge, "show_in_folder");
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Record" }));
  expect(render).toHaveBeenCalledWith(["a.dem"], "1", { seconds: 60 });
  expect(await screen.findByText("Recording")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  expect(await screen.findByText("semi_highlights_2026-11-19_2010.mp4", {}, { timeout: 2000 })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "8" })).toBeInTheDocument(); // plays, not the 14 clips
  expect(screen.getByRole("cell", { name: "stretched" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Show in folder" }));
  expect(show).toHaveBeenCalledWith("D:\\out\\semi_highlights_2026-11-19_2010.mp4");
});

test("stopping says the current clip is finished first", async () => {
  const bridge = installFakeBridge({ job: async () => job("running") });
  const cancel = vi.spyOn(bridge, "cancel");
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Record" }));
  await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
  expect(cancel).toHaveBeenCalledWith("render");
  expect(await screen.findByText("Stopping after the current clip…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stop" })).toBeDisabled();
});

test("a failed render says why and can be tried again", async () => {
  const bridge = installFakeBridge({ job: async () => job("failed", { error: "CS2 never opened its console" }) });
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Record" }));
  expect(await screen.findByText(/CS2 never opened its console/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  const logs = vi.spyOn(bridge, "open_logs");
  await userEvent.click(screen.getByRole("button", { name: "Open logs" }));
  expect(logs).toHaveBeenCalled();
});

test("a render that cannot start shows the reason", async () => {
  installFakeBridge({ render: async () => ({ error: "No plays to record for this player." }) });
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Record" }));
  expect(await screen.findByText("No plays to record for this player.")).toBeInTheDocument();
});
