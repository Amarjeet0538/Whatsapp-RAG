# Technical Requirements Document: WhatsApp Group Chat RAG Assistant

**Project type:** Final Year B.Tech Project **Version:** 1.0 (Draft) **Companion document:** Product Requirements Document (PRD) v1.0 **Status:** Planning

---

## 1. Introduction

### 1.1 Purpose

This document defines how the system described in the PRD will be built. It specifies the architecture, technology choices, module designs, data schemas, APIs, prompts, performance budgets, testing, and deployment. Functional requirement IDs (FR-xxx) refer to the PRD.

### 1.2 Scope

The TRD covers the v1 system: a WhatsApp bot with semantic Q&A, time-filtered queries, summarization, action item extraction, a decision log, and topic clustering, running fully on local open-source models.

### 1.3 Technical assumptions

- A single development machine runs all services (Docker Compose).
- Primary language of chat content is Hinglish (Roman-script Hindi mixed with English).
- Timezone defaults to IST (Asia/Kolkata).
- Chat volume in demo: up to 5 groups, up to 100,000 messages total.
- Internet access is needed only for the WhatsApp connection and initial model downloads.
- Hardware is unconfirmed; the design is config-driven so models can be swapped for smaller ones.

### 1.4 Definitions

See PRD glossary. Additional terms: **Chunk** (a window of consecutive messages indexed as one unit), **RRF** (Reciprocal Rank Fusion), **Gateway** (the Node.js service connected to WhatsApp), **Core API** (the Python FastAPI backend).

---

## 2. System Architecture

### 2.1 Architectural style

A modular monolith backend (FastAPI) plus one separate gateway service, communicating over HTTP and a message queue. A modular monolith is chosen over microservices to keep the project debuggable by one or two people while still keeping module boundaries clean.

### 2.2 Component diagram

```
+--------------------+        HTTP / Redis queue        +------------------------------+
|  WhatsApp Gateway  | <------------------------------> |         Core API (FastAPI)   |
|  (Node.js)         |                                  |                              |
|  whatsapp-web.js   |                                  |  ingestion  | indexing       |
|  session store     |                                  |  query      | summarizer     |
+--------------------+                                  |  extractors | topics         |
                                                        +--------------+---------------+
                                                                       |
                         +---------------------+-----------------------+----------------+
                         |                     |                       |                |
                  +------v------+       +------v------+         +------v-----+   +------v------+
                  | SQLite /    |       | ChromaDB    |         | Ollama     |   | Redis       |
                  | PostgreSQL  |       | (vectors)   |         | (LLM)      |   | (queue)     |
                  +-------------+       +-------------+         +------------+   +-------------+

                      Worker process (RQ/Celery): indexing, extraction, clustering
```

### 2.3 Components and responsibilities

| Component | Runtime | Responsibility |
| --- | --- | --- |
| Gateway | Node.js 20 | Maintain WhatsApp session, receive messages, parse commands, send replies, forward events to Core API |
| Core API | Python 3.11, FastAPI, Uvicorn | REST endpoints, orchestration of all pipelines |
| Worker | Python (RQ or Celery) | Background jobs: embedding, extraction, clustering |
| Relational DB | SQLite (dev), PostgreSQL 15 (optional) | Messages, users, tasks, decisions, logs |
| Vector DB | ChromaDB (persistent) | Chunk embeddings plus metadata filtering |
| Keyword index | SQLite FTS5 or rank\_bm25 | Lexical search for BM25 retrieval |
| LLM runtime | Ollama | Local generation and structured output |
| Embedding service | sentence-transformers / FlagEmbedding in Core API | BGE-M3 embeddings |
| Queue | Redis 7 | Job queue and gateway-to-API event buffer |

### 2.4 Communication contracts

- Gateway to Core API: HTTP POST (JSON) for events; Core API replies with a message payload for the gateway to send.
- Core API to Worker: queue jobs (Redis).
- Core API to Ollama: HTTP on `localhost:11434`.
- Long-running commands (`/summary`, `/topics`): Core API returns `202 Accepted` with a job ID; the Gateway polls or receives a callback and sends the result when ready.

---

## 3. Technology Stack and Versions

| Layer | Technology | Notes |
| --- | --- | --- |
| Gateway | Node.js 20 LTS, whatsapp-web.js (pin exact version) | Baileys kept as fallback behind the same interface |
| Backend | Python 3.11, FastAPI, Pydantic v2, Uvicorn | Async endpoints |
| LLM runtime | Ollama | Models pulled by name |
| Primary LLM | Qwen2.5-7B-Instruct (Q4\_K\_M) | Config key `LLM_MODEL` |
| Fallback LLMs | Llama-3.1-8B-Instruct, Gemma-2-9B, Qwen2.5-3B (low-resource) | Swappable |
| Embeddings | BAAI/bge-m3 (1024-dim) | Alt: multilingual-e5-large |
| Reranker | BAAI/bge-reranker-v2-m3 | Optional, toggled by config |
| Vector DB | ChromaDB | Behind a `VectorStore` interface; Qdrant as alternative |
| BM25 | rank\_bm25 (in-memory per group) or SQLite FTS5 | FTS5 preferred for persistence |
| ORM / DB access | SQLAlchemy 2.x + Alembic migrations |  |
| Date parsing | dateparser + custom Hinglish rule layer |  |
| Topic modeling | BERTopic, UMAP, HDBSCAN, scikit-learn |  |
| Task queue | RQ (simple) or Celery |  |
| Visualization | matplotlib (PNG output for WhatsApp) |  |
| Testing | pytest, pytest-asyncio, httpx; Jest for gateway |  |
| Tooling | Docker, Docker Compose, Makefile, pre-commit, ruff, black |  |
| Logging | structlog (JSON logs) |  |
| Orchestration framework | Plain Python modules; LangChain or LlamaIndex only for small helpers | Keeps pipeline transparent for the viva |

---

## 4. Environment and Resource Requirements

### 4.1 Hardware profiles

| Profile | Spec | Expected setup |
| --- | --- | --- |
| **A (recommended)** | 16-32 GB RAM, GPU with 8-12 GB VRAM | Qwen2.5-7B Q4, BGE-M3 on GPU, reranker on GPU |
| **B (minimum)** | 16 GB RAM, CPU only | Qwen2.5-3B Q4 or 7B Q4 (slow), embeddings on CPU, reranker off or small |
| **C (constrained)** | 8 GB RAM, CPU only | 3B model, multilingual-e5-base, no reranker, smaller chunk batches |

### 4.2 Approximate resource budget (Profile A)

| Item | Memory |
| --- | --- |
| Qwen2.5-7B Q4\_K\_M | \~5 GB VRAM |
| BGE-M3 | \~2.5 GB (GPU or RAM) |
| Reranker | \~1.5 GB |
| ChromaDB, API, Redis, DB | \~2 GB RAM |
| Gateway (headless Chromium) | \~500 MB-1 GB RAM |

### 4.3 Software prerequisites

Docker and Docker Compose, NVIDIA drivers and container toolkit (if GPU), Git, a spare phone number with WhatsApp installed for the bot.

---

## 5. Module Design

### 5.1 WhatsApp Gateway (FR-ING-4, FR-BOT-\*)

**Responsibilities**

- Authenticate by QR code; persist session (`LocalAuth`) in a Docker volume.
- Listen for `message` events in groups and DMs.
- Normalize each event to the internal schema and POST to `/events/message`.
- Detect commands (messages starting with `/`) and mentions of the bot.
- Send replies, split long text into chunks under \~3,500 characters, and send images (charts).
- Reconnect automatically on disconnect with exponential backoff.
- Write to a local outbox so messages are not lost if the Core API is down.

**Event payload (Gateway to API)**

```json
{
  "wa_message_id": "false_1203630...@g.us_3EB0...",
  "group_wa_id": "1203630...@g.us",
  "sender_wa_id": "9198xxxxxxx@c.us",
  "sender_name": "Rahul",
  "timestamp": "2026-10-08T14:32:10+05:30",
  "text": "kal tak report bhej dunga",
  "reply_to_wa_id": null,
  "is_command": false,
  "has_media": false
}
```

**Abstraction:** a `GatewayAdapter` interface (`onMessage`, `sendText`, `sendImage`) so Baileys can replace whatsapp-web.js without touching the rest of the gateway.

### 5.2 Chat export parser (FR-ING-1 to 3)

**Supported formats**

- Android: `12/03/2026, 14:05 - Rahul: message`
- iOS: `[12/03/26, 2:05:13 PM] Rahul: message`
- 12h and 24h clocks; `DD/MM` vs `MM/DD` auto-detected by scanning all dates in the file (a value above 12 reveals the field order).

**Algorithm**

1. Read file as UTF-8 (handle BOM).
2. Match each line against a set of regex patterns; the first pattern that matches 80%+ of lines is selected.
3. Lines that do not start with a timestamp are appended to the previous message (multi-line support).
4. Classify system lines ("X joined", "messages are end-to-end encrypted", "\<Media omitted>", "This message was deleted") and mark `is_system = true`.
5. Resolve sender names to user IDs (map contact names to hashed IDs).
6. Return a list of normalized messages; insert in batches of 1,000.

**Deduplication key:** `sha1(group_id + timestamp + sender + text_raw)`. Live-captured messages use the same key so imports never duplicate them.

### 5.3 Text preprocessing (FR-IDX-1)

Two text fields are kept: `text_raw` (displayed to users) and `text_clean` (used for indexing).

**Cleaning steps for `text_clean`**

1. Unicode NFKC normalization.
2. Lowercase.
3. Collapse character repetition: 3 or more repeats reduce to 2 ("haaaaan" to "haan").
4. Replace URLs with `<url>`, phone numbers with `<phone>`.
5. Convert emojis to short text descriptions where meaningful (e.g., "thumbs up") using the `emoji` library; drop decorative ones.
6. Apply a Hinglish normalization dictionary (maintained as a YAML file): e.g., `kb, kab, kub` to `kab`; `nhi, nahi, nai` to `nahi`; `hn, haan, han` to `haan`; `kl, kal` to `kal`. Dictionary can be extended from corpus statistics.
7. Preserve numbers, amounts, dates, and names untouched (they matter for exact retrieval).

**Note:** normalization is applied to indexed text and queries identically so both sides land in the same space.

### 5.4 Chunking (FR-IDX-2, 3, 7)

**Strategy: time-gap segmentation plus sliding window**

1. Sort messages by timestamp within a group.
2. Split into conversations wherever the gap between messages exceeds `CHUNK_GAP_MINUTES` (default 30).
3. Within each conversation, create windows of `WINDOW_SIZE` messages (default 10) with `WINDOW_OVERLAP` (default 3).
4. Enforce a token cap (`MAX_CHUNK_TOKENS`, default 400); split further if exceeded.
5. Build chunk text in the format `[HH:MM] Sender: message` per line, with the date as a header line, so the embedding sees who said what.
6. Merge any chunk shorter than `MIN_CHUNK_CHARS` (default 80) into the neighbor.

**Chunk record:** `chunk_id`, `group_id`, `start_ts`, `end_ts`, `participants[]`, `message_ids[]`, `text`.

Messages that are system messages or media placeholders are excluded from chunk text.

### 5.5 Embedding and indexing (FR-IDX-4 to 6)

- Model: BGE-M3, dense vectors (1024-dim), normalized; batch size 32 (GPU) or 8 (CPU).
- Vector store collection per group: `grp_<group_id>`. Metadata stored with each vector: `start_ts` and `end_ts` as integer epoch seconds (required for range filters), `participants` as a joined string, `message_count`.
- Indexing runs as a worker job. Imports queue all chunks; live messages are accumulated and indexed when either 10 new messages arrive or 60 seconds pass.
- Idempotent upserts keyed by `chunk_id`; the last open chunk for a group is re-embedded when new messages extend it.
- A `VectorStore` interface (`upsert`, `query`, `delete_group`) hides the Chroma specifics.
- BM25: SQLite FTS5 virtual table over `text_clean` of chunks with `group_id` as an unindexed column.

### 5.6 Query pipeline (FR-QA-\*)

```
question -> intent classifier -> time parser -> query rewriter
         -> (vector top-K, BM25 top-K) -> RRF merge -> reranker -> context builder
         -> LLM answer (grounded) -> citation attach -> reply
```

**Intent classification** Rule-based first (slash commands map directly). For free text, a lightweight LLM call returns one of `ask | summary | tasks | decisions | topics | help | chitchat` as JSON. Fallback is `ask`.

**Query rewriting (FR-QA-2)** LLM prompt returns JSON: `{ "normalized": "...", "expansions": ["...", "..."], "keywords": ["..."] }`. The normalized query and expansions are each embedded; vector results are unioned. Keywords feed BM25.

**Retrieval parameters (config)**

- `VECTOR_TOP_K = 20`, `BM25_TOP_K = 20`
- RRF: `score = sum(1 / (60 + rank_i))`
- `RERANK_TOP_N = 20`, `FINAL_TOP_K = 5`
- Apply metadata filter (group, and time range if present) in both vector and BM25 queries.
- Context expansion: for each final chunk, optionally include one neighboring chunk before and after when the token budget allows.

**Grounded answer prompt (template)**

```
SYSTEM:
You answer questions about a WhatsApp group chat. Use ONLY the chat excerpts provided.
The chat is in English, Hindi (Roman script), or Hinglish. Reply in the same style as the question.
If the excerpts do not contain the answer, reply exactly: NOT_FOUND.
Be concise. Mention who said it and when. Do not invent names, dates, or numbers.
After the answer, list the excerpt numbers you used as: SOURCES: [1,3]

USER:
Question: {question}
Current date: {today}

Excerpts:
[1] ({date}, {participants})
{chunk_text}
...
```

**Post-processing**

1. Parse `SOURCES` and map to chunk metadata.
2. For each source, pick the 1-2 most relevant messages (highest embedding similarity to the answer) and show sender, timestamp, and a snippet.
3. If the model returns `NOT_FOUND`, send the no-answer message instead.
4. Temperature 0.1; max output tokens 400.

**No-answer safeguard (FR-QA-7):** if the best reranker score is below `MIN_RELEVANCE` (calibrated on the dev set), skip generation and return the no-answer response.

### 5.7 Time-filtered queries (FR-TIME-\*)

**Pipeline:** detect, resolve, filter.

1. **Detection:** regex and keyword rules for English and Hinglish terms: `aaj`, `kal` (ambiguous: yesterday or tomorrow; resolve by verb tense, with a default of yesterday for queries about past discussion), `parso`, `pichhle hafte`, `is mahine`, `last week`, `past 3 days`, `in March`, `between X and Y`.
2. **Resolution:** convert to `(start_ts, end_ts)` in IST using `dateparser` with `RELATIVE_BASE = now` and a custom rule table for Hinglish phrases. Week boundaries use Monday start.
3. **Filter:** pass epoch-second range into vector `where` clause (`start_ts <= end` and `end_ts >= start`) and into the FTS5 SQL query.
4. **Echo:** the reply begins with "Showing results from {start} to {end}".
5. If a time phrase is detected but resolution fails, ask the user to clarify rather than silently searching everything.
6. The LLM is never trusted to compute dates; all resolution is done in code.

### 5.8 Summarization (FR-SUM-\*)

**Range selection**

- `unread`: messages with `timestamp > last_seen_at` for the user in that group.
- `last N`, `last X hours/days`, custom range.

**Algorithm (map-reduce)**

1. Fetch messages in range; drop system messages.
2. If the transcript is under `SUMMARY_DIRECT_TOKENS` (default 3,000), summarize in a single call.
3. Otherwise **map:** split into segments of about 1,500 tokens along conversation boundaries; summarize each segment into bullets, keeping names, numbers, and dates.
4. **Reduce:** combine segment summaries into the final structured summary. If the combined text is still too long, reduce recursively.
5. Output format by length option: short (3-5 lines), standard (overview, key topics, updates, open questions), detailed (adds per-topic sections).
6. Update `last_seen_message_id` and `last_seen_at` only after the summary is delivered successfully.

**Final-summary schema**

```json
{
  "overview": "string",
  "key_topics": ["string"],
  "important_updates": ["string"],
  "open_questions": ["string"],
  "mentions_of_requester": ["string"]
}
```

The bot renders this into WhatsApp formatting (bold headings with `*text*`, bullet lines).

### 5.9 Action item extraction (FR-ACT-\*)

**Trigger:** worker job after indexing, processing chunks that have not been extracted (tracked by `extraction_state`).

**LLM prompt** (few-shot with Hinglish examples) produces JSON validated against this schema:

```json
{
  "items": [
    {
      "task": "send the report",
      "owner_name": "Rahul",
      "deadline_text": "kal tak",
      "source_message_index": 4,
      "type": "commitment",
      "confidence": 0.86
    }
  ]
}
```

`type` is one of `commitment` (someone promises), `assignment` (someone is told to do it), or `request`.

**Post-processing (in code)**

1. Validate JSON with Pydantic; retry once on failure with an error hint; skip on second failure and log it.
2. Map `owner_name` to a user ID (fuzzy match on group members; "I"/"main"/"me" resolve to the message sender).
3. Convert `deadline_text` to an absolute date using the source message timestamp as the base (reuse the time parser).
4. Drop items below `ACTION_MIN_CONFIDENCE` (default 0.6).
5. De-duplicate: same owner, similarity of task text above 0.85 (embedding cosine), and deadlines within 24 hours are merged.
6. Completion detection (P1): when a later message says "done", "bhej diya", "sent", a lightweight check against open items of that sender suggests closure; the bot asks for confirmation instead of closing automatically.

### 5.10 Decision log (FR-DEC-\*)

Same pipeline pattern as action items with a separate prompt and schema:

```json
{
  "decisions": [
    {
      "decision": "Team meeting fixed for Saturday 5 PM",
      "topic": "meeting schedule",
      "participants": ["Rahul", "Riya"],
      "source_message_indexes": [3, 5, 6],
      "confidence": 0.9
    }
  ]
}
```

- A decision requires agreement or a conclusive statement; proposals alone are excluded (prompt rule plus few-shot negatives).
- Override detection (P2): when a new decision has high similarity to an older one on the same topic, mark the older as superseded.

### 5.11 Topic clustering (FR-TOP-\*)

1. Collect chunk embeddings for the group (optionally over a date range).
2. UMAP (n\_neighbors=15, n\_components=5, cosine) then HDBSCAN (min\_cluster\_size scaled to data size). KMeans fallback if HDBSCAN returns mostly noise.
3. Extract top terms per cluster with c-TF-IDF (BERTopic).
4. **Label generation:** LLM receives top terms plus 3 representative chunks and returns a 2-4 word label.
5. Compute per-topic message counts, percentage share, and weekly volume.
6. Render a horizontal bar chart (top 8 topics) and, optionally, a topic-over-time chart with matplotlib; send as an image.
7. Persist results in `topics` and refresh nightly or on `/topics refresh`.

### 5.12 Command router and bot logic (FR-BOT-\*)

- Parsing: first token starting with `/` is the command; the remainder is the argument string.
- Authorization: the sender must be a member of the target group (checked against `memberships`). In DMs the user selects a group with `/group`; the active group is stored per user.
- Rate limiting: max 10 requests per user per minute; one heavy job (summary, topics) at a time per user.
- Feedback: send a short "working on it..." message for jobs expected to exceed 5 seconds.
- Formatting helpers for WhatsApp markdown (`*bold*`, `_italic_`, monospace) and message splitting.

---

## 6. Data Design

### 6.1 Relational schema (SQLAlchemy-compatible DDL)

```sql
CREATE TABLE groups (
  id INTEGER PRIMARY KEY,
  wa_group_id TEXT UNIQUE NOT NULL,
  name TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  wa_id_hash TEXT UNIQUE NOT NULL,
  display_name TEXT
);

CREATE TABLE memberships (
  user_id INTEGER REFERENCES users(id),
  group_id INTEGER REFERENCES groups(id),
  last_seen_message_id INTEGER,
  last_seen_at TIMESTAMP,
  PRIMARY KEY (user_id, group_id)
);

CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  sender_id INTEGER REFERENCES users(id),
  ts TIMESTAMP NOT NULL,
  text_raw TEXT NOT NULL,
  text_clean TEXT,
  is_system BOOLEAN DEFAULT 0,
  reply_to_id INTEGER,
  source TEXT CHECK (source IN ('import','live')),
  dedup_key TEXT UNIQUE NOT NULL
);
CREATE INDEX idx_messages_group_ts ON messages(group_id, ts);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  start_ts TIMESTAMP, end_ts TIMESTAMP,
  participants TEXT,
  message_ids TEXT,          -- JSON array
  text TEXT NOT NULL,
  extracted INTEGER DEFAULT 0 -- extraction_state flag
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(text_clean, group_id UNINDEXED, content='');

CREATE TABLE action_items (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL,
  task TEXT NOT NULL,
  owner_id INTEGER REFERENCES users(id),
  deadline TIMESTAMP,
  status TEXT DEFAULT 'open' CHECK (status IN ('open','done','dismissed')),
  item_type TEXT,
  confidence REAL,
  source_message_ids TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);

CREATE TABLE decisions (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL,
  decision_text TEXT NOT NULL,
  topic TEXT,
  decided_on TIMESTAMP,
  participants TEXT,
  source_message_ids TEXT,
  confidence REAL,
  supersedes_id INTEGER REFERENCES decisions(id)
);

CREATE TABLE topics (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL,
  label TEXT,
  keywords TEXT,
  chunk_ids TEXT,
  message_count INTEGER,
  share_pct REAL,
  computed_at TIMESTAMP
);

CREATE TABLE query_logs (
  id INTEGER PRIMARY KEY,
  group_id INTEGER, user_id INTEGER,
  query TEXT, intent TEXT, filters TEXT,
  retrieved_chunk_ids TEXT, answer TEXT,
  latency_ms INTEGER, model TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 Vector store layout

- One collection per group; distance metric: cosine.
- ID: `chunk_<id>`; document: chunk text; embedding: BGE-M3 dense vector.
- Metadata: `group_id`, `start_ts` (int), `end_ts` (int), `participants`, `message_count`.

### 6.3 Data lifecycle

- Group purge (`/purge`, admin only) deletes the group's rows, FTS entries, and vector collection.
- Raw `.txt` uploads are deleted after successful parsing.
- Backups: periodic copy of the SQLite file and Chroma directory (development convenience).

---

## 7. API Specification (Core API)

Base path `/api/v1`. All requests are JSON. The Gateway authenticates with a shared secret in `X-API-Key`.

| Method | Endpoint | Purpose | Related FR |
| --- | --- | --- | --- |
| POST | `/events/message` | Ingest a live message; may return a reply if it was a command | FR-ING-4 |
| POST | `/groups/{id}/import` | Upload a `.txt` export (multipart) | FR-ING-1 |
| GET | `/jobs/{job_id}` | Poll status/result of a background job | FR-BOT-3 |
| POST | `/groups/{id}/ask` | Body: `{question, user_id}`; returns answer and sources | FR-QA-\* |
| POST | `/groups/{id}/summary` | Body: `{user_id, mode, value, length}` | FR-SUM-\* |
| GET | `/groups/{id}/tasks` | Query: `owner`, `status`, `overdue` | FR-ACT-5 |
| POST | `/tasks/{id}/done` | Mark done | FR-ACT-6 |
| GET | `/groups/{id}/decisions` | Query: `topic`, `from`, `to` | FR-DEC-3 |
| GET | `/groups/{id}/topics` | Query: `from`, `to`, `refresh` | FR-TOP-3 |
| DELETE | `/groups/{id}` | Purge group data | Privacy |
| GET | `/health` | Health of API, DB, vector store, Ollama | NFR |

**Ask response example**

```json
{
  "answer": "Client ne bola tha ki delivery 15 November tak ho jayegi.",
  "found": true,
  "interpreted_range": null,
  "sources": [
    { "sender": "Amit (Client)", "ts": "2026-10-02T11:14:00+05:30",
      "snippet": "delivery 15 nov tak pakka ho jani chahiye" }
  ],
  "latency_ms": 4120
}
```

**Error format:** `{ "error": { "code": "GROUP_NOT_FOUND", "message": "..." } }` with appropriate HTTP status.

---

## 8. Configuration Management

All tunables live in `config.yaml` with environment overrides (`.env`). Key settings:

| Key | Default | Purpose |
| --- | --- | --- |
| `LLM_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | Ollama model tag |
| `LLM_TEMPERATURE` | 0.1 | Generation determinism |
| `LLM_CTX` | 8192 | Context window |
| `EMBED_MODEL` | `BAAI/bge-m3` | Embedding model |
| `RERANKER_ENABLED` | true | Toggle reranker |
| `CHUNK_GAP_MINUTES` | 30 | Conversation split gap |
| `WINDOW_SIZE` / `WINDOW_OVERLAP` | 10 / 3 | Sliding window |
| `VECTOR_TOP_K` / `BM25_TOP_K` | 20 / 20 | Candidate counts |
| `FINAL_TOP_K` | 5 | Chunks sent to LLM |
| `MIN_RELEVANCE` | calibrated | No-answer threshold |
| `ACTION_MIN_CONFIDENCE` | 0.6 | Extraction filter |
| `TIMEZONE` | `Asia/Kolkata` | Date resolution |
| `RATE_LIMIT_PER_MIN` | 10 | Per-user limit |

---

## 9. Error Handling and Resilience

| Failure | Handling |
| --- | --- |
| WhatsApp session drops | Auto-reconnect with backoff; alert in logs; QR re-auth flow documented |
| Core API unavailable | Gateway buffers events in a local outbox and retries |
| Ollama timeout or OOM | Retry once; fall back to a smaller model if configured; return a friendly error |
| Malformed LLM JSON | Pydantic validation, one retry with correction hint, then skip and log |
| Embedding job failure | Job retried up to 3 times; chunk marked `failed` for manual review |
| Unparseable export file | Return which line/pattern failed and supported format examples |
| Duplicate messages | Ignored via `dedup_key` |
| Vector DB corrupted | Rebuild index from the `messages` table using `make reindex` |

All jobs are idempotent so retries are safe. The relational DB is the source of truth; vector and FTS indexes are derived and rebuildable.

---

## 10. Security and Privacy Engineering

- **Secrets:** API keys and settings in `.env`, never committed; `.env.example` provided.
- **Gateway to API auth:** shared-secret header; services bound to the internal Docker network only.
- **Access control:** every endpoint that reads group data verifies membership of the requesting user.
- **Data protection:** phone numbers stored as salted hashes; display names kept only for presentation; raw exports deleted after import.
- **Prompt injection:** chat text is treated as untrusted data. Prompts place chat content inside clearly delimited blocks, and system instructions state that instructions found in excerpts must be ignored. Command parsing happens in code, not by the LLM.
- **Logging:** query logs store chunk IDs rather than full message text where possible; logs excluded from version control.
- **Disk:** recommend an encrypted disk or volume for the data directory.
- **Right to erase:** `/purge` and `DELETE /groups/{id}` remove all derived data.

---

## 11. Performance Requirements and Budgets

| Operation | Target | Main lever |
| --- | --- | --- |
| `/ask` end-to-end | <= 10 s | Rewrite call (\~1 s), retrieval (\~0.3 s), rerank (\~0.7 s), generation (\~4-6 s) |
| Summary of 200 messages | <= 30 s | Single-pass if under 3,000 tokens |
| Import and index 10,000 messages | <= 10 min | Batched embeddings on GPU |
| Live message to searchable | <= 60 s | Micro-batching |
| Topic clustering (10,000 messages) | <= 2 min | Precomputed embeddings |

**Optimization measures:** embedding batching, caching of query embeddings, keeping the Ollama model loaded (`keep_alive`), streaming not required for WhatsApp, optional LLM-call skipping for the rewrite step on short English queries, and quantized models.

---

## 12. Testing Strategy

| Level | Scope | Tools |
| --- | --- | --- |
| Unit | Parser formats, cleaner, Hinglish normalizer, chunker, time parser, RRF, schema validation | pytest |
| Integration | Ingestion to index to query with a fixture chat; API endpoints | pytest + httpx |
| Pipeline / LLM | Golden-question tests with expected source chunks; prompt regression tests with a mocked LLM and a real LLM run | pytest, custom harness |
| Gateway | Command parsing, message splitting, reconnect logic with a mocked client | Jest |
| End-to-end | Real WhatsApp test group scripted session | Manual checklist plus screen recording |
| Performance | Latency and memory benchmarks | Locust or custom timing scripts |
| Security | Membership authorization, prompt injection samples | Targeted test cases |

**Key test cases**

- Parser: Android 24h, Android 12h, iOS, multi-line messages, emoji, system lines, different date orders.
- Time parser: "pichhle hafte", "is mahine", "last 3 days", boundary dates, month names in Hinglish.
- Retrieval: a query using different wording than the source ("payment kab milega" against "paisa 20 tarikh tak aa jayega").
- No-answer: questions about topics never discussed must return not-found.
- Extraction: sarcasm, jokes, and hypothetical statements must not create tasks.
- Authorization: a non-member must never receive group content.

Target unit-test coverage for core modules: 70% or higher.

---

## 13. Evaluation Implementation

The evaluation harness is a standalone package (`/eval`) that runs against the same pipeline code.

- **Datasets:** `qa.jsonl` (question, gold chunk or message IDs, language tag), `actions.jsonl`, `decisions.jsonl`, `summaries.jsonl`.
- **Retrieval benchmark:** runs configurations (BM25 only, vector only, hybrid, hybrid + rerank, with and without rewrite) and reports Recall@1/3/5/10, MRR, nDCG.
- **Generation benchmark:** faithfulness scored with a rubric prompt to a judge model plus a manual check on a sample; no-answer accuracy on out-of-scope questions.
- **Extraction benchmark:** precision, recall, F1 using fuzzy match of task text and exact match of owner and date.
- **Summary evaluation:** human ratings via a simple form, plus ROUGE-L and BERTScore as secondary measures.
- **Reproducibility:** fixed random seeds, pinned model versions, and results written to `eval/results/<date>.json`.
- **Synthetic data:** a script generates Hinglish group conversations from templates and an LLM, followed by manual correction. Roughly 20% is manually audited.

---

## 14. Deployment and Project Structure

### 14.1 Docker Compose services

`gateway`, `api`, `worker`, `redis`, `ollama`, and optionally `postgres`. Volumes: `wa_session`, `chroma_data`, `db_data`, `ollama_models`. GPU access is enabled for `ollama`, `api`, and `worker` via the NVIDIA runtime when available.

### 14.2 Repository layout

```
whatsapp-rag/
  gateway/            # Node.js bot
    src/adapters/
    src/commands/
  api/
    app/main.py
    app/routers/
    app/ingestion/    # parser, cleaner
    app/indexing/     # chunker, embedder, vector_store
    app/query/        # intent, time_parser, rewriter, retriever, reranker, answerer
    app/summarize/
    app/extract/      # actions, decisions
    app/topics/
    app/models/       # SQLAlchemy models, schemas
    app/prompts/      # versioned prompt templates
    app/config.py
  worker/
  eval/
  data/               # sample/synthetic chats (anonymized)
  docs/               # PRD, TRD, report
  docker-compose.yml
  Makefile
  config.yaml
```

### 14.3 Developer workflow

- Git with feature branches and pull requests (even if solo, for history in the report).
- `make up`, `make test`, `make reindex`, `make eval`, `make seed` shortcuts.
- Prompts versioned as files; each query log records the prompt version for traceability.

---

## 15. Technical Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Unofficial library breaks or account is banned | Adapter interface, pinned versions, spare number, `.txt` import as backup demo path |
| 7B model produces weak Hinglish output | Test Qwen, Llama, Gemma on the dev set; allow model switch via config; add few-shot examples |
| Hinglish spelling variance reduces recall | Normalization dictionary, BGE-M3, BM25 fuzzy variants, query expansion |
| LLM-based extraction yields many false positives | Confidence filter, negative few-shot examples, evaluation on labeled data, user confirmation for suggested completions |
| GPU memory contention between LLM and embedding models | Sequential model usage, CPU offload for reranker, smaller quantization |
| Clustering gives noisy topics on small groups | Minimum-data threshold, KMeans fallback, LLM label cleanup |
| Context window overflow in summaries | Token counting before each call, recursive map-reduce |
| Time-zone and date-order bugs | Single timezone config, tests for edge dates, date-order auto-detection |

---

## 16. Requirements Traceability

| PRD requirement group | TRD section |
| --- | --- |
| FR-ING (ingestion) | 5.1, 5.2, 6.1 |
| FR-IDX (indexing) | 5.3, 5.4, 5.5, 6.2 |
| FR-QA (search and Q&A) | 5.6 |
| FR-TIME (time filters) | 5.7 |
| FR-SUM (summaries) | 5.8 |
| FR-ACT (action items) | 5.9 |
| FR-DEC (decisions) | 5.10 |
| FR-TOP (topics) | 5.11 |
| FR-BOT (bot interface) | 5.1, 5.12 |
| Non-functional: performance | 11 |
| Non-functional: privacy and security | 10 |
| Non-functional: reliability | 9 |
| Evaluation plan | 13 |

---

## 17. Open Technical Decisions

1. Final LLM choice after benchmarking Qwen2.5-7B, Llama-3.1-8B, and Gemma-2-9B on the Hinglish dev set.
2. SQLite FTS5 versus rank\_bm25 for the keyword index (FTS5 preferred for persistence; confirm tokenizer behavior on Hinglish).
3. Whether the reranker fits within hardware limits, or is replaced by a lighter cross-encoder.
4. RQ versus Celery for background jobs (RQ is simpler and sufficient at this scale).
5. Whether to use a PostgreSQL service for the demo or stay on SQLite.
6. Confirmed hardware profile (A, B, or C from Section 4.1).
