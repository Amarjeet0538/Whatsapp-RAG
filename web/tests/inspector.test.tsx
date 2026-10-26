import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import InspectorPane from "../src/components/InspectorPane";
import { response, trace, turn } from "./fixtures";

afterEach(cleanup);

const withTrace = (over: Parameters<typeof trace>[0]) =>
  turn({ response: response({ trace: trace(over) }) });

describe("InspectorPane", () => {
  it("shows the gate as passed with both numbers", () => {
    render(<InspectorPane turn={withTrace({})} />);
    expect(screen.getAllByText("3.42").length).toBeGreaterThan(0);
    expect(screen.getByText("-8.00")).toBeTruthy();
    expect(screen.getByText("Passed")).toBeTruthy();
  });

  it("shows when the relevance gate blocked the answer", () => {
    render(<InspectorPane turn={withTrace({ gated: true, best_score: -9.5 })} />);
    expect(screen.getByText("Below threshold")).toBeTruthy();
  });

  it("says the reranker is off instead of showing scores", () => {
    render(<InspectorPane turn={withTrace({ rerank_enabled: false, best_score: null })} />);
    expect(screen.getAllByText("Reranker off").length).toBeGreaterThan(0);
  });

  it("prompts for a question when nothing is selected", () => {
    render(<InspectorPane />);
    expect(screen.getByText("Ask a question to see how it was answered.")).toBeTruthy();
  });
});
