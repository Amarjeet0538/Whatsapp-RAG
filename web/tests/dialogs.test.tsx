import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ContextPanel from "../src/components/ContextPanel";
import ImportDialog from "../src/components/ImportDialog";

vi.mock("../src/api", async (orig) => ({
  ...(await orig<typeof import("../src/api")>()),
  getContext: vi.fn(() => new Promise(() => {})),
}));

// jsdom has <dialog> but no modal behaviour; record calls and keep `open` in sync.
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  });
});
afterEach(cleanup);

describe("ContextPanel", () => {
  it("opens as a modal dialog so focus stays inside it", () => {
    render(<ContextPanel groupId="fyp" messageId={1} userId="Riya" onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog.tagName).toBe("DIALOG");
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled();
  });
});

describe("ImportDialog", () => {
  it("starts empty each time it opens, so a new file is not merged into the last group", () => {
    const props = { onClose: () => {}, onImported: () => {} };
    const { rerender } = render(<ImportDialog open {...props} />);
    const id = () => screen.getByPlaceholderText("final-year-project") as HTMLInputElement;
    fireEvent.change(id(), { target: { value: "first-chat" } });
    rerender(<ImportDialog open={false} {...props} />);
    rerender(<ImportDialog open {...props} />);
    expect(id().value).toBe("");
  });
});
