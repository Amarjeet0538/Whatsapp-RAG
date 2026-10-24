# Implementation Roadmap

A step-by-step build order for the WhatsApp group-chat RAG assistant. `PRD.md` says what to build and `TRD.md` says how. This file sets the order and gives each step a "done when" check. `TODO.md` holds the detailed checklist for the current phase.

> **You are here: Phase 1, Step 1.3 (config keys)**. Steps 1.1 and 1.2 are done, and every later step is still open.

Legend: `[x]` done, `[~]` in progress / partial, `[ ]` not started.

Phases follow the 16-week timeline in PRD §15. Scope freezes at the end of Phase 4.

---

## Phase 1: Foundation (weeks 1-2)

### 1.1 [x] Repo skeleton, config loader, health stub
- Module directories under `api/app/`, `gateway/`, `worker/`, `eval/`, `data/`.
- `api/app/config.py`: pydantic-settings that loads init args > env > `.env` > `config.yaml`.
- `GET /api/v1/health` stub in `api/app/main.py`. `.env.example` sets `LANGSMITH_TRACING=false`.
- **Done when:** `uvicorn app.main:app` serves `/api/v1/health`. ✔

### 1.2 [x] Environment and dependencies (TRD §3, §4, §17.7)
- Create a Gemini API key (Google AI Studio) and put it in `.env` as `GOOGLE_API_KEY`. The LLM is `gemini-3.5-flash-lite`, with no local fallback. Embeddings and the reranker run locally on this laptop (RTX 3050 4 GB, 16 GB RAM).
- Install the deps and pin exact versions in `api/requirements.txt`: `langchain-core`, `langchain-google-genai`, `langchain-chroma`, `langchain-huggingface`, `langchain-community`, `chromadb`, `sentence-transformers`, `sqlalchemy`, `alembic`, `dateparser`, `emoji`, `structlog`, `pytest`, `pytest-asyncio`, `httpx`.
- Configure ruff + black in `pyproject.toml`.
- **Done when:** a one-line `ChatGoogleGenerativeAI` call returns text, `pip install -r api/requirements.txt` succeeds with every version pinned, and `ruff check` runs. ✔ (2026-10-24: Gemini text and structured-output calls work; deps pinned; ruff + black configured in `pyproject.toml`; torch sees the RTX 3050 via CUDA.)
- Latency issue (resolved 2026-10-24): `gemini-3.8-flash` calls took 30-123 s. The cause was Google's server time on the free tier (`server-timing` header ~123 s for 14 tokens). The network (0.7 s round trip), SDK retries (none), and thinking tokens (0) were ruled out. Switched to `gemini-3.5-flash-lite`: 2.7-5.9 s per call through LangChain, with valid structured output in 3 of 3 runs. Flash-Lite ignores `temperature` (fixed sampling) and sometimes returns `503 high demand`, so the 1.4 factory needs retry with backoff. Minor: this machine has no IPv6 route, so the first connection loses ~1 s on the IPv6 attempt. See TRD §17.1.

### 1.3 [ ] Config keys (TRD §8)
- Already added: `llm_provider`, `llm_model`, `llm_max_tokens`, `llm_thinking_level`, `google_api_key`. Still to add: `reranker_model`, `rerank_top_n`, `rrf_k`, `chroma_dir`, `min_relevance`, `max_chunk_tokens`, `min_chunk_chars`, `summary_direct_tokens`, `db_url` to both `config.yaml` and `Settings`.
- **Done when:** `get_settings()` exposes every TRD §8 key, and an env var overrides the YAML value.

### 1.4 [ ] Model factories in `app/llm/` (TRD §2.5)
- `get_chat_model()` returns `ChatGoogleGenerativeAI` (model, temperature set explicitly, `max_tokens`, `thinking_level`, `max_retries` from config). It fails fast if `google_api_key` is empty, and it retries `503`/`429` with backoff.
- `get_embeddings()` returns `HuggingFaceEmbeddings("BAAI/bge-m3", normalize_embeddings=True)`, cached as a singleton.
- `get_reranker()` returns `HuggingFaceCrossEncoder`, or `None` when `reranker_enabled=false`.
- Write a smoke script: `with_structured_output(<Pydantic model>)` on a Hinglish prompt.
- **Done when:** the smoke script returns a valid Pydantic object from Gemini 3.5 Flash-Lite.

### 1.5 [ ] Test scaffold (TRD §12)
- `api/tests/conftest.py` with fixtures for `GenericFakeChatModel` / `FakeListChatModel`, fake embeddings, and an in-memory SQLite.
- `Makefile` target: `make test`.
- **Done when:** `make test` runs green with at least one test (config loading).

### 1.6 [ ] Synthetic Hinglish dataset plan (PRD §12.1, TRD §13)
- Pick the scenarios (college project, client group, family). Write sample Android and iOS export fixtures under `data/samples/`.
- Stub the generator script (`eval/generate_synthetic.py`) and set the target of 5,000+ messages, about 20% manually audited.
- **Done when:** fixture files exist for both export formats, and the generator plan is written down.

---

## Phase 2: Ingestion and indexing (weeks 3-4)

### 2.1 [ ] DB layer (TRD §6.1)
- `app/db/`: engine, session, SQLite pragmas, Alembic setup. `app/models/`: SQLAlchemy models for groups, users, memberships, messages, chunks, action_items, decisions, topics, query_logs.
- Create the FTS5 virtual table `chunks_fts` through a migration.
- **Done when:** `alembic upgrade head` creates every table, and a model round-trip test passes.

### 2.2 [ ] Chat export parser (TRD §5.2; FR-ING-1, 2, 3, 5)
- `app/ingestion/parser.py`: regex patterns for Android and iOS, 12h/24h, DD/MM vs MM/DD auto-detection, BOM handling, multi-line joining, system-line flags, `sha1` dedup key.
- Hash phone numbers / map display names to `wa_id_hash` (TRD §10). Batch inserts of 1,000.
- **Done when:** unit tests cover Android 24h, Android 12h, iOS, multi-line, emoji, system lines, and date order, and re-importing the same file inserts 0 rows.

### 2.3 [ ] Cleaner and Hinglish normalizer (TRD §5.3; FR-IDX-1)
- `app/ingestion/cleaner.py`: NFKC, lowercase, repeat collapse, `<url>`/`<phone>`, emoji to text. A YAML variant dictionary (`kb/kab/kub → kab`, …) keeps numbers and names untouched.
- One function, used for both indexed text and queries.
- **Done when:** table-driven tests pass, and `text_clean` is filled on import.

### 2.4 [ ] Chunker (TRD §5.4; FR-IDX-2, 3, 7)
- `app/indexing/chunker.py`: 30-min gap split, window 10 / overlap 3, token cap, merging short chunks, `[HH:MM] Sender: msg` lines with a date header, system messages excluded.
- Output `Document`s with scalar metadata (epoch `start_ts`/`end_ts`, joined participants and message IDs). Persist to `chunks`.
- **Done when:** tests check gap splitting, overlap, the cap, and the short-chunk merge, and no chunk is made of a lone "ok".

### 2.5 [ ] Vector store and FTS5 retriever (TRD §5.5, §6.2; FR-IDX-4, 5)
- `app/indexing/vector_store.py`: `get_store(group_id)` returns `Chroma(collection_name="grp_<id>", persist_directory=chroma_dir)`, with idempotent `add_documents(ids=["chunk_<id>"])`.
- `app/indexing/fts.py`: FTS5 insert/delete plus an `FTS5Retriever(BaseRetriever)` that returns Documents with the same metadata.
- **Done when:** indexing a fixture group twice leaves the counts unchanged, and both retrievers return the expected chunk for a known query.

### 2.6 [ ] Import endpoint, auth, health (TRD §7)
- `app/routers/`: `POST /groups/{id}/import` (multipart, synchronous for now; moves to a job in 4.3). `X-API-Key` dependency. Error envelope `{error:{code,message}}`. Delete the raw upload after parsing.
- `/health` checks the DB, Chroma, and that the Gemini key is configured (a cheap `models.get` call).
- **Done when:** an httpx integration test runs import → messages → chunks → both indexes on a fixture chat.

### 2.7 [ ] Reindex command (TRD §9)
- Script plus `make reindex` that rebuilds Chroma and FTS5 from `messages`.
- **Done when:** deleting `chroma_data` and running `make reindex` restores the search results.

---

## Phase 3: Core RAG (weeks 5-6)

### 3.1 [ ] Prompt loading (TRD §2.5.5)
- `app/prompts/*.yaml` (versioned, e.g. `answer_v1.yaml`), with a loader that returns `ChatPromptTemplate` and the version string. Excerpts sit in delimited blocks, with an instruction to ignore any instructions found inside them.

### 3.2 [ ] Intent and query rewrite (TRD §5.6; FR-QA-2)
- `app/query/intent.py`: rule-based first, LLM structured-output fallback, default `ask`.
- `app/query/rewriter.py`: `prompt | llm.with_structured_output(Rewrite)` → `{normalized, expansions, keywords}`, retry once.

### 3.3 [ ] Hybrid retrieval and RRF (FR-QA-3)
- `app/query/retrieve.py`: `RunnableParallel` (vector over normalized + expansions, FTS5 over keywords), then a custom `rrf_merge` (k = `rrf_k`). Retrievers are built per request with the group and time filter.
- **Done when:** RRF has unit tests, and a paraphrase query ("payment kab milega" vs "paisa 20 tarikh tak") hits the right chunk.

### 3.4 [ ] Reranker and no-answer gate (FR-QA-4, 7)
- `app/query/rerank.py`: cross-encoder over the top `rerank_top_n`, keeping `final_top_k` and exposing `best_score`. `RunnableBranch` returns not-found below `min_relevance`. Passes through when the reranker is disabled.

### 3.5 [ ] Grounded answer and citations (FR-QA-5, 6, 8)
- `app/query/answer.py`: format excerpts, `ChatGoogleGenerativeAI(temperature=0.1, max_tokens=400)`, parse `SOURCES: [..]` and `NOT_FOUND`, pick the 1-2 best messages per source (sender, ts, snippet).

### 3.6 [ ] `ask_chain`, endpoint, logging (TRD §5.6, §7)
- `app/query/chain.py` assembles the LCEL pipeline. `POST /groups/{id}/ask` enforces membership.
- `app/llm/callbacks.py`: a `BaseCallbackHandler` that writes to `query_logs` (chunk IDs, latency, model, prompt version).
- **Done when:** the response matches the TRD §7 example shape, a non-member gets 403, and a log row is written.

### 3.7 [ ] First golden tests
- Fake-LLM chain tests for found / not-found. Start `eval/datasets/qa.jsonl` with about 20 labeled questions.

---

## Phase 4: Bot integration (weeks 7-8), then scope freeze

### 4.1 [ ] Gateway service (TRD §5.1)
- `gateway/`: Node 20, pinned `whatsapp-web.js`. A `GatewayAdapter` interface (`onMessage`, `sendText`, `sendImage`), `LocalAuth` QR login, reconnect with backoff, a local outbox for when the API is down. Normalize events to the TRD payload.

### 4.2 [ ] Live ingest and command router (TRD §5.12; FR-ING-4, FR-BOT-1, 2, 5, 6)
- `POST /events/message`: store the live message (same dedup key), parse commands in code, mention detection, `/help`, `/group` (active group per DM user), `/ask`, `/import`. Membership check and rate limit (10/min).

### 4.3 [ ] Worker and jobs (TRD §2.4, §5.5; FR-IDX-6)
- Redis + RQ in `worker/`, reusing `api/app`. Live micro-batching (10 messages or 60 s), re-embedding the open chunk, import as a job, `GET /jobs/{id}`, 3 retries and a `failed` mark.

### 4.4 [ ] Reply formatting (FR-BOT-3, 4)
- WhatsApp markdown helpers, splitting at about 3,500 characters, "working on it…" for jobs over 5 s. Jest tests for parsing, splitting, and reconnect.

### 4.5 [ ] Docker Compose (TRD §14.1)
- Services `gateway`, `api`, `worker`, `redis`. Volumes `wa_session`, `chroma_data`, `db_data`. `GOOGLE_API_KEY` passed via `.env`. `make up`.
- **Phase done when:** in a real test group, `/ask` returns a cited answer and a live message becomes searchable within 60 s.

---

## Phase 5: Summarization (week 9), TRD §5.8, FR-SUM-*, FR-ING-7
- [ ] 5.1 Range selection: unread (`last_seen_at`), last N, last X hours/days, custom range.
- [ ] 5.2 Direct path under `summary_direct_tokens`. Map chain with `.batch(max_concurrency≤2)`, reduce chain `with_structured_output(Summary)`, recursive reduce guarded by token count.
- [ ] 5.3 Short / standard / detailed rendering in WhatsApp format. Delivered by DM.
- [ ] 5.4 Update `last_seen_*` only after delivery succeeds. `/summary` command plus the endpoint (202 + job).
- **Done when:** a 200-message summary takes ≤ 30 s and keeps names, numbers, and dates.

## Phase 6: Time-filtered queries (week 10), TRD §5.7, FR-TIME-*
- [ ] 6.1 `app/query/time_parser.py`: English and Hinglish rules (`aaj`, `kal` defaults to yesterday for past queries, `parso`, `pichhle hafte`, `is mahine`, `last 3 days`, `in March`, `between X and Y`), dateparser, IST, Monday weeks.
- [ ] 6.2 Apply the range in the Chroma `where` filter and the FTS5 SQL. Echo "Showing results from … to …". Ask for clarification when resolution fails.
- [ ] 6.3 Reuse the parser in summary ranges and extraction deadlines.
- **Done when:** the TRD §12 time-parser test cases pass, including boundary dates.

## Phase 7: Action items and decisions (weeks 11-12), TRD §5.9, §5.10, FR-ACT-*, FR-DEC-*
- [ ] 7.1 Pydantic schemas plus few-shot Hinglish prompts (with negatives for sarcasm, jokes, hypotheticals).
- [ ] 7.2 Extraction chain with one retry. Post-processing: owner fuzzy match ("main/I" → sender), deadline via the time parser from the message timestamp, confidence filter, embedding-based dedup.
- [ ] 7.3 Decision chain (agreement required). Override detection is P2.
- [ ] 7.4 Worker job over chunks with `extracted=0`, run on import and on live batches.
- [ ] 7.5 `/tasks` (all, mine, @person, overdue), `/done <id>`, `/decisions [topic]` plus the TRD §7 endpoints. Overdue flag. Completion suggestions (P1).
- **Done when:** extraction F1 ≥ 0.70 on the labeled dev set.

## Phase 8: Topic clustering (week 13), TRD §5.11, FR-TOP-*
- [ ] 8.1 Read embeddings from Chroma, UMAP + HDBSCAN (KMeans fallback), c-TF-IDF via BERTopic.
- [ ] 8.2 LLM label chain with `.batch()`, counts / share / weekly volume, persist to `topics`.
- [ ] 8.3 matplotlib bar chart and timeline sent as an image. `/topics [range|refresh]`, nightly refresh job.
- **Done when:** clustering 10k messages takes ≤ 2 min, and the labels make sense.

## Phase 9: Evaluation (week 14), PRD §12, TRD §13
- [ ] 9.1 Complete the datasets: `qa.jsonl` (100+), `actions.jsonl` / `decisions.jsonl` (150+), `summaries.jsonl` (20).
- [ ] 9.2 Retrieval benchmark: BM25-only, vector-only, hybrid, + rerank, ± rewrite, done by swapping stages for passthroughs. Recall@1/3/5/10, MRR, nDCG.
- [ ] 9.3 Faithfulness judge plus a manual sample, no-answer accuracy, extraction P/R/F1, ROUGE-L / BERTScore, LLM comparison (Gemini 3.5 Flash-Lite vs 3.8 Flash, re-measuring 3.8 Flash latency), chunking and embedding ablations.
- [ ] 9.4 `make eval` writes `eval/results/<date>.json` with fixed seeds. Calibrate `min_relevance` on the dev set.
- **Done when:** Recall@5 ≥ 80% and faithfulness ≥ 85% (or the gaps are documented).

## Phase 10: Polish and documentation (weeks 15-16)
- [ ] 10.1 Security tests: a non-member never gets content, prompt-injection samples, `/purge` and `DELETE /groups/{id}` remove all derived data.
- [ ] 10.2 Performance benchmarks against TRD §11 (ask ≤ 10 s, import of 10k ≤ 10 min). `make seed`.
- [ ] 10.3 README, API docs, demo script (PRD §16), demo video, final report with ablations, slides, viva prep.

---

## Keeping this file current
- Tick a box when its "done when" check passes, and move the **You are here** marker.
- When a phase starts, copy its steps into `TODO.md` as detailed sub-tasks.
- References: [PRD](PRD.md) · [TRD](TRD.md) · [TODO](TODO.md)
