import { ApiFailure, api, bridge, useBridge, type Bridge } from "./api";

afterEach(() => {
  useBridge(null);
  delete window.pywebview;
});

function fake(overrides: Partial<Bridge>): Bridge {
  return overrides as Bridge;
}

test("answers come back unwrapped", async () => {
  useBridge(fake({ find_demos: async () => ({ demos: [] }), render: async () => ({ job: "j1" }) }));
  expect(await api.findDemos()).toEqual([]);
  expect(await api.render(["a.dem"], "7656")).toBe("j1");
});

test("Python's error answers become ApiFailure with its message", async () => {
  useBridge(fake({ analyze: async () => ({ error: "Pick at least one demo." }) }));
  await expect(api.analyze([])).rejects.toEqual(new ApiFailure("Pick at least one demo."));
});

test("the bridge is waited for until pywebview says it is ready", async () => {
  const waiting = bridge();
  const injected = fake({ version: async () => ({ version: "1.0.0" }) });
  window.pywebview = { api: injected };
  window.dispatchEvent(new Event("pywebviewready"));
  expect(await waiting).toBe(injected);
});

test("a bridge that never arrives is reported, not waited on forever", async () => {
  await expect(bridge(5)).rejects.toThrow("did not answer");
});
