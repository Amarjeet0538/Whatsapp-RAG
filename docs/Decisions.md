# Decisions

Why the system is built the way it is. Append a record whenever a dependency is added, a pattern is chosen, or a significant refactor happens. Never edit an old record's reasoning: if a decision is reversed, add a new record and mark the old one **Superseded by D-xx**.

Format: **Context & problem** · **Options considered** · **Chosen** · **Why** (the deciding factor).

_Records D-01 to D-22 were written retroactively on 2026-10-25, covering work up to the HTTP MVP._

---

## Index

| ID | Decision | Status |
| --- | --- | --- |
| D-01 | Modular monolith + separate gateway | Accepted |
| D-02 | LangChain with explicit LCEL chains | Accepted |
| D-03 | Cloud LLM (Gemini) instead of local Ollama | Accepted (supersedes TRD v1 local-LLM plan) |
| D-04 | Gemini 3.5 Flash-Lite instead of 3.8 Flash | Accepted |
| D-05 | No fallback LLM | Accepted |
| D-06 | Local BGE-M3 + bge-reranker-v2-m3, fp16 on GPU | Accepted |
| D-07 | Reranker outputs raw logits; `min_relevance = -8.0` | Accepted (provisional value) |
| D-08 | Rerank against all query variants, keep the max | Accepted |
| D-09 | Hybrid retrieval: Chroma + custom FTS5 retriever + custom RRF | Accepted |
| D-10 | Plain (not contentless) FTS5 table | Accepted |
| D-11 | Time-gap + sliding-window chunking, approximate token count | Accepted |
| D-12 | Custom export parser, DD/MM default | Accepted |
| D-13 | Citation pick: formatted-line similarity + time-mention boost | Accepted |
| D-14 | SQLite + `create_all`; Alembic deferred | Accepted (temporary) |
| D-15 | Rebuild a group's indexes on every import | Accepted (temporary) |
| D-16 | Synchronous import; no queue yet | Accepted (temporary) |
| D-17 | Query log written by the endpoint, not a callback handler | Accepted (temporary) |
| D-18 | URL group id = WhatsApp group id; import identities = hashed display name | Accepted |
| D-19 | Tests run on fakes (no network, no GPU) | Accepted |
| D-20 | Exact version pins; Python 3.12 | Accepted |
| D-21 | Query rewrite falls back to the raw question | Accepted |
| D-22 | Cleaner rules: letters-only repeat collapse, curated variant dictionary | Accepted |

---

### D-01: Modular monolith + separate gateway
- **Context & problem:** The system needs a WhatsApp connection (only Node libraries are mature for this) plus a Python RAG stack, built and debugged by one or two students.
- **Options:** microservices per module; a single Node app; a Python monolith with a Node gateway.
- **Chosen:** A FastAPI modular monolith (`api/app/*` packages with clear boundaries) plus a thin Node gateway talking over HTTP with a shared `X-API-Key`.
- **Why:** It keeps the system debuggable by a small team while module boundaries stay clean. The gateway sits behind a `GatewayAdapter` because the unofficial WhatsApp library is the riskiest dependency (ban or breakage risk), so it needs to be swappable for Baileys. (TRD §2.1)

### D-02: LangChain with explicit LCEL chains
- **Context & problem:** We need an orchestration layer with swappable models and stores, and every pipeline step has to be explainable in the viva.
- **Options:** plain Python; LlamaIndex; LangChain legacy chains (`RetrievalQA`, `load_summarize_chain`, `EnsembleRetriever`); LangChain LCEL with custom runnables.
- **Chosen:** `langchain-core` runnables plus integration packages. Each stage is its own function or runnable composed in `app/query/chain.py`. Domain logic stays plain Python.
- **Why:** The standard interfaces make model and store swaps a config change, while explicit LCEL keeps every step visible, testable, and swappable for a passthrough (ablations in the eval). Legacy chains hide steps, and `EnsembleRetriever` can't send different queries to each retriever (see D-09).

### D-03: Cloud LLM (Gemini) instead of local Ollama
- **Context & problem:**
  - The TRD v1 planned a local Qwen2.5-7B through Ollama.
  - The dev laptop's GPU has 4 GB of VRAM, so a 7B Q4 model (~5 GB) only partly fits and runs at about 5-10 tokens/s.
  - Arch's `ollama` package is CPU-only, so the GPU wasn't even detected.
  - The user judged 3B/7B models too weak.
- **Options:** local 3B (fits on the GPU but is weak); local 7B with partial offload (slow); Ollama Cloud; Gemini; Groq; OpenAI or Anthropic (paid).
- **Chosen:** Gemini through `langchain-google-genai` (`ChatGoogleGenerativeAI`). Embeddings, vector and keyword search, and reranking stay local.
- **Why:** It's the strongest model the user can get cheaply on this hardware, with good Hindi/Hinglish ability and native JSON-schema structured output. **Trade-off accepted:** prompts (the question plus at most 5 excerpts) leave the machine. Because Google uses free-tier prompts to improve its products, the free tier is restricted to synthetic or anonymized chats, and real group data needs the paid tier. PRD G8 and §8 and TRD §10 were amended to match. (2026-10-24)

### D-04: Gemini 3.5 Flash-Lite instead of 3.8 Flash
- **Context & problem:** With `gemini-3.8-flash`, single calls took 30-123 s, against a 10 s budget for `/ask`.
- **Investigation:**
  - One HTTP request with no SDK retries, so retries weren't the cause.
  - Network round trip 0.7 s.
  - 0 thinking tokens.
  - Google's own `server-timing` header showed about 123 s on its servers for a 14-token reply.
  - Same key, prompt and network with `gemini-3.5-flash-lite`: 2.6 s server time.
- **Options:** keep 3.8 Flash and re-check later; paid tier (unverified benefit, costs money); switch to Flash-Lite.
- **Chosen:** `llm_model: gemini-3.5-flash-lite`.
- **Why:** Latency. Flash-Lite answered in 2.7-5.9 s with valid structured output. It's a config value, so 3.8 Flash can be re-measured in the Phase 9 eval. Side effects worth knowing: Flash-Lite ignores `temperature` (fixed sampling) and sometimes returns `503 high demand`, which is handled by `llm_max_retries: 4`. (2026-10-24)

### D-05: No fallback LLM
- **Context & problem:** TRD §9 originally fell back to a smaller model on LLM failure.
- **Options:** a local Ollama fallback; a second cloud model; no fallback.
- **Chosen:** No fallback (user decision). Retry with backoff, then return an error.
- **Why:** The user chose simplicity and a single model. A local fallback would need GPU memory that the local embedder and reranker already use (D-06). Accepted risk: a Gemini outage means `/ask` fails.

### D-06: Local BGE-M3 + bge-reranker-v2-m3, fp16 on GPU
- **Context & problem:** Retrieval quality on Hinglish needs multilingual embeddings and a reranker. Loading both in fp32 (~2.3 GB each) caused `CUDA out of memory` on the 3.73 GB card.
- **Options:** run the reranker on CPU (slower); use smaller models (multilingual-e5); load both in fp16; turn the reranker off.
- **Chosen:** Both load in fp16 on CUDA (`model_kwargs={"dtype": float16}`), using 2.28 GB of VRAM together, with an fp32 CPU fallback when there's no GPU. Built once per process in `app/llm/`.
- **Why:** It keeps the TRD's stronger models within the hardware limit with no measurable quality loss. fp16 logits matched fp32 (−10.906 vs −10.902). Keeping these local also keeps the full chat history on the machine (D-03).

### D-07: Reranker outputs raw logits; `min_relevance = -8.0`
- **Context & problem:** With the default sigmoid activation, every score printed as 0.0, which made a no-answer threshold unusable.
- **Investigation:** Raw logits were about −11 for irrelevant pairs and −1.7 to −5.8 for relevant ones. The sigmoid squashes this whole range to between 1e-5 and 0.15.
- **Options:** keep the sigmoid and pick a tiny threshold; use raw logits.
- **Chosen:** `activation_fn=torch.nn.Identity()`. `min_relevance: -8.0` on the logit scale (config).
- **Why:** The logit scale separates the classes readably. **−8.0 is provisional** and gets calibrated on the labeled dev set in Phase 9 (ROADMAP 9.4).

### D-08: Rerank against all query variants, keep the max
- **Context & problem:** bge-reranker scored the Hinglish paraphrase "client ne payment kab bola?" vs "paisa 20 tarikh tak aa jayega" at −10.8, about as low as an irrelevant pair. This is exactly the TRD §15 risk around spelling and synonym variance.
- **Options:** rerank with the original question only; rerank with the rewritten `normalized` query only; score each candidate against the question and every expansion and take the max.
- **Chosen:** Max over `[question, normalized, *expansions]` (`app/query/rerank.py`).
- **Why:** The rewriter's job is to add synonyms ("paisa", "installment"), so using them at rerank time recovers paraphrase matches. It's cheap: 21 pairs score in 0.05 s.

### D-09: Hybrid retrieval: Chroma + custom FTS5 retriever + custom RRF
- **Context & problem:** Vector search alone misses exact tokens (amounts, names), and BM25 alone misses meaning (FR-QA-3).
- **Options:** `EnsembleRetriever`; rank_bm25 in memory; SQLite FTS5; a custom RRF.
- **Chosen:**
  - Chroma retrievers over the question plus each expansion.
  - `FTS5Retriever(BaseRetriever)` over the question plus keywords.
  - A custom `rrf_merge` (k=60) combining them.
- **Why:** FTS5 persists in the same SQLite file as the source of truth, with nothing extra to rebuild in memory. `EnsembleRetriever` can't route different query strings to each retriever. FTS5 queries are built from quoted tokens of the cleaned query, so user input can't inject FTS syntax.

### D-10: Plain (not contentless) FTS5 table
- **Context & problem:** The TRD DDL used `content=''` (contentless).
- **Options:** contentless (smaller, but deletes need the original column values); a regular FTS5 table.
- **Chosen:** A regular `fts5(text_clean, group_id UNINDEXED)` with `rowid = chunks.id`.
- **Why:** Reindexing deletes by `group_id`, and contentless tables make that awkward. At demo scale (≤100k messages) the extra storage doesn't matter.

### D-11: Time-gap + sliding-window chunking, approximate token count
- **Context & problem:** Character splitters ignore conversation boundaries, and single messages ("ok") carry no meaning on their own (FR-IDX-2, 7).
- **Options:** `RecursiveCharacterTextSplitter`; one chunk per message; a time-gap split plus a sliding window.
- **Chosen:**
  - Split at 30-minute gaps, then windows of 10 messages with an overlap of 3.
  - Recursively halve any window over 400 tokens.
  - Merge chunks under 80 characters into a neighbor.
  - Chunk text is `[HH:MM] Sender: msg` with date headers.
- **Why:** It follows conversation structure and tells the embedding who said what. Tokens are estimated at ~4 chars/token instead of with a real tokenizer, because the cap only guards size and loading a tokenizer for this isn't worth it.

### D-12: Custom export parser, DD/MM default
- **Context & problem:** The community `WhatsAppChatLoader` lacks iOS and 12h format detection and doesn't flag system messages.
- **Options:** the community loader; a custom regex parser.
- **Chosen:** `app/ingestion/parser.py`:
  - Android and iOS patterns; whichever matches the most lines wins.
  - Date order auto-detected (any field > 12 decides), defaulting to DD/MM.
  - Invisible characters stripped (`‎`, ` `).
  - Multi-line messages joined; system lines flagged.
- **Why:** FR-ING-2 and 3 coverage. DD/MM is the default because the target users are in India. Known gap: a system line containing `": "` is read as a chat message.

### D-13: Citation pick: formatted-line similarity + time-mention boost
- **Context & problem:** In the first end-to-end run, citations pointed at the *question* message ("Rahul tum report kab tak bhejoge?") instead of the reply ("main kal tak report bhej dunga"). Answer-to-message cosine similarity alone tied them (0.698 vs 0.697 after formatting).
- **Options:** return the top 2 messages per chunk; lexical overlap; embed `[HH:MM] Sender: text`; boost messages whose time the answer quotes.
- **Chosen:** Embed the formatted line, plus a +0.5 boost when the message's `HH:MM` appears in the answer. One message per cited chunk.
- **Why:** The answer prompt instructs the LLM to "mention who said it and when", and real answers quote the exact time, so a quoted time is the most reliable signal. Reproduced with a failing test first and verified on the real stack (Amit 11:14, Rahul 20:15).

### D-14: SQLite + `create_all`; Alembic deferred
- **Context & problem:** The TRD calls for Alembic migrations, but the schema is still changing during MVP work.
- **Options:** Alembic from day one; `create_all` until the first breaking change.
- **Chosen:** `init_db()` = `Base.metadata.create_all` + FTS5 DDL. Relative SQLite paths resolve against the repo root.
- **Why:** Time-to-MVP. There's no production data to migrate yet. **Revisit:** add Alembic before the first schema change once real data exists (ROADMAP 2.1).

### D-15: Rebuild a group's indexes on every import
- **Context & problem:** Incremental upserts need chunk identity tracking. In particular, the last open chunk gets re-embedded as new messages extend it (TRD §5.5).
- **Options:** incremental upserts keyed by `chunk_id`; drop and rebuild the group.
- **Chosen:** `index_group()` deletes the group's chunks, FTS rows, and Chroma collection, then rebuilds everything from `messages`.
- **Why:** It's simple, idempotent, and doubles as `reindex` (TRD §9). Import-only data doesn't need incremental updates. **Revisit** in Phase 4, when live messages arrive every few seconds.

### D-16: Synchronous import; no queue yet
- **Context & problem:** The TRD runs indexing as an RQ job.
- **Options:** add Redis + RQ now; index inside the request.
- **Chosen:** Index inside the `/import` request.
- **Why:** A 49-message import indexes in about 0.4 s, so a queue would add infrastructure with no benefit yet. It moves to RQ in Phase 4 (ROADMAP 4.3), along with live ingestion.

### D-17: Query log written by the endpoint, not a callback handler
- **Context & problem:** TRD §2.5.6 and CLAUDE.md specify a `BaseCallbackHandler` writing to `query_logs`.
- **Options:** a callback handler; a direct insert in the `/ask` endpoint.
- **Chosen:** A direct insert in `routers/groups.py:ask()`. It records chunk ids, latency, model, and prompt version, with no chat text beyond the question and answer.
- **Why:** The MVP only needs one row per request. The privacy goal (local-only telemetry) is met either way. **Revisit** when the eval needs per-stage timings; that's what a callback handler is good at.

### D-18: URL group id = WhatsApp group id; import identities = hashed display name
- **Context & problem:**
  - The gateway knows WhatsApp ids, not internal DB ids.
  - Chat exports contain contact names, not phone numbers.
  - Membership still has to be enforced (FR-BOT-6).
- **Options:** internal integer ids in URLs; WhatsApp ids in URLs; for identity, phone numbers only or a name-based ref for imports.
- **Chosen:**
  - `{wa_group_id}` in paths.
  - User ref = WhatsApp id (contains `@`) for live senders, `name:<display name>` for imported senders.
  - Stored as sha256(salt + ref); phone-like display names masked (`+•••3210`).
- **Why:** It works for both import and (future) live paths without exposing phone numbers (TRD §10). Limitation: the same person appears as two users across import and live until identity linking is built.

### D-19: Tests run on fakes (no network, no GPU)
- **Context & problem:** Real models are slow (10 s load, 4.5 GB download) and Gemini has quotas, but tests must catch real bugs.
- **Options:** mock everything with `MagicMock`; `DeterministicFakeEmbedding` (random-like, so retrieval assertions mean nothing); behavior-preserving fakes.
- **Chosen:**
  - `BagOfWordsEmbeddings`: crc32 word hashing over `clean_text`, so similarity tracks shared words.
  - `OverlapReranker`.
  - `FakeListChatModel`; an empty response list raises if the LLM is called, which proves the not-found path skips it.
  - A per-test SQLite file and a temp Chroma directory.
- **Why:** Retrieval and citation assertions stay meaningful, and the suite runs in about 2 s. The real stack is still verified manually end to end at each milestone.

### D-20: Exact version pins; Python 3.12
- **Context & problem:** LangChain integrations move between packages across releases (TRD §3, §17.7).
- **Chosen:** `==` pins for every dependency in `api/requirements.txt`. The dev venv runs Python 3.12 (the TRD says 3.11; nothing depends on 3.11 specifically).
- **Why:** Reproducibility for the eval and the viva demo. `python-multipart` was added because FastAPI requires it for the upload endpoint.

### D-21: Query rewrite falls back to the raw question
- **Context & problem:** The rewrite costs an extra Gemini call and can fail (503 or malformed JSON).
- **Options:** fail the request; skip the rewrite always; retry, then fall back.
- **Chosen:** `(prompt | llm.with_structured_output(Rewrite)).with_retry(2).with_fallbacks([identity_rewrite])`. It can also be switched off with `query_rewrite_enabled`.
- **Why:** The rewrite improves recall (FR-QA-2, P1) but must never break `/ask` (P0). The toggle doubles as the "with/without rewrite" ablation.

### D-22: Cleaner rules: letters-only repeat collapse, curated variant dictionary
- **Context & problem:** Normalization must unify Hinglish spellings without corrupting retrieval-critical tokens (TRD §5.3.7). TDD caught two real bugs:
  - repeat collapse turned "₹5000" into "₹500";
  - the dictionary mapped "hain" → "hai".
- **Chosen:**
  - Collapse 3+ repeats only for letters (`[^\W\d_]`).
  - Whole-word replacements from `hinglish_norm.yaml`.
  - Ambiguous variants removed: `h`, `ha` (laughter), `hain`.
- **Why:** Amounts, dates, and distinct words must survive cleaning, and a wrong merge hurts recall more than a missed variant.
