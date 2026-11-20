import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { SettingsPage, changed } from "./SettingsPage";
import { installFakeBridge } from "./test/fakeBridge";
import type { Settings } from "./types";

afterEach(() => useBridge(null));

const SETTINGS: Settings = {
  configured: true,
  output_dir: "D:/auto-highlights/output",
  clips_dir: "D:/auto-highlights/clips",
  aspect: "stretched",
  hud: "clean",
  recorder: "hlae",
  music: null,
  music_start: 0,
  transition: "cut",
  target_seconds: 120,
};

test("only changed settings are saved, under their config keys", async () => {
  const bridge = installFakeBridge({
    settings: async () => SETTINGS,
    save_settings: async (changes) => ({ ...SETTINGS, aspect: String(changes["recording.aspect"]) }),
    pick_folder: async () => ({ path: "E:/reels" }),
  });
  const save = vi.spyOn(bridge, "save_settings");
  render(<SettingsPage />);
  const button = await screen.findByRole("button", { name: "Save" });
  expect(button).toBeDisabled();
  await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Reel shape" }), "vertical");
  await userEvent.click(screen.getByRole("button", { name: "Change…" }));
  expect(screen.getByRole("textbox", { name: "Output folder" })).toHaveValue("E:/reels");
  await userEvent.click(button);
  expect(save).toHaveBeenCalledWith({ "recording.aspect": "vertical", "paths.output_dir": "E:/reels" });
  expect(await screen.findByText("Saved")).toBeInTheDocument();
});

test("a rejected value is shown and nothing else changes", async () => {
  installFakeBridge({
    settings: async () => SETTINGS,
    save_settings: async () => ({ error: "editing.target_seconds must be at least 15" }),
  });
  render(<SettingsPage />);
  const length = await screen.findByRole("spinbutton", { name: "Default length" });
  await userEvent.clear(length);
  await userEvent.type(length, "5");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("editing.target_seconds must be at least 15")).toBeInTheDocument();
});

test("music can be chosen and removed", () => {
  expect(changed(SETTINGS, { ...SETTINGS, music: "C:/m/track.mp3" })).toEqual({ "editing.music": "C:/m/track.mp3" });
  expect(changed({ ...SETTINGS, music: "C:/m/track.mp3" }, { ...SETTINGS, music: "" })).toEqual({ "editing.music": "" });
  expect(changed(SETTINGS, { ...SETTINGS, music: "" })).toEqual({});
});

test("before setup there is nothing to edit yet", async () => {
  installFakeBridge({ settings: async () => ({ configured: false }) });
  render(<SettingsPage />);
  expect(await screen.findByText(/Not set up yet/)).toBeInTheDocument();
});
