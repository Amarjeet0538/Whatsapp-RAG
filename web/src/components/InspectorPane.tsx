import { fmtRange, fmtScore } from "../format";
import type { Turn } from "../thread";
import s from "./InspectorPane.module.css";

type Props = {
  turn?: Turn;
  onClose?: () => void;
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className={s.section}>
      <h3 className={s.heading}>{title}</h3>
      {children}
    </section>
  );
}

export default function InspectorPane({ turn, onClose }: Props) {
  const header = (
    <header className={s.header}>
      <h2 className={s.title}>Trace</h2>
      {onClose && (
        <button type="button" className={`btn ${s.close}`} onClick={onClose}>
          Close
        </button>
      )}
    </header>
  );

  const r = turn?.response;
  if (!turn || !r) {
    return (
      <div className={s.pane}>
        {header}
        <p className="hint">
          {turn?.status === "pending"
            ? "Waiting for the answer."
            : turn?.status === "error"
              ? "This question failed, so there is no trace."
              : "Ask a question to see how it was answered."}
        </p>
      </div>
    );
  }

  const t = r.trace;
  return (
    <div className={s.pane}>
      {header}
      <p className={`hint ${s.for}`}>For: {turn.question}</p>

      <Section title="Query rewrite">
        <dl className={s.dl}>
          <dt>Normalized</dt>
          <dd>{t.rewrite.normalized}</dd>
          {t.rewrite.expansions.length > 0 && (
            <>
              <dt>Expansions</dt>
              <dd>
                <ul className={s.plain}>
                  {t.rewrite.expansions.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </dd>
            </>
          )}
          {t.rewrite.keywords.length > 0 && (
            <>
              <dt>Keywords</dt>
              <dd className={s.keywords}>
                {t.rewrite.keywords.map((k) => (
                  <code key={k}>{k}</code>
                ))}
              </dd>
            </>
          )}
        </dl>
      </Section>

      <Section title="Retrieval">
        <table className={s.table}>
          <thead>
            <tr>
              <th scope="col">Vector search query</th>
              <th scope="col" className={s.right}>
                Hits
              </th>
            </tr>
          </thead>
          <tbody>
            {t.retrieval.queries.map((q, i) => (
              <tr key={i}>
                <td>{q.text}</td>
                <td className={`num ${s.right}`}>{q.vector_hits}</td>
              </tr>
            ))}
            <tr>
              <td>
                Keyword search (FTS5)
                <span className={s.sub}>{t.retrieval.fts_query}</span>
              </td>
              <td className={`num ${s.right}`}>{t.retrieval.fts_hits}</td>
            </tr>
            <tr className={s.total}>
              <td>Unique chunks after RRF merge</td>
              <td className={`num ${s.right}`}>{t.retrieval.merged}</td>
            </tr>
          </tbody>
        </table>
      </Section>

      <Section title="Reranked excerpts">
        <ol className={s.chunks}>
          {t.reranked.map((c, i) => (
            <li key={c.chunk_id} className={c.cited ? `${s.chunk} ${s.cited}` : s.chunk}>
              <div className={s.chunkHead}>
                <span className="num">{i + 1}</span>
                <span className={s.score}>
                  {c.score === null ? "Reranker off" : <span className="num">{fmtScore(c.score)}</span>}
                </span>
                {c.cited && <span className={s.citedTag}>Cited</span>}
              </div>
              <p className={s.chunkMeta}>
                {fmtRange(c.start_ts, c.end_ts)}
                <br />
                {c.participants}
              </p>
              <p className={`chat-text ${s.preview}`}>{c.preview}</p>
            </li>
          ))}
        </ol>
        <p className={s.note}>Scores are raw cross-encoder logits; higher is more relevant.</p>
      </Section>

      <Section title="Relevance gate">
        {t.rerank_enabled && t.best_score !== null ? (
          <>
            <dl className={s.dl}>
              <dt>Best score</dt>
              <dd className="num">{fmtScore(t.best_score)}</dd>
              <dt>Minimum</dt>
              <dd className="num">{fmtScore(t.min_relevance)}</dd>
            </dl>
            <p className={t.gated ? s.blocked : s.passed}>
              {t.gated ? "Below threshold" : "Passed"}
            </p>
            {t.gated && (
              <p className="hint">No excerpt was relevant enough, so the model was not called.</p>
            )}
          </>
        ) : (
          <p>Reranker off</p>
        )}
        {!t.gated && !r.found && (
          <p className="hint">The model read the excerpts and found no answer in them.</p>
        )}
      </Section>

      <Section title="Run">
        <dl className={s.dl}>
          <dt>Prompt</dt>
          <dd className="num">{t.prompt_version}</dd>
          <dt>Latency</dt>
          <dd>
            <span className="num">{t.latency_ms}</span> ms
          </dd>
        </dl>
      </Section>
    </div>
  );
}
