# Web Demo Frontend: Design

Date: 2026-10-26. Status: approved in brainstorming, pending spec review.
Roadmap: new step **3.8 Web demo** (before Phase 4). Resolves PRD §479 (open question on a minimal web dashboard): yes, a local demo UI.

## 1. Goal

A local, single-user web app for the final-year evaluation that lets an examiner:

1. Import a WhatsApp `.txt` export into a group.
2. Switch between imported groups.
3. Ask questions and read grounded answers with numbered citations.
4. Open a citation to see the cited message in its surrounding conversation.
5. Inspect how each answer was produced (rewrite, retrieval counts, rerank scores, relevance gate).

Success: on a fresh checkout, `make run` + `make web`, import `data/samples/college_project_android.txt`, ask a Hinglish question, open a citation and read the trace, in both light and dark themes, with no network access needed for the UI itself (the LLM call still needs the Gemini API).

### Non-goals

- Streaming answers, conversational follow-up memory, persisted chat history (thread lives in `sessionStorage` per tab).
- Multi-user login, deployment, or a browser-safe auth path (the API key never reaches the browser).
- Summaries, time filters, extraction, topics (later phases; the UI must not show placeholders for them).
- Live (gateway) members in the "Ask as" picker; only imported display names are supported now.

## 2. Visual rules (hard constraints)

Direction: **Ledger**. Warm paper background, serif headings, IBM Plex for text and data, one deep green accent.

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#F5F2EA` | `#1A1916` |
| `--surface` | `#FFFDF8` | `#22211D` |
| `--surface-sunk` | `#EFEBE1` | `#151412` |
| `--ink` | `#1C1B18` | `#ECE8DE` |
| `--ink-muted` | `#6B6557` | `#A39D8E` |
| `--rule` | `#D9D3C4` | `#36342E` |
| `--accent` | `#1F5A45` | `#6FB394` |
| `--accent-ink` (text on accent) | `#F5F2EA` | `#151412` |
| `--danger` | `#9B2C1F` | `#E08070` |

Type: headings Source Serif 4 (500/600); UI and body IBM Plex Sans (400/500/600); metadata, scores, timestamps IBM Plex Mono (400/500). Self-hosted via `@fontsource/*` packages.

Rules:
- No gradients, no pill shapes (radius 2-4px only), no emoji, no em dashes in UI copy, no invented metrics or testimonials, no marketing hero.
- Every number shown comes from the API response.
- Motion: opacity/translate transitions of 120-180ms only; disabled under `prefers-reduced-motion`.
- Theme: follows `prefers-color-scheme`; a toggle overrides and is remembered in `localStorage` (wrapped in try/catch).
- Copy is plain and instructional ("Import a WhatsApp .txt export to begin").
- Keyboard: all actions reachable; visible focus ring in `--accent`; Enter sends, Shift+Enter newline.

## 3. Layout (option A)

```
┌──────────────┬───────────────────────────────┬────────────────────┐
│ Groups       │ Final Year Project            │ Trace              │
│ > Final Year │ Asking as [Rahul v]           │ rewrite            │
│   Hostel 4B  │                               │ retrieval counts   │
│              │ Q / A blocks with [1] markers │ reranked chunks    │
│ Import       │ Sources list                  │ gate: 3.42 >= -8.0 │
│ Theme        │ [ Ask about this chat     ]   │ prompt, latency    │
└──────────────┴───────────────────────────────┴────────────────────┘
```

- Widths: sidebar 240px, inspector 340px, chat fluid (max reading width ~720px).
- Below 1100px: inspector becomes a right drawer toggled from the chat header.
- Below 720px: sidebar collapses to a group `<select>` in the chat header; 16px side gutter; no horizontal scroll.
- Citation context opens as an overlay panel over the chat column (Esc closes, focus is trapped and restored).

## 4. Backend changes (`api/`)

All under `/api/v1`, all require `X-API-Key` (existing `require_api_key`). Errors use the existing `{"error": {"code", "message"}}` envelope.

### 4.1 `GET /groups`

Response `list[GroupSummary]`:

```json
[{"wa_group_id": "fyp", "name": "Final Year Project", "message_count": 46,
  "member_count": 4, "last_message_ts": "2026-10-01T18:40:00+05:30"}]
```

Ordered by `last_message_ts` desc. `message_count` excludes system messages. Operator-level view (no membership check, see §6).

### 4.2 `GET /groups/{wa_group_id}/members`

Response `list[MemberSummary]`: `{"display_name": "Rahul", "message_count": 13}`, ordered by `message_count` desc. 404 `GROUP_NOT_FOUND`. Operator-level view.

The picker sends `display_name` as `AskRequest.user_id`, which the existing `member_ref()` maps to `name:<display_name>`.

### 4.3 `GET /groups/{wa_group_id}/messages/{message_id}/context?user_id=<ref>&window=5`

- `window`: int, 1-20, default 5.
- Checks: group exists (404 `GROUP_NOT_FOUND`); `user_id` is a member (403 `NOT_A_MEMBER`, same query as `ask`); message belongs to the group (404 `MESSAGE_NOT_FOUND`).
- Returns the target plus up to `window` non-system messages before and after it, ordered by `(ts, id)`:

```json
{"target_id": 812, "messages": [
  {"id": 810, "sender": "Riya", "ts": "2026-10-01T10:10:00+05:30", "text": "...", "is_target": false}]}
```

The membership lookup shared by `ask` and `context` moves into one helper (`resolve_member()` in `app/routers/groups.py`) so both enforce it identically.

### 4.4 `POST /groups/{wa_group_id}/ask` (extended, backward compatible)

- `Source` gains `message_id: int` (set in `pick_citations`).
- `AskResponse` gains `trace: Trace`:

```json
{"rewrite": {"normalized": "...", "expansions": ["..."], "keywords": ["..."]},
 "retrieval": {"queries": [{"text": "...", "vector_hits": 8}], "fts_query": "...",
               "fts_hits": 5, "merged": 10},
 "reranked": [{"chunk_id": 31, "start_ts": "...", "end_ts": "...",
               "participants": "Riya, Amit Client", "score": 3.42,
               "preview": "first 160 chars", "cited": true}],
 "best_score": 3.42, "min_relevance": -8.0, "gated": false,
 "rerank_enabled": true, "prompt_version": "answer_v1", "latency_ms": 2140}
```

- Scores are raw cross-encoder logits (unbounded, can be negative), not probabilities; the UI labels them "rerank logit" and shows 2 decimals.
- `best_score` and `score` are `null` when the reranker is disabled (`rerank_enabled: false`).
- `gated` is true when the not-found branch fired because of no docs or `best_score < min_relevance`. When the LLM itself says not-found, `gated` is false and `found` is false.
- `cited` is true for the chunks the answer's `[n]` markers resolved to.

### 4.5 Chain change (`app/query/chain.py`)

Split `hybrid_retrieve` into two assigns so raw per-source lists survive:

```
assign(rewrite) | assign(hits=retrieve_lists) | assign(candidates=rrf_merge(hits))
  | assign(top=rerank) | branch(gate, answer) | attach_citations
```

`retrieve_lists` returns `{"vector": [[Document]...per query], "fts": [Document], "fts_query": str}`. Stage order is unchanged, so eval ablations (swap one stage for a passthrough) still work. `attach_citations` adds `"trace": build_trace(x, ...)`; `build_trace` is a pure function in new `app/query/trace.py`. The router fills `trace.latency_ms` with the same value as `AskResponse.latency_ms`.

The trace is returned to the caller only. `query_logs` is unchanged (chunk ids, no chat text, TRD §10).

## 5. Frontend (`web/`)

Stack: React 18, Vite, TypeScript (strict), CSS Modules plus `src/styles/tokens.css`. No UI component library, no Tailwind, no state library.

```
web/
  index.html
  vite.config.ts          # /api proxy -> http://127.0.0.1:8000, injects X-API-Key from ../.env
  package.json            # scripts: dev, build, preview, typecheck, test
  src/
    main.tsx, App.tsx     # AppShell: three-column grid, responsive breakpoints
    api.ts                # typed client; ApiError(code, message, status)
    types.ts              # mirrors the Pydantic response models
    citations.ts          # split answer text into text/marker segments
    styles/tokens.css, styles/base.css
    components/
      GroupSidebar.tsx    # list, selected state, Import button, theme toggle
      ImportDialog.tsx    # file + wa_group_id + name; shows counts or error
      ChatPane.tsx        # header (group name, Ask-as select), thread, composer
      AnswerBlock.tsx     # answer with [n] markers, sources list, not-found style
      ContextPanel.tsx    # surrounding messages, target highlighted
      InspectorPane.tsx   # trace of the selected answer (defaults to latest)
      ThemeToggle.tsx
  tests/                  # vitest: citations.test.ts, api.test.ts
```

Behaviour:
- **State:** `App` holds `groups`, `selectedGroupId`, `askAs` per group, `threads[groupId]` (synced to `sessionStorage`), `selectedTurnId` for the inspector. Plain `useState`/`useEffect`.
- **First load:** fetch `/groups`. Empty: centered instruction to import, mentioning `data/samples/college_project_android.txt`. After import: refresh groups and select the imported one.
- **Ask as:** fetched from `/members` on group select; defaults to the first member; changing it does not clear the thread.
- **Pending:** the turn shows "Searching the chat" plus a live elapsed seconds counter; composer disabled. No fake stage progress.
- **Answer:** `[n]` markers render as small accent squares linked to source `n`; clicking a marker or a source opens `ContextPanel`. Not-found answers render in `--ink-muted` with the reply text and no sources.
- **Inspector:** clicking a turn selects it. Sections: Rewrite, Retrieval (per-query vector hits, FTS query and hits, merged count), Reranked (table: score, time range, participants, preview, cited flag), Gate (`best >= min` or `best < min`, gated yes/no), Run (prompt version, latency).
- **Errors:** `ApiError` messages shown inline at the place of failure (import dialog, turn, context panel). 401 shows "API key mismatch: check API_KEY in .env".
- **Import:** client-side check `.txt` and <= 20 MB before upload; shows "Indexing" with elapsed time while the request runs (first run downloads models, can be slow).

API key handling: `vite.config.ts` uses `loadEnv(mode, '..', '')` to read `API_KEY` and sets `headers: {'X-API-Key': key}` on the `/api` proxy. The key is never in client code or the bundle. `vite preview` uses the same proxy config.

## 6. Security and privacy

- Message text (`ask`, `context`) requires group membership, as CLAUDE.md requires for any endpoint reading group data. `/groups` and `/members` expose names and counts only, to the API key holder (the operator running the demo). Recorded in Decisions.md.
- React escapes all chat text; no `dangerouslySetInnerHTML`. Chat text is untrusted.
- No analytics, no external requests from the page (fonts bundled).

## 7. Testing

Backend (pytest, existing fakes, no network):
- `GET /groups`: empty list; after import, counts correct.
- `GET /members`: names and counts; 404 unknown group.
- `context`: window bounds at chat start/end; 403 non-member; 404 wrong-group message id; system messages excluded.
- `ask`: `sources[].message_id` present; `trace` shape; `gated` true when below `min_relevance`; `reranked[].cited` matches markers.
- `build_trace` unit test on a hand-built chain state.

Frontend (vitest): `citations.ts` (markers, out-of-range markers, no markers); `api.ts` (error envelope to `ApiError`, non-JSON error body). `npm run typecheck` clean.

Manual (real browser): import sample, ask 3 questions including one not-found, open a citation, check trace numbers match the response, toggle theme, resize to 1000px and 400px, keyboard-only pass.

## 8. Commands and docs

- Makefile: `web-install` (`cd web && npm install`), `web` (`cd web && npm run dev`), `web-test` (`npm run typecheck && npm test`).
- `.gitignore`: add `.superpowers/`, `web/dist/`.
- Update: `docs/Architecture.md` (web module, boundary: browser talks only to the Vite proxy), `docs/Decisions.md` (React+Vite, no UI library, trace via chain split, operator-level list endpoints, key via proxy), `docs/Flow.md` (UI ask and context flows), `docs/Feature.md` (trail), `docs/ROADMAP.md` (step 3.8, move marker), CLAUDE.md commands section.
