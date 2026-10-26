import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, listGroups } from "../src/api";

function respond(status: number, body: string, contentType = "application/json") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status, headers: { "Content-Type": contentType } })),
  );
}

async function failure(): Promise<ApiError> {
  try {
    await listGroups();
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected listGroups to reject");
}

afterEach(() => vi.unstubAllGlobals());

describe("api client errors", () => {
  it("maps the API error envelope to ApiError", async () => {
    respond(403, JSON.stringify({ error: { code: "NOT_A_MEMBER", message: "nope" } }));
    const e = await failure();
    expect(e).toBeInstanceOf(ApiError);
    expect([e.code, e.status, e.message]).toEqual(["NOT_A_MEMBER", 403, "nope"]);
  });

  it("treats a non-JSON proxy error as the API being down", async () => {
    respond(502, "<html>Bad Gateway</html>", "text/html");
    const e = await failure();
    expect(e.code).toBe("API_UNREACHABLE");
    expect(e.message).toBe("API not reachable at 127.0.0.1:8000. Run make run.");
  });

  it("reports a server crash as an API error, not as the API being down", async () => {
    respond(500, "Internal Server Error", "text/plain");
    const e = await failure();
    expect(e.code).toBe("API_ERROR");
    expect(e.message).toBe(
      "The API failed with status 500. Check the terminal running make run.",
    );
  });

  it("treats a network failure as the API being down", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    expect((await failure()).code).toBe("API_UNREACHABLE");
  });

  it("explains a key mismatch on 401", async () => {
    respond(401, JSON.stringify({ error: { code: "UNAUTHORIZED", message: "x" } }));
    expect((await failure()).message).toBe("API key mismatch: check API_KEY in .env");
  });
});
