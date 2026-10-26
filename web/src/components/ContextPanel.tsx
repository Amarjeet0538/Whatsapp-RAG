import { useEffect, useRef, useState } from "react";
import { ApiError, getContext } from "../api";
import { fmtDate, fmtTime } from "../format";
import type { ContextResponse } from "../types";
import s from "./ContextPanel.module.css";

type Props = {
  groupId: string;
  messageId: number;
  userId: string;
  onClose: () => void;
};

export default function ContextPanel({ groupId, messageId, userId, onClose }: Props) {
  const [data, setData] = useState<ContextResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const targetRef = useRef<HTMLLIElement>(null);

  // A modal <dialog> traps focus and handles Esc natively. Opened once per mount, so a
  // re-render of the chat behind it does not move focus.
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    dialogRef.current?.showModal();
    closeRef.current?.focus();
    return () => trigger?.focus();
  }, []);

  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    getContext(groupId, messageId, userId)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [groupId, messageId, userId]);

  useEffect(() => {
    targetRef.current?.scrollIntoView({ block: "center" });
  }, [data]);

  const day = data ? fmtDate(data.messages.find((m) => m.is_target)!.ts) : null;

  return (
    <dialog
      ref={dialogRef}
      className={s.dialog}
      aria-labelledby="ctx-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className={s.panel}>
        <header className={s.header}>
          <div>
            <h2 id="ctx-title" className={s.title}>
              In the chat
            </h2>
            {day && <p className="hint">Around the cited message, {day}</p>}
          </div>
          <button ref={closeRef} type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </header>
        {error && <p className="error">{error}</p>}
        {!data && !error && <p className="hint">Loading messages</p>}
        {data && (
          <ol className={s.list}>
            {data.messages.map((m) => (
              <li
                key={m.id}
                ref={m.is_target ? targetRef : undefined}
                className={m.is_target ? `${s.msg} ${s.target}` : s.msg}
                aria-current={m.is_target ? "true" : undefined}
              >
                <div className={s.meta}>
                  <span className={s.sender}>{m.sender ?? "Unknown"}</span>
                  <time className="num" dateTime={m.ts}>
                    {fmtTime(m.ts)}
                  </time>
                </div>
                <p className="chat-text">{m.text}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </dialog>
  );
}
