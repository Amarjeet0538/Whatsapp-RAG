# Architecture

The system map. Read this before making structural changes, and update it whenever a module, service, table, or boundary is added or changed. The specs are `PRD.md` (what) and `TRD.md` (how). The build order is `ROADMAP.md`, the reasoning behind choices is `Decisions.md`, and execution traces are `Flow.md`.

_Last updated: 2026-10-25 (HTTP MVP, Phases 1-3)._

---

## 1. System overview

A WhatsApp group-chat assistant that answers questions over chat history using Retrieval-Augmented Generation (RAG). The main content language is Hinglish, and the default timezone is IST.

```
                      (planned, Phase 4)
 WhatsApp  <──>  gateway/ (Node.js, whatsapp-web.js)
                      │  HTTP + X-API-Key
                      ▼
 curl / tests ──► Core API (FastAPI, api/app, base path /api/v1)      ◄── built (MVP)
                      │
     ┌────────────────┼──────────────────────────┬─────────────────────────┐
     ▼                ▼                          ▼                         ▼
 SQLite (SQLAlchemy)  Chroma (persistent)       Local models (GPU/CPU)    Gemini API (cloud)
 source of truth      grp_<group_id> vectors    BGE-M3 embeddings         gemini-3.5-flash-lite
 + chunks_fts (FTS5)  derived index             bge-reranker-v2-m3        rewrite + answer only
```

### Component status

| Component | Runtime | Status | Notes |
| --- | --- | --- | --- |
| Core API | Python 3.12, FastAPI, LangChain (LCEL) | **Built** | Import, ask, health endpoints |
| Relational DB | SQLite via SQLAlchemy 2.x | **Built** | `data/app.db`; tables via `create_all` (Alembic deferred) |
| Keyword index | SQLite FTS5 table `chunks_fts` | **Built** | Derived from `chunks`; same DB file |
| Vector index | ChromaDB (persistent, cosine) | **Built** | `data/chroma_data`, one collection per group |
| Embeddings | BGE-M3 via `langchain-huggingface` | **Built** | Local; fp16 on GPU |
| Reranker | bge-reranker-v2-m3 via `HuggingFaceCrossEncoder` | **Built** | Local; fp16 on GPU; raw logits |
| LLM | Gemini 3.5 Flash-Lite via `langchain-google-genai` | **Built** | Cloud; only prompts leave the machine |
| Gateway | Node 20, whatsapp-web.js | Planned (Phase 4) | `gateway/` holds only placeholders |
| Worker | RQ + Redis | Planned (Phase 4) | Import/indexing currently synchronous |
| Summaries, time filter, extraction, topics | — | Planned (Phases 5-8) | |
| Eval harness | Python, reuses `app/query` runnables | Planned (Phase 9) | `eval/` holds only placeholders |

---

## 2. Folder structure

```
Whatsapp_RAG/
├── api/
│   ├── requirements.txt          pinned deps
│   ├── app/
│   │   ├── main.py               FastAPI app: routers + APIError handler
│   │   ├── config.py             Settings (pydantic-settings): init > env > .env > config.yaml
│   │   ├── deps.py               require_api_key, Models container, get_models() (lazy, cached)
│   │   ├── errors.py             APIError + {"error":{code,message}} envelope
│   │   ├── db/__init__.py        make_engine (repo-root-relative SQLite), init_db (+FTS5), session factory
│   │   ├── models/
│   │   │   ├── db.py             ORM: Group, User, Membership, Message, Chunk, QueryLog
│   │   │   └── schemas.py        Pydantic: Rewrite (structured output), AskRequest/Response, Source, ImportResponse
│   │   ├── llm/__init__.py       factories: get_chat_model, get_embeddings, get_reranker
│   │   ├── ingestion/
│   │   │   ├── parser.py         .txt export → ParsedMessage (Android/iOS, 12/24h, date order, system lines)
│   │   │   ├── cleaner.py        clean_text(): NFKC, lowercase, repeats, <url>/<phone>, emoji, Hinglish variants
│   │   │   ├── hinglish_norm.yaml  canonical spelling → variants
│   │   │   └── service.py        import_chat(): group/user/membership upsert, dedup, message insert
│   │   ├── indexing/
│   │   │   ├── chunker.py        build_chunks(): time-gap + sliding window + token cap + short merge
│   │   │   ├── documents.py      chunk_to_document(): Chunk row → LangChain Document (scalar metadata)
│   │   │   ├── vector_store.py   get_store()/drop_store() for Chroma collection grp_<id>
│   │   │   ├── fts.py            fts_query() + FTS5Retriever (BaseRetriever over chunks_fts)
│   │   │   └── index.py          index_group(): rebuild chunks + FTS5 + Chroma for one group
│   │   ├── query/
│   │   │   ├── chain.py          build_ask_chain(): the LCEL ask pipeline
│   │   │   ├── rewrite.py        make_rewrite_chain() (structured output) / identity_rewrite
│   │   │   ├── rrf.py            rrf_merge()
│   │   │   ├── rerank.py         rerank(): best score over query variants
│   │   │   ├── answer.py         format_excerpts(), parse_answer(), NOT_FOUND constants
│   │   │   └── citations.py      pick_citations(): best message per cited chunk
│   │   ├── prompts/              versioned YAML prompts (rewrite_v1, answer_v1) + load_prompt()
│   │   ├── routers/
│   │   │   ├── groups.py         POST /groups/{wa_group_id}/import, POST /groups/{wa_group_id}/ask
│   │   │   └── health.py         GET /health
│   │   ├── summarize/ extract/ topics/   placeholders (Phases 5, 7, 8)
│   └── tests/                    pytest; fakes only (no network, no GPU)
├── gateway/ worker/ eval/        placeholders (Phases 4, 9)
├── data/
│   ├── samples/                  synthetic Hinglish exports (committed)
│   ├── app.db, chroma_data/      runtime data (git-ignored)
├── docs/                         PRD, TRD, ROADMAP, TODO, Architecture, Flow, Decisions, Bug, Feature
├── config.yaml                   all tunables (snake_case, mirrors Settings)
├── pyproject.toml                ruff, black, pytest config
└── Makefile                      run, test, lint, format
```

---

## 3. Boundaries (strict rules)

1. **The relational DB is the source of truth.** Chroma and `chunks_fts` are derived indexes. They are rebuilt from `messages` by `index_group()` and are never edited by hand or treated as authoritative.
2. **Models come only from `app/llm/`.** No other module constructs `ChatGoogleGenerativeAI`, `HuggingFaceEmbeddings`, or a cross-encoder. Routers get them through `deps.get_models()`, so tests can override them.
3. **Domain logic is plain Python.** Parsing, cleaning, chunking, dedup, RRF, citation selection, and auth are ordinary functions. They only become `RunnableLambda` inside `app/query/chain.py`. **The LLM never parses commands, computes dates, or decides membership.**
4. **Pipelines are explicit LCEL.** No `RetrievalQA`, `load_summarize_chain`, or `EnsembleRetriever`.
5. **JSON from the LLM goes through `with_structured_output(<Pydantic>)`** with one retry, then a safe fallback (for example, the rewrite falls back to the raw question).
6. **Prompts live in `app/prompts/*.yaml`**, each with a `version` that is recorded in `query_logs.prompt_version`.
7. **Privacy:**
   - Only the LLM prompt (the question plus at most `final_top_k` excerpts) leaves the machine. Chat storage, embeddings, vector and keyword search, and reranking are all local.
   - Free-tier Gemini is for synthetic or anonymized data only.
   - LangSmith tracing stays off.
   - Uploaded exports stay in memory and are never written to disk.
   - Sender ids are stored as salted hashes, and phone-number display names are masked.
   - `query_logs` stores chunk ids, not chat text.
8. **Untrusted chat text:** excerpts go to the LLM inside `<excerpt>` blocks, with a system rule to ignore any instructions found in them. FTS5 queries are built from quoted tokens, so user text can't inject FTS syntax.
9. **Group isolation:** every endpoint that reads group data checks `memberships` for the requesting user. Each group has its own Chroma collection, and FTS5 queries filter on `group_id`.
10. **Auth:** every `/groups/*` route requires `X-API-Key` (compared in constant time). `/health` is open.

---

## 4. Core domain model

### Relational (SQLite, `app/models/db.py`)

| Table | Key columns | Notes |
| --- | --- | --- |
| `groups` | `id`, `wa_group_id` (unique), `name` | `wa_group_id` is the external id used in URLs |
| `users` | `id`, `wa_id_hash` (unique), `display_name` | hash = sha256(salt + ref); ref is `name:<display>` for imports, the WhatsApp id for live messages |
| `memberships` | (`user_id`, `group_id`), `last_seen_*` | Created on import for every sender |
| `messages` | `group_id`, `sender_id`, `ts` (naive IST), `text_raw`, `text_clean`, `is_system`, `source`, `dedup_key` (unique) | dedup = sha1(group, ts, sender, text) |
| `chunks` | `group_id`, `start_ts`, `end_ts`, `participants` (comma-joined), `message_ids` (JSON), `text` | `text` = `[HH:MM] Sender: msg` lines with date headers |
| `chunks_fts` | FTS5(`text_clean`, `group_id` UNINDEXED), `rowid = chunks.id` | Plain (not contentless) table |
| `query_logs` | query, intent, filters, retrieved_chunk_ids, answer, latency_ms, model, prompt_version | One row per `/ask` |

Planned tables (TRD §6.1): `action_items`, `decisions`, `topics`.

### Vector store (Chroma)
- Collection `grp_<group_id>`, cosine distance, document id `chunk_<id>`.
- Metadata (scalar only): `chunk_id`, `group_id`, `start_ts`/`end_ts` (epoch ints), `participants` (string), `message_ids` (JSON string).

### Runtime objects
- `ParsedMessage` (parser output), `MessageIn` / `ChunkDraft` (chunker), LangChain `Document` (retrieval unit).
- `Rewrite` (structured LLM output), `Models` (DI container).

---

## 5. External interfaces

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | none | `{status, db, vector_store, llm}`; `llm` checks only that the key is present |
| POST | `/api/v1/groups/{wa_group_id}/import?name=` | X-API-Key | Multipart `.txt`; returns `{group_id, new_messages, chunks}` |
| POST | `/api/v1/groups/{wa_group_id}/ask` | X-API-Key | `{question, user_id}` → `{answer, found, interpreted_range, sources[], latency_ms}` |

Error codes: `UNAUTHORIZED` 401, `NOT_A_MEMBER` 403, `GROUP_NOT_FOUND` 404, `FILE_TOO_LARGE` 413, `UNPARSEABLE_EXPORT` 422.

---

## 6. Configuration and environment

- `config.yaml` holds all tunables (models, chunking, retrieval, thresholds, paths). `.env` holds secrets: `GOOGLE_API_KEY`, `API_KEY`, `ID_HASH_SALT`, `LANGSMITH_TRACING=false`.
- Relative paths (`db_url`, `chroma_dir`) resolve against the repo root, so it doesn't matter which directory the server is started from.
- Hardware (dev laptop): RTX 3050 (4 GB VRAM), 16 GB RAM. Both local models fit only in fp16 (about 2.3 GB together).

## 7. Testing

- `make test` runs pytest over `api/tests/` (56 tests). The fakes are in `conftest.py`:
  - `FakeListChatModel` for the LLM
  - `BagOfWordsEmbeddings`, an overlap-sensitive fake embedding
  - `OverlapReranker`, a fake reranker
  - a per-test SQLite file and a temp Chroma directory
- API tests use FastAPI `dependency_overrides` on `get_session_factory` and `get_models`.
- The real stack is checked manually end to end (see `ROADMAP.md`, "You are here").
