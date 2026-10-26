import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AnswerBlock from "../src/components/AnswerBlock";
import { response, turn } from "./fixtures";

afterEach(cleanup);

describe("AnswerBlock", () => {
  it("renders citation markers as buttons that open the cited message", () => {
    const onOpenSource = vi.fn();
    render(<AnswerBlock turn={turn()} onOpenSource={onOpenSource} />);
    fireEvent.click(screen.getByRole("button", { name: "Source 1" }));
    expect(onOpenSource).toHaveBeenCalledWith(812);
  });

  it("maps a marker to the source from that excerpt, not by list position", () => {
    const onOpenSource = vi.fn();
    const src = response().sources[0];
    const t = turn({
      response: response({
        answer: "Paisa 20 tarikh tak [2].",
        sources: [{ ...src, message_id: 900, excerpt: 2 }],
      }),
    });
    render(<AnswerBlock turn={t} onOpenSource={onOpenSource} />);
    fireEvent.click(screen.getByRole("button", { name: "Source 2" }));
    expect(onOpenSource).toHaveBeenCalledWith(900);
  });

  it("shows no source list for a not-found answer", () => {
    const t = turn({
      response: response({ found: false, answer: "I couldn't find this in the chat.", sources: [] }),
    });
    render(<AnswerBlock turn={t} onOpenSource={() => {}} />);
    expect(screen.getByText("I couldn't find this in the chat.")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();
  });
});
