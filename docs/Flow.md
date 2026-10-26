# Execution Flows

How data and execution move through the system, traced across file boundaries. Update this file whenever core logic changes. For the static map, see `Architecture.md`.

_Last updated: 2026-10-25 (HTTP MVP)._

Notation: `[file:function()]`, `→` for a call or data handoff, **⚡** for a side effect or state change.

---

## 0. Process startup and lazy initialization

```
uvicorn app.main:app  (run from api/, or via `make run`)
  → [app/main.py] FastAPI(); add_exception_handler(APIError); include health + groups routers
  (nothing heavy loads at import time)

First request that needs the DB:
  → [app/db/__init__.py:get_session_factory()] → get_engine()
      → make_engine(settings.db_url)    relative sqlite path → <repo>/data/app.db (mkdir parent)
                                        sqlite: PRAGMA foreign_keys=ON on every connection
      → init_db()  ⚡ Base.metadata.create_all + CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
      → cache module-level _engine / _Session

First request that needs models:
  → [app/deps.py:get_models()]  (lru_cache, once per process)
      → [app/llm:get_chat_model()]   raises RuntimeError if GOOGLE_API_KEY is empty
      → make_rewrite_chain(llm) if query_rewrite_enabled, else None
      → [app/llm:get_embeddings()]   ⚡ loads BGE-M3 (fp16 on CUDA), ~1.1 GB VRAM
      → [app/llm:get_reranker()]     ⚡ loads bge-reranker-v2-m3 (fp16, Identity activation), ~1.1 GB VRAM
                                     None if reranker_enabled=false
```

The first call to `/health`, `/import` or `/ask` pays the model load: about 10 s, and the first run also downloads ~4.5 GB.

---

## 1. Import a chat export: `POST /api/v1/groups/{wa_group_id}/import`

```
Client (multipart file=chat.txt, ?name=)
  → [routers/groups.py] router dependency [deps.py:require_api_key()]
        X-API-Key != settings.api_key → APIError(401 UNAUTHORIZED) → [errors.py:api_error_handler] envelope
  → [routers/groups.py:import_export()]
        read ≤ 20 MB + 1 byte; too large → 413 FILE_TOO_LARGE
        decode utf-8-sig (BOM stripped); bytes stay in memory, never written to disk
  → [ingestion/service.py:import_chat(session, wa_group_id, content, name)]
        → [ingestion/parser.py:parse_export(content)]
              strip ‎ ‏ ﻿; split lines
              _detect_pattern(): pattern (android | ios) that matches the most lines; 0 matches → ParseError
              group each timestamped line with its continuation lines (multi-line messages)
              _day_first(): any first field > 12 → DD/MM; any second field > 12 → MM/DD; else DD/MM
              body "Sender: text" → chat message; else system line (sender=None)
              _SYSTEM_TEXT match (<Media omitted>, deleted, ...) → is_system=True
              → list[ParsedMessage(ts naive local, sender, text, is_system)]
        ParseError → router → 422 UNPARSEABLE_EXPORT (message lists supported formats)
        → get_or_create_group()                      ⚡ INSERT groups (if new)
        → load existing dedup_keys for the group
        for each ParsedMessage:
            dedup_key = sha1(group_id|ts|sender|text); skip if already seen
            sender → get_or_create_member(ref="name:<sender>", display=masked if phone-like)
                       → hash_id(ref) = sha256(ID_HASH_SALT:ref)
                       ⚡ INSERT users / memberships (if new)
            text_clean = [ingestion/cleaner.py:clean_text(text)] (None for system lines)
            ⚡ INSERT messages (flush every 1000)
        ⚡ COMMIT → ImportResult(group_id, new_messages)
  → [indexing/index.py:index_group(session, group_id, models.embeddings, chroma_dir)]
        SELECT messages ⨝ users.display_name ORDER BY ts, id
        → [indexing/chunker.py:build_chunks(MessageIn[], ChunkParams.from_settings)]
              drop system messages; sort by ts
              _conversations(): split where gap > chunk_gap_minutes (30)
              _windows(): window_size 10, step = size - overlap (3)
              _cap(): halve recursively while approx_tokens(text) > max_chunk_tokens (400)
              _merge_short(): chunks with text < min_chunk_chars (80) merge into a neighbor
              → list[ChunkDraft]  (.text = "DD Mon YYYY\n[HH:MM] Sender: msg", .text_clean)
        ⚡ DELETE FROM chunks_fts WHERE group_id; DELETE chunks WHERE group_id
        ⚡ INSERT chunks (flush → ids)
        ⚡ INSERT chunks_fts(rowid=chunk.id, text_clean, group_id)
        → [indexing/vector_store.py:drop_store()]   ⚡ delete Chroma collection grp_<id> if it exists
        → [indexing/documents.py:chunk_to_document()] per chunk (epoch ts, scalar metadata)
        → get_store(group_id).add_documents(docs, ids=chunk_<id>)
              ⚡ BGE-M3 embeds every chunk text; ⚡ Chroma persists to data/chroma_data
        ⚡ COMMIT → number of chunks
  → 200 {group_id, new_messages, chunks}
```

Properties:
- **Idempotent.** Re-importing the same file inserts 0 messages, and the rebuild gives the same chunk count.
- Every import rebuilds the whole group's derived indexes. The cost grows with group size, not with the number of new messages.
- Runs synchronously inside the request. It moves to an RQ job in Phase 4.

---

## 2. Ask a question: `POST /api/v1/groups/{wa_group_id}/ask`

```
Client {question, user_id}
  → require_api_key()  (as above)
  → [routers/groups.py:ask()]   t0 = perf_counter()
        SELECT group by wa_group_id → none → 404 GROUP_NOT_FOUND
        member_ref(user_id): contains "@" → WhatsApp id; else "name:<user_id>"
        SELECT user ⨝ memberships WHERE group AND wa_id_hash = hash_id(ref) → none → 403 NOT_A_MEMBER
  → [query/chain.py:build_ask_chain(...)]   built per request (collection + group are request-specific)
        vector = get_store(group_id).as_retriever(k=vector_top_k 20)
        fts    = FTS5Retriever(group_id, k=bm25_top_k 20)
        answer_prompt, prompt_version = [prompts:load_prompt("answer_v1")]
  → chain.invoke({"question": q})   (LCEL; each stage adds a key to the dict)

    1. assign(rewrite)      [query/rewrite.py]
         rewriter = rewrite_v1 prompt | gemini.with_structured_output(Rewrite)
                    .with_retry(2) .with_fallbacks([identity_rewrite])
         ⚡ Gemini call #1 (~1-3 s); any failure falls back to {normalized=q, expansions=[], keywords=[]}
         (rewriter None in config → identity_rewrite, no LLM call)

    2. assign(candidates)   hybrid_retrieve()
         queries = dedupe([q, rewrite.normalized, *rewrite.expansions])
         vector.batch(queries)                    → one ranked list per query (BGE-M3 query embeddings)
         fts.invoke(q + " " + keywords)           → [indexing/fts.py]
               fts_query(): clean_text → tokens → '"t1" OR "t2" ...'
               SELECT rowid FROM chunks_fts WHERE MATCH AND group_id ORDER BY bm25 LIMIT k
               → SELECT chunks → chunk_to_document()
         → [query/rrf.py:rrf_merge(lists, k=rrf_k 60)]  score = Σ 1/(60 + rank), metadata.rrf_score

    3. assign(top)          do_rerank() → [query/rerank.py:rerank()]
         first rerank_top_n (20) candidates × every query variant → reranker.score(pairs)  (raw logits)
         each doc keeps max over variants; sort; keep final_top_k (5); best = top score
         reranker None → passthrough (first 5), best = None

    4. RunnableBranch
         below_min_relevance: no docs, or best < min_relevance (-8.0)
             → raw_answer = "NOT_FOUND"         (no LLM call)
         else answer_chain:
             answer_inputs(): {question, today (IST), excerpts = [query/answer.py:format_excerpts(top)]}
                  each excerpt = <excerpt id="n" date=".." participants="..">chunk text</excerpt>
             | answer_v1 prompt | gemini | StrOutputParser   ⚡ Gemini call #2 (~2-4 s)

    5. attach_citations()
         [query/answer.py:parse_answer(raw)] → (answer, [excerpt numbers], not_found)
         not_found → {found: False, answer: NOT_FOUND_REPLY, sources: []}
         cited = docs[n-1] for valid n (default: top doc)
         → [query/citations.py:pick_citations(answer, cited, ...)]
               SELECT the cited chunks' messages ⨝ users (non-system)
               score = cos(embed(answer), embed("[HH:MM] Sender: text")) + 0.5 if "HH:MM" is in the answer
               best message per chunk → {sender, ts (ISO, +05:30), snippet[:200]}
         → {found, answer, sources, interpreted_range: None, chunk_ids, best_score, prompt_version}

  ← back in ask(): latency_ms
     ⚡ INSERT query_logs (query, intent="ask", retrieved_chunk_ids JSON, answer, latency, model, prompt_version)
  → 200 AskResponse {answer, found, interpreted_range, sources, latency_ms}
```

Latency (measured 2026-10-24): 3.0-6.5 s end to end. Stages haven't been timed separately yet. Reranking 21 pairs took 0.05 s on the GPU, so most of the time is presumably the two Gemini calls. Per-stage timing would be the job of a callback handler (see Decisions D-17).

Failure paths:
- Gemini `503` or `429` → retried inside the SDK (`llm_max_retries` 4).
  - In the rewrite step, a final failure falls back to the raw question.
  - In the answer step, a final failure surfaces as a 500. A friendly error message is still to do.
- Empty retrieval → not-found branch.

---

## 3. Health: `GET /api/v1/health`

```
→ [routers/health.py:health()]
    db:           session.execute("SELECT 1")
    vector_store: chromadb PersistentClient(<chroma_dir>).heartbeat()
    llm:          "ok" if GOOGLE_API_KEY is set (no network call, so no quota is used)
→ {status: ok | degraded, db, vector_store, llm}
```

Note: this calls `get_models()`, so the first health check loads the local models.

---

## 4. Test-time flow (no network, no GPU)

```
pytest → [api/tests/conftest.py]
   engine/Session: per-test SQLite file in tmp_path, init_db()
   bow_embeddings: BagOfWordsEmbeddings (crc32 word hashing, over clean_text)
   OverlapReranker: -11 + 3 per shared word, capped at 0
   FakeListChatModel: canned answers; an empty list raises if the LLM is called
API tests: app.dependency_overrides[get_session_factory | get_models] → TestClient
```

---

## Planned flows (not built)

- **Live message** (Phase 4): gateway → `POST /events/message` → store with the same dedup key → micro-batch index job (RQ) → command router (intent rules) → reply.
- **Summary** (Phase 5), **time filter** inside the ask chain between rewrite and retrieval (Phase 6), **extraction jobs** (Phase 7), **topic clustering** (Phase 8).
