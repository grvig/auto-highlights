import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { App } from "./App";
import { READY, installFakeBridge } from "./test/fakeBridge";

afterEach(() => useBridge(null));

test("the side bar says ready with warnings and opens the checks", async () => {
  installFakeBridge();
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: /Ready, with warnings/ }));
  expect(await screen.findByText("HLAE")).toBeInTheDocument();
  expect(screen.getByLabelText("WARN")).toBeInTheDocument();
});

test("not ready when a check fails", async () => {
  installFakeBridge({
    check: async () => ({ ready: false, checks: [{ name: "ffmpeg", state: "FAIL", detail: "not found" }] }),
  });
  render(<App />);
  expect(await screen.findByRole("button", { name: /Not ready to record/ })).toBeInTheDocument();
});

test("setup runs as a job and the checks are read again afterwards", async () => {
  let checks = 0;
  const bridge = installFakeBridge({
    check: async () => {
      checks += 1;
      return READY;
    },
  });
  const setup = vi.spyOn(bridge, "setup");
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: /Ready, with warnings/ }));
  await screen.findByText("HLAE");
  const before = checks;
  await userEvent.click(screen.getByRole("button", { name: "Download missing tools" }));
  expect(setup).toHaveBeenCalledOnce();
  await vi.waitFor(() => expect(checks).toBeGreaterThan(before));
});
