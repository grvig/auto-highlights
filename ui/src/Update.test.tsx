import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useBridge } from "./api";
import { UpdateButton } from "./Update";
import { installFakeBridge } from "./test/fakeBridge";

afterEach(() => useBridge(null));

test("a newer release shows a button that opens its page", async () => {
  const bridge = installFakeBridge({
    check_update: async () => ({ available: true, version: "1.0.1", url: "https://github.com/grvig/auto-highlights/releases" }),
  });
  const open = vi.spyOn(bridge, "open_releases");
  render(<UpdateButton />);
  await userEvent.click(await screen.findByRole("button", { name: "Version 1.0.1 is available" }));
  expect(open).toHaveBeenCalled();
});

test("nothing shows when the app is up to date", async () => {
  installFakeBridge();
  const { container } = render(<UpdateButton />);
  await new Promise((r) => setTimeout(r, 0));
  expect(container).toBeEmptyDOMElement();
});
