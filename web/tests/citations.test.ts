import { describe, expect, it } from "vitest";
import { splitCitations } from "../src/citations";

describe("splitCitations", () => {
  it("treats a marker as valid only if some source came from that excerpt", () => {
    // Sources came from excerpts 3 and 1: [3] is a citation, [2] is plain text
    expect(splitCitations("x [3] y [2]", [3, 1])).toEqual([
      { kind: "text", text: "x " },
      { kind: "cite", n: 3 },
      { kind: "text", text: " y [2]" },
    ]);
  });

  it("splits markers that point at real sources", () => {
    expect(splitCitations("A [1] b [2].", [1, 2])).toEqual([
      { kind: "text", text: "A " },
      { kind: "cite", n: 1 },
      { kind: "text", text: " b " },
      { kind: "cite", n: 2 },
      { kind: "text", text: "." },
    ]);
  });

  it("keeps out-of-range markers as plain text", () => {
    expect(splitCitations("x [7]", [1, 2, 3])).toEqual([{ kind: "text", text: "x [7]" }]);
  });

  it("returns one text segment when there are no markers", () => {
    expect(splitCitations("plain", [])).toEqual([{ kind: "text", text: "plain" }]);
  });

  it("handles adjacent markers", () => {
    expect(splitCitations("[1][2]", [1, 2])).toEqual([
      { kind: "cite", n: 1 },
      { kind: "cite", n: 2 },
    ]);
  });
});
