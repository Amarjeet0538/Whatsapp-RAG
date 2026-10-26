# Feature Trail

Start-to-finish records of every feature. Write the goal **before** starting, then log the trail as work proceeds. Bugs hit along the way go in `Bug.md` (BUG-xx), and the reasoning behind choices goes in `Decisions.md` (D-xx).

Format: **Context** (what is being built, and why) · **Investigation / Steps** · **Blockers** · **Resolution** (changes + verification) · **Status**.

_FEAT-01 to FEAT-04 were backfilled on 2026-10-25. Commit refs: `7a59a51` (skeleton), `b90736a` (config/env), `cdb5191` (MVP)._

---

## Index

| ID | Feature | ROADMAP | Status |
| --- | --- | --- | --- |
| FEAT-01 | Implementation roadmap | — | Done |
| FEAT-02 | LLM provider: Gemini + environment setup | 1.2 | Done |
| FEAT-03 | HTTP RAG MVP: import + ask with citations | Phases 1-3 | Done (with open items) |
| FEAT-04 | Living documentation set | — | Done |
| FEAT-05 | WhatsApp gateway | 4.1 | **Next**, not started |
| FEAT-06 | Web demo UI | 3.8 | Done (not committed) |

---

### FEAT-01: Implementation roadmap
- **Context:** The PRD and TRD said what and how, but not in what order, and there was no "where are we" marker. Goal: one ordered plan tied to PRD FR-IDs and TRD sections, with a "done when" check for every step.
- **Investigation / Steps:** Read PRD (501 lines) and TRD (801 lines) in full, plus the existing code (`config.py`, the `/health` stub, empty Makefile and compose file) and `TODO.md`. Checked the environment: Ollama installed but not running; only `fastapi` in the venv.
- **Resolution:** Created `docs/ROADMAP.md` with 10 phases following the PRD §15 timeline. Each step lists files, references, and a done-when check, and there's a "You are here" banner. Added a pointer to it in CLAUDE.md.
- **Status:** Done (2026-10-24). The roadmap is kept current as steps finish.

### FEAT-02: LLM provider: Gemini + environment setup (ROADMAP 1.2)
- **Context:** The planned local Ollama/Qwen setup didn't work on the hardware (BUG-01), and the user wanted a stronger model. Goal: a working cloud LLM through LangChain, plus pinned dependencies and lint tooling.
- **Investigation / Steps:**
  1. Compared local options (3B fits the GPU but is weak; 7B is slow) with cloud options (Ollama Cloud, Gemini, Groq, OpenAI/Anthropic). The user chose Gemini Flash, with no fallback (D-03, D-05).
  2. Looked up current model ids and pricing. The free tier allows Google to train on prompts, so it's restricted to synthetic or anonymized data.
  3. Replaced Ollama with Gemini across PRD, TRD, CLAUDE.md, config, `.env.example`, and requirements.
  4. Tested the key: plain text and structured output both worked, but slowly (BUG-03).
  5. Installed and pinned all Phase 1 dependencies. torch sees CUDA.
- **Blockers:** BUG-02 (`thinking_level` minimal rejected), BUG-03 (30-123 s latency, which forced a model change), BUG-04 (intermittent 503s).
- **Resolution:**
  - `llm_provider/llm_model/llm_max_tokens/llm_thinking_level/google_api_key` in `config.yaml` and `Settings`.
  - Model `gemini-3.5-flash-lite`.
  - `api/requirements.txt` fully `==`-pinned.
  - `pyproject.toml` with ruff + black + pytest.
  - Verified: Hinglish text and `with_structured_output` calls at 2.7-5.9 s, and `ruff check` / `black --check` pass.
- **Status:** Done (2026-10-24, `b90736a`).

### FEAT-03: HTTP RAG MVP: import + ask with citations (ROADMAP Phases 1-3)
- **Context:** Goal: the smallest end-to-end product that proves the core value (PRD G1, G7). Upload a WhatsApp `.txt` export, then ask a Hinglish or English question and get a grounded answer with cited source messages, or an honest not-found. Scope was set to HTTP only: the WhatsApp gateway needs the user's phone for QR login, so it's Phase 4.
- **Investigation / Steps:** Built in 10 thin vertical slices, each test-first (red, then green), with the full suite and lint run after each:
  1. **Config keys** (1.3): TRD §8 keys added, plus `llm_max_retries`, `embed_batch_size`, `query_rewrite_enabled`, `id_hash_salt`. Tests check env override and that the YAML keys match `Settings`.
  2. **Model factories** (1.4): `app/llm/` with fail-fast on a missing key and the reranker toggle. Real models verified on the GPU after BUG-05 and BUG-06.
  3. **DB layer** (2.1): SQLAlchemy models, FTS5 DDL, repo-root-relative SQLite path. Tests cover FTS match and dedup uniqueness.
  4. **Parser** (2.2): Android/iOS, 12h/24h with narrow-nbsp, date-order detection, BOM, multi-line messages, system lines, and an error message that lists supported formats.
  5. **Cleaner** (2.3): table-driven tests caught BUG-08 and BUG-09.
  6. **Chunker** (2.4): gap split, window/overlap, system exclusion, short merge, text format, token cap.
  7. **Ingestion + indexing** (2.2, 2.5): wrote a synthetic sample chat `data/samples/college_project_android.txt` (49 lines with known facts). Then: import with dedup and hashed identities, `index_group()` rebuilding chunks + FTS5 + Chroma, and `FTS5Retriever` with group isolation.
  8. **Query units** (3.1-3.5): RRF (hand-computed expected scores), answer parsing, delimited excerpts, rerank max over query variants (from BUG-07).
  9. **Ask chain** (3.6): LCEL `build_ask_chain()` with the rewrite fallback. Tests use a bag-of-words fake embedding and a fake LLM that raises if called, which proves the not-found path skips the LLM.
  10. **HTTP API** (2.6, 3.6): import/ask/health routers, `X-API-Key`, error envelope, membership check (403), and `query_logs`. Ruff config allows FastAPI's `Depends` idiom.
  - **End-to-end check on the real stack:** uvicorn with a throwaway DB, Chroma dir and API key; real BGE-M3 and reranker on the GPU; real Gemini. This found BUG-10 (wrong citations), which was fixed test-first and re-verified.
- **Blockers:** BUG-05 (GPU OOM), BUG-06 (reranker scores showing 0.0), BUG-07 (Hinglish paraphrase), BUG-08/09 (cleaner), BUG-10 (citations), BUG-11 (python-multipart).
- **Resolution:**
  - Files: `api/app/{db,models,llm,ingestion,indexing,query,prompts,routers}/`, `deps.py`, `errors.py`, `main.py`; `api/tests/` (11 files, 56 tests); `Makefile` (`run/test/lint/format`); README "Try the MVP"; ROADMAP/TRD/TODO/CLAUDE.md status updates. Commit `cdb5191` ("MVP done").
  - Verification: `make test` 56 passed, and `make lint` is clean. On the real stack:
    - 5 of 5 sample questions were answered with the correct cited message (payment, report owner, meeting place, login theme, deploy platform).
    - An out-of-scope question returned not-found.
    - A non-member got 403.
    - Re-import added 0 messages.
    - Latency was 3.0-6.5 s.
- **Status:** Done (2026-10-24). **Open items** (ROADMAP `[~]`): Alembic (D-14), `make reindex` CLI, intent classifier (moved to 4.2), `qa.jsonl` + synthetic generator + iOS sample, `min_relevance` calibration, friendly error on Gemini failure in the answer step, callback-based query logging (D-17).

### FEAT-04: Living documentation set
- **Context:** The user added documentation rules to CLAUDE.md, so every change must keep Architecture, Flow, Decisions, and Bug/Feature trails current. Goal: backfill them for all work so far, so nothing has to be reconstructed from chat history.
- **Investigation / Steps:** Re-read the code (every module's functions and routes), git history (`7a59a51`, `b90736a`, `cdb5191`), the working tree, and the existing docs. Where a doc claim went beyond the evidence, I reworded it (for example, only reranking had been timed, not retrieval).
- **Resolution:** Created `docs/Architecture.md`, `docs/Flow.md`, `docs/Decisions.md` (D-01 to D-22), `docs/Bug.md` (BUG-01 to BUG-11), and `docs/Feature.md` (this file). Found one inconsistency: CLAUDE.md says query logs go "through a callback handler" while the code logs from the endpoint (D-17). It's flagged to the user and still open.
- **Status:** Done (2026-10-25).

### FEAT-06: Web demo UI (ROADMAP 3.8)
- **Context:** The user wants a visible, modern frontend to chat with the assistant for the final-year evaluation, with strict rules against generic AI-made design (no purple gradients, pill buttons, fake reviews or metrics, vague hero text, emoji, em dashes, over-the-top animation).
- **Investigation / Steps:**
  - Brainstormed with the user (AskUserQuestion + browser mockups): purpose = evaluation demo; screens = import, group switcher, chat with citations, pipeline inspector; React + Vite + TS; proxy-injected key with an "Ask as" member picker; per-tab history; no streaming; citation opens surrounding messages; light + dark; two processes. Layout A (three columns, inspector always visible) and style "Ledger" picked from mockups.
  - Spec `docs/superpowers/specs/2026-10-26-web-demo-design.md`, plan `docs/superpowers/plans/2026-10-26-web-demo.md` (8 tasks, TDD).
  - Backend: `GET /groups`, `GET /groups/{id}/members`, context endpoint, `Source.message_id`, `trace` on `/ask` (D-26, D-27, D-28). The plan's member counts (16/7) were wrong: the sample's `<Media omitted>` and deleted message are system messages, so the counts are 15/6.
  - Frontend: `web/` (D-24, D-25). Component tests for AnswerBlock and InspectorPane were run red against null stubs before the components were written.
- **Blockers:**
  - `npm install` could not reach the registry from the Claude Code sandbox (TLS EOF), and an unsandboxed retry was denied. The user ran the install in their own terminal (with `--dns-result-order=ipv4first`) and approved esbuild's install script.
  - The sandbox also blocks loopback, and browser tools were declined, so the real-browser check is handed to the user (checklist in the final report).
- **Resolution (files):** `api/app/routers/groups.py`, `api/app/models/schemas.py`, `api/app/query/{chain,citations,trace}.py`, `api/tests/{test_api,test_query_units}.py`, `web/**`, `Makefile` (`web-install`, `web`, `web-test`), `.gitignore`.
- **Final review (fresh Opus reviewer):** fixed, each with a test run red first:
  - A late answer overwrote another group's thread after a group switch (Critical). Fixed with the `useThreads` per-group store, where every update names its group.
  - `[n]` was mapped by list position. Fixed with `Source.excerpt`.
  - A plain-text 500 was shown as "API not reachable". It now reports "The API failed with status N".
  - The context panel didn't trap focus. It is now a native modal `<dialog>`, which also fixed the double-Esc and the focus jump.
  - The import dialog kept the last group ID, which would merge a new export into the old group. It now resets each time it opens.
  - Deferred minors: the inspector's "Reranker off" label is wrong for zero candidates; Esc closes the import dialog mid-import; there is no end-of-chat context test.
- **Verification:** `pytest -q` 71 passed; ruff + black clean; `vitest` 21/21; `tsc --noEmit` clean; `vite build` OK; built bundle contains no API key or `X-API-Key` header. Real-browser pass done by the user (2026-10-27).
- **Status:** Done (2026-10-27). Not committed (CLAUDE.md).

### FEAT-05: WhatsApp gateway (ROADMAP 4.1), next
- **Context:** Phase 4 connects the MVP to real WhatsApp (FR-ING-4, FR-BOT-*).
- **Investigation / Steps:** Not started. Per CLAUDE.md, the requirements interview (AskUserQuestion) comes before any implementation.
- **Status:** Not started.
