import { useEffect, useRef, useState } from "react";
import { ApiError, importChat } from "../api";
import { useElapsed } from "../useElapsed";
import s from "./ImportDialog.module.css";

const MAX_BYTES = 20 * 1024 * 1024;
const ID_PATTERN = /^[a-z0-9-]+$/;

type Props = {
  open: boolean;
  onClose: () => void;
  onImported: (groupId: string) => void;
};

type State =
  | { kind: "idle" }
  | { kind: "busy"; since: number }
  | { kind: "done"; text: string }
  | { kind: "error"; text: string };

function suggestId(filename: string): string {
  return filename
    .replace(/\.txt$/i, "")
    .replace(/^WhatsApp Chat (with )?/i, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

export default function ImportDialog({ open, onClose, onImported }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [groupId, setGroupId] = useState("");
  const [name, setName] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [state, setState] = useState<State>({ kind: "idle" });
  const elapsed = useElapsed(state.kind === "busy" ? state.since : null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      // Start clean: a leftover group ID would merge the next export into the last group.
      formRef.current?.reset();
      setFile(null);
      setGroupId("");
      setName("");
      setState({ kind: "idle" });
      setFieldError(null);
      d.showModal();
    }
    if (!open && d.open) d.close();
  }, [open]);

  function pick(f: File | null) {
    setFile(f);
    setFieldError(null);
    if (f && !groupId) setGroupId(suggestId(f.name));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return setFieldError("Choose a .txt export file.");
    if (!/\.txt$/i.test(file.name)) {
      return setFieldError("WhatsApp exports are .txt files. Export the chat without media.");
    }
    if (file.size > MAX_BYTES) return setFieldError("The export must be under 20 MB.");
    if (!ID_PATTERN.test(groupId)) {
      return setFieldError("Group ID can use lowercase letters, numbers and hyphens only.");
    }
    setFieldError(null);
    setState({ kind: "busy", since: Date.now() });
    try {
      const r = await importChat(groupId, file, name.trim() || undefined);
      setState({
        kind: "done",
        text:
          r.new_messages === 0
            ? "No new messages; already imported."
            : `Imported ${r.new_messages} new messages into ${r.chunks} chunks.`,
      });
      onImported(groupId);
    } catch (err) {
      setState({ kind: "error", text: err instanceof ApiError ? err.message : String(err) });
    }
  }

  const busy = state.kind === "busy";
  return (
    <dialog ref={ref} className={s.dialog} onClose={onClose} aria-labelledby="import-title">
      <form ref={formRef} onSubmit={submit} className={s.form}>
        <h2 id="import-title" className={s.title}>
          Import a chat
        </h2>
        <p className="hint">
          In WhatsApp, open the group, choose Export chat, then Without media. Upload the .txt
          file here.
        </p>

        <label className="field">
          Export file
          <input
            className="input"
            type="file"
            accept=".txt,text/plain"
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
        </label>

        <label className="field">
          Group ID
          <input
            className="input"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            placeholder="final-year-project"
            disabled={busy}
            required
          />
          <span className="hint">Importing again with the same ID adds only new messages.</span>
        </label>

        <label className="field">
          Display name <span className="hint">(optional)</span>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Final Year Project"
            disabled={busy}
          />
        </label>

        <div className={s.status} aria-live="polite">
          {fieldError && <p className="error">{fieldError}</p>}
          {busy && (
            <p className="hint">
              Indexing, <span className="num">{elapsed}</span> s. The first import also loads
              the embedding model, which can take a minute.
            </p>
          )}
          {state.kind === "done" && <p>{state.text}</p>}
          {state.kind === "error" && <p className="error">{state.text}</p>}
        </div>

        <div className={s.actions}>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            {state.kind === "done" ? "Close" : "Cancel"}
          </button>
          {state.kind !== "done" && (
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Importing" : "Import"}
            </button>
          )}
        </div>
      </form>
    </dialog>
  );
}
