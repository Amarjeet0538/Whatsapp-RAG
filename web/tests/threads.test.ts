import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { loadThread, type Turn, useThreads } from "../src/thread";

const pending = (id: string): Turn => ({
  id,
  question: "q",
  askedAs: "Riya",
  status: "pending",
  startedAt: 0,
});

beforeEach(() => sessionStorage.clear());

describe("useThreads", () => {
  it("lands a late answer in its own group after the user switched groups", () => {
    const { result } = renderHook(() => useThreads());
    act(() => result.current.update("a", (p) => [...p, pending("t1")]));
    act(() => result.current.update("b", (p) => [...p, pending("t2")]));
    // the ask from group a resolves while b is on screen
    act(() =>
      result.current.update("a", (p) =>
        p.map((t) => (t.id === "t1" ? { ...t, status: "done" } : t)),
      ),
    );
    expect(result.current.turnsFor("a").map((t) => [t.id, t.status])).toEqual([["t1", "done"]]);
    expect(result.current.turnsFor("b").map((t) => t.id)).toEqual(["t2"]);
    expect(loadThread("a").map((t) => t.id)).toEqual(["t1"]);
  });

  it("keeps a pending turn when the user switches away and back", () => {
    const { result } = renderHook(() => useThreads());
    act(() => result.current.update("a", (p) => [...p, pending("t1")]));
    expect(result.current.turnsFor("a")[0].status).toBe("pending");
  });
});
