import type {
  AskResponse,
  ContextResponse,
  GroupSummary,
  ImportResponse,
  MemberSummary,
} from "./types";

const BASE = "/api/v1";
const UNREACHABLE = "API not reachable at 127.0.0.1:8000. Run make run.";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError("API_UNREACHABLE", UNREACHABLE, 0);
  }
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    // The Vite proxy answers 502/503/504 when the API is down. Other non-JSON errors
    // (an uncaught exception gives a plain-text 500) mean the API is up but failed.
    if ([502, 503, 504].includes(res.status)) {
      throw new ApiError("API_UNREACHABLE", UNREACHABLE, res.status);
    }
    if (!res.ok) {
      throw new ApiError(
        "API_ERROR",
        `The API failed with status ${res.status}. Check the terminal running make run.`,
        res.status,
      );
    }
    throw new ApiError("BAD_RESPONSE", "The API sent a response that is not JSON.", res.status);
  }
  if (res.ok) return body as T;
  if (res.status === 401) {
    throw new ApiError("UNAUTHORIZED", "API key mismatch: check API_KEY in .env", 401);
  }
  const err = (body as { error?: { code?: string; message?: string } }).error;
  if (err?.code) throw new ApiError(err.code, err.message ?? err.code, res.status);
  // FastAPI validation errors come as {"detail": [...]}
  throw new ApiError("REQUEST_FAILED", `Request failed with status ${res.status}.`, res.status);
}

const seg = encodeURIComponent;

export const listGroups = () => request<GroupSummary[]>("/groups");

export const listMembers = (g: string) => request<MemberSummary[]>(`/groups/${seg(g)}/members`);

export function importChat(g: string, file: File, name?: string): Promise<ImportResponse> {
  const form = new FormData();
  form.append("file", file);
  const q = name ? `?name=${seg(name)}` : "";
  return request(`/groups/${seg(g)}/import${q}`, { method: "POST", body: form });
}

export function ask(g: string, question: string, userId: string): Promise<AskResponse> {
  return request(`/groups/${seg(g)}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, user_id: userId }),
  });
}

export function getContext(
  g: string,
  messageId: number,
  userId: string,
  window = 5,
): Promise<ContextResponse> {
  const q = `?user_id=${seg(userId)}&window=${window}`;
  return request(`/groups/${seg(g)}/messages/${messageId}/context${q}`);
}
