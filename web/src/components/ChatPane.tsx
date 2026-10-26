import { useEffect, useRef, useState } from "react";
import { ApiError, ask, listMembers } from "../api";
import { safeStorage } from "../storage";
import { newTurnId, type Turn } from "../thread";
import { useElapsed } from "../useElapsed";
import type { GroupSummary, MemberSummary } from "../types";
import AnswerBlock from "./AnswerBlock";
import ContextPanel from "./ContextPanel";
import s from "./ChatPane.module.css";

type Props = {
  group: GroupSummary;
  groups: GroupSummary[];
  onSelectGroup: (id: string) => void;
  turns: Turn[];
  updateTurns: (groupId: string, update: (prev: Turn[]) => Turn[]) => void;
  selectedTurnId: string | null;
  onSelectTurn: (id: string) => void;
  onOpenTrace: () => void;
};

const MAX_QUESTION = 1000;

function Pending({ since }: { since: number }) {
  const n = useElapsed(since);
  return (
    <p className={s.pending} aria-live="polite">
      Searching the chat, <span className="num">{n}</span> s
    </p>
  );
}

export default function ChatPane(props: Props) {
  const { group, turns, updateTurns, selectedTurnId, onSelectTurn } = props;
  const groupId = group.wa_group_id;
  const [members, setMembers] = useState<MemberSummary[] | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [askAs, setAskAs] = useState("");
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState<{ messageId: number; userId: string } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const pending = turns.some((t) => t.status === "pending");

  useEffect(() => {
    let live = true;
    setMembers(null);
    setMembersError(null);
    setContext(null);
    listMembers(groupId)
      .then((m) => {
        if (!live) return;
        setMembers(m);
        const saved = safeStorage("session")?.getItem(`askAs:${groupId}`);
        const pick = m.find((x) => x.display_name === saved) ?? m[0];
        setAskAs(pick?.display_name ?? "");
      })
      .catch((e) => live && setMembersError(e instanceof ApiError ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [groupId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns.length]);

  function chooseAskAs(name: string) {
    setAskAs(name);
    try {
      safeStorage("session")?.setItem(`askAs:${groupId}`, name);
    } catch {
      // ignore
    }
  }

  async function send() {
    const q = question.trim();
    if (!q || !askAs || pending) return;
    const turn: Turn = {
      id: newTurnId(),
      question: q,
      askedAs: askAs,
      status: "pending",
      startedAt: Date.now(),
    };
    setQuestion("");
    // groupId is fixed for this ask: the answer goes to this group even after a switch
    const g = groupId;
    updateTurns(g, (prev) => [...prev, turn]);
    onSelectTurn(turn.id);
    const patch = (p: Partial<Turn>) =>
      updateTurns(g, (prev) => prev.map((t) => (t.id === turn.id ? { ...t, ...p } : t)));
    try {
      patch({ status: "done", response: await ask(groupId, q, askAs) });
    } catch (e) {
      patch({ status: "error", error: e instanceof ApiError ? e.message : String(e) });
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  }

  const noMembers = members !== null && members.length === 0;

  return (
    <section className={s.pane} aria-label="Conversation">
      <header className={s.header}>
        <div className={s.titleRow}>
          <select
            className={`input ${s.groupSelect}`}
            value={groupId}
            onChange={(e) => props.onSelectGroup(e.target.value)}
            aria-label="Chat"
          >
            {props.groups.map((g) => (
              <option key={g.wa_group_id} value={g.wa_group_id}>
                {g.name || g.wa_group_id}
              </option>
            ))}
          </select>
          <h1 className={s.title}>{group.name || group.wa_group_id}</h1>
          <button type="button" className={`btn ${s.traceBtn}`} onClick={props.onOpenTrace}>
            Trace
          </button>
        </div>
        <label className={s.askAs}>
          <span>Asking as</span>
          <select
            className="input"
            value={askAs}
            onChange={(e) => chooseAskAs(e.target.value)}
            disabled={!members || noMembers}
          >
            {noMembers && <option value="">No members found</option>}
            {members?.map((m) => (
              <option key={m.display_name} value={m.display_name}>
                {m.display_name}
              </option>
            ))}
          </select>
        </label>
        {membersError && <p className="error">{membersError}</p>}
      </header>

      <div className={s.thread}>
        {turns.length === 0 && (
          <div className={s.empty}>
            <h2 className={s.emptyTitle}>Ask about this chat</h2>
            <p className="hint">
              Questions can mix Hindi and English, for example "budget kitna approved hua?" or
              "who is sending the requirements document?". Answers cite the messages they come
              from.
            </p>
          </div>
        )}
        <ol className={s.turns}>
          {turns.map((t) => (
            <li
              key={t.id}
              className={t.id === selectedTurnId ? `${s.turn} ${s.selected}` : s.turn}
              onClick={() => onSelectTurn(t.id)}
            >
              <p className={s.question}>
                <span className={s.asker}>{t.askedAs}</span>
                <span className="chat-text">{t.question}</span>
              </p>
              {t.status === "pending" && <Pending since={t.startedAt} />}
              {t.status === "error" && <p className="error">{t.error}</p>}
              {t.status === "done" && (
                <AnswerBlock
                  turn={t}
                  onOpenSource={(messageId) => setContext({ messageId, userId: t.askedAs })}
                />
              )}
            </li>
          ))}
        </ol>
        <div ref={endRef} />
      </div>

      <form
        className={s.composer}
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <label htmlFor="question" className="visually-hidden">
          Question
        </label>
        <textarea
          id="question"
          className={`input ${s.textarea}`}
          rows={Math.min(6, Math.max(1, question.split("\n").length))}
          maxLength={MAX_QUESTION}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={askAs ? `Ask as ${askAs}` : "Ask about this chat"}
          disabled={pending || !askAs}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={pending || !askAs || !question.trim()}
        >
          Ask
        </button>
      </form>

      {context && (
        <ContextPanel
          groupId={groupId}
          messageId={context.messageId}
          userId={context.userId}
          onClose={() => setContext(null)}
        />
      )}
    </section>
  );
}
