import { useCallback, useEffect, useState } from "react";
import { ApiError, listGroups } from "./api";
import ChatPane from "./components/ChatPane";
import GroupSidebar from "./components/GroupSidebar";
import ImportDialog from "./components/ImportDialog";
import InspectorPane from "./components/InspectorPane";
import { applyStoredTheme } from "./components/ThemeToggle";
import { type Turn, useThreads } from "./thread";
import type { GroupSummary } from "./types";
import s from "./App.module.css";

applyStoredTheme();

export default function App() {
  const [groups, setGroups] = useState<GroupSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const { turnsFor, update: updateTurns } = useThreads();
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);

  const refresh = useCallback(async (select?: string) => {
    try {
      const gs = await listGroups();
      setGroups(gs);
      setLoadError(null);
      setSelected((cur) => select ?? cur ?? gs[0]?.wa_group_id ?? null);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const turns: Turn[] = selected ? turnsFor(selected) : [];

  // On group switch, the inspector shows that group's latest turn.
  useEffect(() => {
    if (selected) setSelectedTurnId(turnsFor(selected).at(-1)?.id ?? null);
  }, [selected]); // only on switch, not on every thread update

  useEffect(() => {
    if (!traceOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setTraceOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [traceOpen]);

  const group = groups?.find((g) => g.wa_group_id === selected) ?? null;
  const selectedTurn = turns.find((t) => t.id === selectedTurnId);

  let main: React.ReactNode;
  if (loadError) {
    main = (
      <div className={s.notice}>
        <h1 className={s.noticeTitle}>Can't load chats</h1>
        <p>{loadError}</p>
        <button type="button" className="btn" onClick={() => refresh()}>
          Try again
        </button>
      </div>
    );
  } else if (!groups) {
    main = <p className={`hint ${s.notice}`}>Loading chats</p>;
  } else if (!group) {
    main = (
      <div className={s.notice}>
        <h1 className={s.noticeTitle}>No chats imported yet</h1>
        <p>
          Import a WhatsApp .txt export to begin. A sample is in
          data/samples/college_project_android.txt.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setImportOpen(true)}>
          Import chat
        </button>
      </div>
    );
  } else {
    main = (
      <ChatPane
        group={group}
        groups={groups}
        onSelectGroup={setSelected}
        turns={turns}
        updateTurns={updateTurns}
        selectedTurnId={selectedTurnId}
        onSelectTurn={setSelectedTurnId}
        onOpenTrace={() => setTraceOpen(true)}
      />
    );
  }

  return (
    <div className={s.app}>
      <aside className={s.sidebar}>
        <GroupSidebar
          groups={groups ?? []}
          selected={selected}
          onSelect={setSelected}
          onImport={() => setImportOpen(true)}
        />
      </aside>
      <main className={s.main}>{main}</main>
      <aside className={traceOpen ? `${s.inspector} ${s.open}` : s.inspector} aria-label="Trace">
        <InspectorPane turn={selectedTurn} onClose={() => setTraceOpen(false)} />
      </aside>
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={(id) => refresh(id)}
      />
    </div>
  );
}
