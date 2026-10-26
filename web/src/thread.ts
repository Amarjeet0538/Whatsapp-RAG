import { useCallback, useState } from "react";
import { readJSON, safeStorage, writeJSON } from "./storage";
import type { AskResponse } from "./types";

export type Turn = {
  id: string;
  question: string;
  askedAs: string;
  status: "pending" | "done" | "error";
  response?: AskResponse;
  error?: string;
  startedAt: number;
};

const key = (groupId: string) => `thread:${groupId}`;

/** Pending turns are dropped on load: their request died with the previous page. */
export function loadThread(groupId: string): Turn[] {
  const store = safeStorage("session");
  if (!store) return [];
  return readJSON<Turn[]>(store, key(groupId), []).filter((t) => t.status !== "pending");
}

export function saveThread(groupId: string, turns: Turn[]): void {
  const store = safeStorage("session");
  if (store) writeJSON(store, key(groupId), turns);
}

/**
 * Threads for every group visited this tab. Updates name their group explicitly, so an
 * answer that arrives after the user switched groups still lands in the group it was asked in.
 */
export function useThreads() {
  const [threads, setThreads] = useState<Record<string, Turn[]>>({});

  const turnsFor = useCallback(
    (groupId: string) => threads[groupId] ?? loadThread(groupId),
    [threads],
  );

  const update = useCallback((groupId: string, fn: (prev: Turn[]) => Turn[]) => {
    setThreads((all) => {
      const next = fn(all[groupId] ?? loadThread(groupId));
      saveThread(groupId, next);
      return { ...all, [groupId]: next };
    });
  }, []);

  return { turnsFor, update };
}

export const newTurnId =() => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
