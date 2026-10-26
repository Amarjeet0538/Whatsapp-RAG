import { splitCitations } from "../citations";
import { fmtDateTime } from "../format";
import type { Turn } from "../thread";
import s from "./AnswerBlock.module.css";

type Props = {
  turn: Turn;
  onOpenSource: (messageId: number) => void;
};

export default function AnswerBlock({ turn, onOpenSource }: Props) {
  const r = turn.response;
  if (!r) return null;

  if (!r.found) {
    return <p className={`${s.answer} ${s.notFound}`}>{r.answer}</p>;
  }

  const segments = splitCitations(
    r.answer,
    r.sources.map((src) => src.excerpt),
  );
  const byExcerpt = new Map(r.sources.map((src) => [src.excerpt, src]));
  return (
    <div className={s.block}>
      <p className={`${s.answer} chat-text`}>
        {segments.map((seg, i) =>
          seg.kind === "text" ? (
            <span key={i}>{seg.text}</span>
          ) : (
            <button
              key={i}
              type="button"
              className={s.marker}
              aria-label={`Source ${seg.n}`}
              onClick={(e) => {
                e.stopPropagation();
                onOpenSource(byExcerpt.get(seg.n)!.message_id);
              }}
            >
              {seg.n}
            </button>
          ),
        )}
      </p>
      {r.sources.length > 0 && (
        <ol className={s.sources} aria-label="Sources">
          {r.sources.map((src) => (
            <li key={src.message_id}>
              <button
                type="button"
                className={s.source}
                aria-label={`Open message from ${src.sender ?? "Unknown"} in the chat`}
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenSource(src.message_id);
                }}
              >
                <span className={s.num}>{src.excerpt}</span>
                <span className={s.sourceBody}>
                  <span className={s.sourceMeta}>
                    <span className={s.sender}>{src.sender ?? "Unknown"}</span>
                    <time className="num" dateTime={src.ts}>
                      {fmtDateTime(src.ts)}
                    </time>
                  </span>
                  <span className="chat-text">{src.snippet}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
