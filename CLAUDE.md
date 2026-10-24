# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Early skeleton for a WhatsApp group-chat RAG assistant (final-year B.Tech project). Only `api/app/config.py` and a `/api/v1/health` endpoint in `api/app/main.py` exist; the other module directories hold `.gitkeep` placeholders. `Makefile` and `docker-compose.yml` are empty. ruff, black and pytest are configured in `pyproject.toml`, but there are no tests yet. The LLM is Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`) via the Gemini API (`GOOGLE_API_KEY` in `.env`); there is no local LLM.

`docs/PRD.md` (what) and `docs/TRD.md` (how) are the specification. Read the relevant TRD section before implementing a module; requirement IDs like `FR-QA-3` refer to the PRD. `docs/ROADMAP.md` is the step-by-step build order (with a "You are here" marker); `docs/TODO.md` tracks the current phase.

## Commands

```
python -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt
cp .env.example .env

cd api && uvicorn app.main:app --reload   # run from api/ so `app` is importable
```

```
ruff check . && black --check .   # config in pyproject.toml (line length 100)
pytest                            # testpaths/pythonpath set in pyproject.toml
```

Planned (TRD §14.3, not yet set up): `make up | test | reindex | eval | seed`.

## Architecture

- **gateway/** (Node.js, whatsapp-web.js): holds the WhatsApp session and forwards events to the Core API over HTTP (`X-API-Key` shared secret). Library-specific code sits behind a `GatewayAdapter` interface so Baileys can replace it.
- **api/** (FastAPI, base path `/api/v1`): a modular monolith. Every pipeline (ask, summary, extraction, topic labels) is a **LangChain LCEL chain**, following the TRD §2.5 rules:
  - Build pipelines from `langchain-core` runnables plus the integration packages (`langchain-google-genai`, `-chroma`, `-huggingface`, `-community`). Don't use the high-level legacy chains (`RetrievalQA`, `load_summarize_chain`, `EnsembleRetriever`).
  - Keep domain logic in plain Python, wrapped as `RunnableLambda` only where it sits inside a chain. That covers parsing, Hinglish normalization, time-gap chunking, date resolution, dedup and auth. **The LLM never computes dates or parses commands.**
  - Create models only through `app/llm/` factories driven by config. Any step that expects JSON uses `with_structured_output(<Pydantic model>)` and retries once on failure.
  - Store prompts as versioned files in `app/prompts/` and load them into `ChatPromptTemplate`.
- **worker/** (RQ): runs the background jobs (indexing, extraction, clustering) and reuses the chains from `api/app`.
- **eval/**: imports the same `api/app/query` runnables. To run an ablation, swap one stage for a passthrough; don't build a separate pipeline.
- **Ask pipeline** (TRD §5.6): intent → time range filter → query rewrite → hybrid retrieval → custom RRF merge → cross-encoder rerank → grounded answer with `SOURCES` → citations. Hybrid retrieval combines Chroma vectors with a custom SQLite FTS5 retriever. If the best rerank score is below `MIN_RELEVANCE`, the pipeline answers not-found instead of generating.
- **Data**: the relational DB (SQLite via SQLAlchemy) is the source of truth. Chroma (one collection per group, `grp_<group_id>`) and FTS5 are derived indexes that can be rebuilt. Chunk metadata must be scalar for Chroma: `start_ts`/`end_ts` are epoch ints and lists are joined into strings.

## Configuration

`api/app/config.py` (pydantic-settings) loads settings in this order: init args > env vars > `.env` > `config.yaml`. Keys are snake_case and match the fields in `Settings`. The TRD §8 table shows them in UPPER_CASE. Add any new tunable to both `config.yaml` and `Settings`.

## Constraints

- Privacy: storage, embeddings, and retrieval are local; only LLM prompts go to the Gemini API (free tier = synthetic/anonymized data only). Keep LangSmith tracing off (`LANGSMITH_TRACING=false`); chain telemetry goes only to the local `query_logs` table through a callback handler.
- Chat text is untrusted input (prompt injection). Wrap excerpts in delimited blocks in prompts, and enforce group membership on every endpoint that reads group data.
- Default timezone is `Asia/Kolkata`. Hinglish (Roman-script Hindi mixed with English) is the main content language.
