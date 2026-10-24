# Product Requirements Document: WhatsApp Group Chat RAG Assistant

**Project type:** Final Year B.Tech Project **Version:** 1.0 (Draft) **Status:** Planning

---

## 1. Overview

### 1.1 Product summary

A WhatsApp bot that lets users query, summarize, and analyze a group chat using Retrieval-Augmented Generation (RAG). Users ask questions in natural language (English, Hindi, or Hinglish), and the system finds the answer by meaning rather than exact keywords, grounded in real messages and cited with sources. All AI components run on local open-source models.

### 1.2 Problem statement

Active WhatsApp groups (project teams, college groups, client groups, families) generate hundreds of messages a day. This creates three recurring problems:

1. **Finding information is hard.** WhatsApp search is keyword-only. If a user remembers the meaning but not the exact words, search fails.
2. **Catching up is painful.** Returning to 200+ unread messages means scrolling through noise to find what matters.
3. **Commitments and decisions get lost.** Who promised what, by when, and what was decided are buried in casual conversation.

These problems are worse in Indian groups, where messages mix Hindi and English in Roman script (Hinglish) with inconsistent spelling, which breaks most existing tools.

### 1.3 Vision

A group member should be able to ask the chat a question the way they would ask a colleague who read everything, and get a reliable, sourced answer in seconds.

---

## 2. Goals, Non-Goals and Success Metrics

### 2.1 Goals

- G1: Answer natural-language questions about chat content with cited sources.
- G2: Summarize any span of chat (especially unread messages) accurately and concisely.
- G3: Extract action items with owner and deadline automatically.
- G4: Maintain a log of decisions made in the group.
- G5: Support time-aware queries ("last week", "in March", "yesterday").
- G6: Cluster messages into topics and show what the group discusses most.
- G7: Handle Hinglish and mixed-language chat as a first-class use case.
- G8: Keep chat storage, indexing, and retrieval local; use a cloud LLM (Gemini 3.5 Flash-Lite) only for generation.

### 2.2 Non-goals (v1)

- Sending messages on behalf of users or acting autonomously in the group.
- Voice note transcription, image/OCR understanding, and video analysis.
- Multi-tenant production deployment and user billing.
- A mobile app or full web dashboard (a lightweight analytics view is optional).
- Official WhatsApp Business API integration (it cannot read standard groups).

### 2.3 Success metrics

| Metric | Target | How measured |
| --- | --- | --- |
| Retrieval Recall@5 on Hinglish test set | >= 80% | Labeled question set (Section 12) |
| Answer faithfulness (grounded in sources) | >= 85% | Manual rubric + LLM-judge check |
| Summary quality (human rating, 1-5) | >= 4.0 avg | 5+ reviewers on 20 sample summaries |
| Action item extraction F1 | >= 0.70 | Hand-labeled chat segments |
| Query response time (search/Q&A) | <= 10 s on target hardware | Timed benchmark |
| Summary time for 200 messages | <= 30 s | Timed benchmark |

---

## 3. Target Users and Personas

**Persona 1: Riya, project group member.** Misses chat during classes. Wants a quick summary and a list of her pending tasks when she returns.

**Persona 2: Arjun, team lead / client-facing person.** Needs to recall what a client agreed to weeks ago without scrolling. Wants decisions and deadlines on record.

**Persona 3: Mr. Sharma, community admin.** Manages a large group and wants to see what topics dominate and what has been decided.

**Primary evaluators for this project:** faculty and external examiners who will assess technical depth, correctness, and demo quality.

---

## 4. User Stories

| ID | As a... | I want to... | So that... |
| --- | --- | --- | --- |
| US-1 | group member | ask "client ne delivery kab bola tha?" | I find the answer without scrolling |
| US-2 | group member | get a summary of unread messages | I catch up in under a minute |
| US-3 | group member | list my pending action items | I don't miss commitments |
| US-4 | group member | see who promised what, by when | accountability is clear |
| US-5 | team lead | view a log of decisions | I can verify what was agreed |
| US-6 | group member | ask "last week budget pe kya discuss hua?" | results are limited to that period |
| US-7 | admin | see the main topics in the group | I understand group activity |
| US-8 | any user | see source messages behind each answer | I can trust and verify it |
| US-9 | group admin | import old chat history | the bot has full context |

---

## 5. Scope

### 5.1 In scope (v1)

1. Chat ingestion via exported `.txt` and live capture.
2. Hinglish-aware preprocessing and indexing.
3. Semantic search and question answering with citations.
4. Time-filtered queries.
5. Chat summarization (unread, time range, last N messages).
6. Action item and deadline extraction.
7. Decision log.
8. Topic clustering and statistics.
9. WhatsApp bot command interface.
10. Evaluation module with a labeled test set.

### 5.2 Out of scope (v1)

Voice notes, images, daily digests, multi-language translation, cloud deployment, and user authentication beyond group membership.

---

## 6. Functional Requirements

Priority key: **P0** = must have, **P1** = should have, **P2** = nice to have.

### 6.1 Data ingestion (FR-ING)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-ING-1 | System shall accept an exported WhatsApp `.txt` file sent to the bot and import it. | P0 |
| FR-ING-2 | Parser shall support both Android and iOS export formats, 12h/24h time, and multi-line messages. | P0 |
| FR-ING-3 | Parser shall extract timestamp, sender, and message text, and flag system messages (joins, leaves, "media omitted", deleted messages). | P0 |
| FR-ING-4 | System shall capture new group messages live via a linked-device library (whatsapp-web.js or Baileys) and store them in near real time. | P0 |
| FR-ING-5 | System shall deduplicate messages when imported history overlaps with live-captured messages. | P1 |
| FR-ING-6 | System shall support multiple groups, each with an isolated index. | P1 |
| FR-ING-7 | System shall track a per-user "last seen" marker for unread summaries. | P0 |

### 6.2 Preprocessing and indexing (FR-IDX)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-IDX-1 | System shall normalize text: lowercase, collapse repeated characters ("haaaan" to "haan"), standardize common Hinglish spelling variants, and strip noise. | P0 |
| FR-IDX-2 | System shall build conversation chunks using time-gap segmentation (e.g., new chunk after 30+ minutes of silence) plus a sliding window (e.g., 8-15 messages with overlap). | P0 |
| FR-IDX-3 | Each chunk shall store metadata: group ID, start/end timestamps, participants, message IDs. | P0 |
| FR-IDX-4 | System shall embed chunks using a multilingual embedding model (BGE-M3 or multilingual-e5) and store them in a vector database. | P0 |
| FR-IDX-5 | System shall maintain a BM25 keyword index in parallel for hybrid retrieval. | P0 |
| FR-IDX-6 | New live messages shall be indexed incrementally within 60 seconds. | P1 |
| FR-IDX-7 | Short, low-information messages ("ok", "hmm") shall be kept inside chunks but never indexed alone. | P0 |

### 6.3 Semantic search and Q&A (FR-QA)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-QA-1 | User shall ask a free-form question in English, Hindi (Roman), or Hinglish. | P0 |
| FR-QA-2 | System shall rewrite the query (normalize spelling, expand synonyms, translate intent) before retrieval. | P1 |
| FR-QA-3 | System shall perform hybrid retrieval (vector + BM25) and merge results using Reciprocal Rank Fusion. | P0 |
| FR-QA-4 | System shall rerank the top candidates with a cross-encoder reranker. | P1 |
| FR-QA-5 | System shall generate an answer with the local LLM using only retrieved context. | P0 |
| FR-QA-6 | Answer shall include citations: sender, date/time, and a short snippet of each source message. | P0 |
| FR-QA-7 | If retrieved context does not support an answer, system shall say "I couldn't find this in the chat" rather than guess. | P0 |
| FR-QA-8 | System shall reply in the same language style as the question (English or Hinglish). | P1 |
| FR-QA-9 | System shall support simple follow-up questions using short conversation memory. | P2 |

### 6.4 Time-filtered queries (FR-TIME)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-TIME-1 | System shall detect time expressions in queries: "yesterday", "last week", "pichhle hafte", "in March", "between 5 and 10 Jan". | P0 |
| FR-TIME-2 | System shall convert expressions into absolute date ranges using the current date and timezone (IST by default). | P0 |
| FR-TIME-3 | Date range shall be applied as a metadata filter on retrieval, before ranking. | P0 |
| FR-TIME-4 | System shall confirm the interpreted range in the reply (e.g., "Showing results from 1-7 Oct"). | P1 |
| FR-TIME-5 | If no time expression is present, system shall search the entire history. | P0 |

### 6.5 Summarization (FR-SUM)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-SUM-1 | User shall request a summary of: unread messages, last N messages, last X hours/days, or a custom date range. | P0 |
| FR-SUM-2 | For long ranges, system shall use map-reduce summarization (summarize chunks, then combine). | P0 |
| FR-SUM-3 | Summary shall be structured: overview, key topics, important updates, questions awaiting answers. | P0 |
| FR-SUM-4 | User shall choose length: short (3-5 lines), standard, or detailed. | P1 |
| FR-SUM-5 | Summary shall be sent privately to the requesting user by default, not posted to the group. | P0 |
| FR-SUM-6 | After an unread summary, system shall update that user's last-seen marker. | P0 |
| FR-SUM-7 | Summary shall preserve names, numbers, dates, and amounts accurately. | P0 |

### 6.6 Action items and deadlines (FR-ACT)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-ACT-1 | System shall detect commitments, tasks, and requests in messages (e.g., "main kal tak report bhej dunga", "can you share the file by Friday?"). | P0 |
| FR-ACT-2 | Each action item shall be stored as: task, owner, deadline (if any), source message, status (open/done), created-at. | P0 |
| FR-ACT-3 | System shall resolve relative deadlines ("kal", "next Monday") into absolute dates using the message timestamp. | P0 |
| FR-ACT-4 | System shall resolve pronouns and implied owners where possible ("I" maps to message sender). | P0 |
| FR-ACT-5 | User shall list action items: all, mine, by person, or overdue. | P0 |
| FR-ACT-6 | User shall mark an item done via command. System may also suggest completion when a later message indicates it. | P1 |
| FR-ACT-7 | System shall flag overdue items. | P1 |
| FR-ACT-8 | Extraction shall run automatically on new messages in batches and on imported history. | P0 |

### 6.7 Decision log (FR-DEC)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-DEC-1 | System shall detect decisions ("toh final hai, Saturday ko milte hain", "we'll go with option B"). | P0 |
| FR-DEC-2 | Each decision shall be stored with: decision text, topic, participants, date, source messages. | P0 |
| FR-DEC-3 | User shall view the decision log: all, by topic, or by date range. | P0 |
| FR-DEC-4 | System shall link related decisions and flag when a later decision overrides an earlier one. | P2 |
| FR-DEC-5 | Each entry shall link back to its source messages for verification. | P0 |

### 6.8 Topic clustering (FR-TOP)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-TOP-1 | System shall cluster chunk embeddings (BERTopic, or UMAP + HDBSCAN/KMeans) into topics. | P0 |
| FR-TOP-2 | Each topic shall receive an auto-generated label (via LLM from top keywords and sample chunks). | P0 |
| FR-TOP-3 | User shall request top topics with message counts and share of conversation. | P0 |
| FR-TOP-4 | System shall show topic trends over time (topic volume by week). | P1 |
| FR-TOP-5 | Clustering shall be re-run on schedule or on demand. | P1 |
| FR-TOP-6 | A topic can be expanded into a summary and its key messages. | P2 |
| FR-TOP-7 | Output may be a text list in WhatsApp plus a generated chart image (bar chart / topic timeline). | P1 |

### 6.9 Bot interface (FR-BOT)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-BOT-1 | Bot shall respond to commands and to natural-language messages that mention it. | P0 |
| FR-BOT-2 | Bot shall support private (DM) interaction with a user for queries about groups they belong to. | P0 |
| FR-BOT-3 | Bot shall show a typing indicator or "working on it" message for slow tasks. | P1 |
| FR-BOT-4 | Long replies shall be split into readable WhatsApp messages with basic formatting. | P1 |
| FR-BOT-5 | Bot shall provide `/help` with all commands and examples. | P0 |
| FR-BOT-6 | Bot shall only answer users who are members of the relevant group. | P0 |

---

## 7. Bot Command Specification

| Command | Example | Description |
| --- | --- | --- |
| `/ask <question>` | `/ask client ne payment kab bola?` | Semantic Q&A with citations |
| `/summary` | `/summary` | Summarize unread messages |
| `/summary <range>` | `/summary last 3 hours`, `/summary 100` | Summarize a range or last N messages |
| `/tasks` | `/tasks`, `/tasks mine`, `/tasks @Rahul` | List action items |
| `/done <id>` | `/done 12` | Mark action item complete |
| `/decisions` | `/decisions`, `/decisions budget` | Show decision log |
| `/topics` | `/topics last month` | Show topic clusters and stats |
| `/import` | (send .txt file) | Import chat history |
| `/group <name>` | `/group College Project` | Select active group in DM |
| `/help` | `/help` | Show commands |

Natural-language equivalents (e.g., "summarize karo") should map to these commands via an intent classifier (P1).

---

## 8. Non-Functional Requirements

| Category | Requirement |
| --- | --- |
| **Performance** | Q&A under 10 s; 200-message summary under 30 s; indexing 10,000 messages under 10 minutes on target hardware. |
| **Accuracy** | Answers must be grounded; hallucination rate tracked and reported. |
| **Privacy** | Storage, embeddings, and retrieval run locally. Only the minimal prompt (question plus top retrieved excerpts) is sent to the Gemini API; free tier used only with synthetic/anonymized data. |
| **Security** | Group isolation enforced at query time; bot answers only for verified members; data stored on local encrypted disk where possible. |
| **Reliability** | Bot reconnects automatically after session drop; message capture queue survives restart. |
| **Scalability** | Support at least 5 groups and 100,000 messages in total for demo. |
| **Maintainability** | Modular services; config-driven model choice; documented APIs; every pipeline built from composable LangChain runnables. |
| **Portability** | Models and DB swappable through LangChain's standard interfaces (chat model, embeddings, vector store, retriever), e.g., Gemini model name in config, Chroma replaceable by Qdrant. |
| **Observability** | Log each query with retrieved chunks, latency, and model used, for debugging and evaluation (via LangChain callbacks written to the local DB; hosted tracing such as LangSmith stays off to honor the privacy requirement). |

---

## 9. System Architecture

### 9.1 High-level flow

```
WhatsApp Group
     |
     v
Bot Gateway (Node.js: whatsapp-web.js / Baileys)
     |  REST / queue
     v
Backend API (Python, FastAPI; pipelines orchestrated with LangChain)
     |
     +--> Ingestion: parser, cleaner, dedup
     +--> Indexing: chunker -> embedder -> Vector DB + BM25 index
     +--> Query Engine: intent -> time parser -> query rewrite -> hybrid retrieval -> reranker -> LLM answer
     +--> Summarizer: map-reduce over chunks
     +--> Extractors: action items, decisions (LLM, JSON output)
     +--> Topic Engine: clustering + labeling
     |
     v
Storage: SQLite/PostgreSQL (messages, tasks, decisions, users) + Chroma/Qdrant (vectors)
     |
LLM: Google Gemini API (Gemini 3.5 Flash-Lite)
```

### 9.2 Components

1. **Bot gateway:** maintains the WhatsApp session, receives messages and commands, forwards to the backend, and sends replies.
2. **Ingestion service:** parses exports and live messages into a unified schema.
3. **Indexing service:** chunks, embeds, and stores data; updates incrementally.
4. **Query engine:** the core RAG pipeline.
5. **Extraction service:** background jobs for action items and decisions.
6. **Topic engine:** periodic clustering.
7. **Evaluation harness:** offline scripts to measure each module.

### 9.3 RAG query pipeline (detailed)

1. Receive question and group ID.
2. Classify intent (ask / summary / tasks / decisions / topics).
3. Extract time range (if any) and apply as filter.
4. Rewrite query for Hinglish normalization and expansion.
5. Retrieve top-K from vector search and BM25.
6. Merge via Reciprocal Rank Fusion.
7. Rerank top \~20 down to \~5 with a cross-encoder.
8. Build the prompt with chunks, metadata, and instructions to cite and not guess.
9. Generate the answer with the local LLM.
10. Attach citations and send to the user.

### 9.4 Extraction pipeline (action items and decisions)

1. New or imported chunks are queued.
2. LLM is prompted with a strict JSON schema and few-shot Hinglish examples.
3. Output is validated; invalid JSON is retried once.
4. Relative dates are resolved in code (not by the LLM) for reliability.
5. Duplicates are merged by similarity of task text, owner, and date.
6. Results are written to the database with source message IDs.

---

## 10. Technology Stack (proposed)

| Layer | Choice | Alternatives |
| --- | --- | --- |
| Bot gateway | Node.js + whatsapp-web.js | Baileys |
| Backend | Python 3.11 + FastAPI | Flask |
| LLM | Gemini 3.5 Flash-Lite (Gemini API) | Gemini 3.8 Flash |
| Embeddings | BGE-M3 | multilingual-e5-large |
| Reranker | bge-reranker-v2-m3 | cross-encoder MiniLM |
| Vector DB | ChromaDB | Qdrant, FAISS |
| Keyword search | rank\_bm25 | SQLite FTS5 |
| Relational DB | SQLite (dev), PostgreSQL (optional) |  |
| Orchestration | LangChain (LCEL runnables, `langchain-google-genai`, `langchain-chroma`, `langchain-huggingface`) | LlamaIndex, plain Python |
| Date parsing | dateparser + custom Hinglish rules |  |
| Topic modeling | BERTopic (UMAP + HDBSCAN) | KMeans + c-TF-IDF |
| Charts | matplotlib / plotly |  |
| Queue | Redis or in-process queue |  |
| Packaging | Docker Compose |  |

**Hardware assumption (to confirm):** a machine with at least 16 GB RAM and ideally a GPU with 8 GB+ VRAM. On CPU only, use quantized models (Q4) and expect slower responses. The model is config-driven so it can be downsized to a 3B-4B model if needed.

---

## 11. Data Model

### 11.1 Core tables

**groups**: id, whatsapp\_group\_id, name, created\_at

**users**: id, phone\_hash, display\_name

**memberships**: user\_id, group\_id, last\_seen\_message\_id, last\_seen\_at

**messages**: id, group\_id, sender\_id, timestamp, text\_raw, text\_clean, is\_system, reply\_to\_id, source (import/live)

**chunks**: id, group\_id, start\_ts, end\_ts, participants, message\_ids, text, embedding\_ref

**action\_items**: id, group\_id, task, owner\_id, deadline, status, source\_message\_ids, confidence, created\_at, completed\_at

**decisions**: id, group\_id, decision\_text, topic, decided\_on, participants, source\_message\_ids, supersedes\_id

**topics**: id, group\_id, label, keywords, chunk\_ids, message\_count, created\_at

**query\_logs**: id, group\_id, user\_id, query, intent, filters, retrieved\_chunk\_ids, answer, latency\_ms, created\_at

### 11.2 Vector store

Each record holds: chunk ID, embedding vector, and metadata (group\_id, start\_ts, end\_ts, participants) to enable group and time filtering.

---

## 12. Evaluation Plan

A dedicated evaluation module is a core deliverable and a major viva asset.

### 12.1 Datasets

- **Real or realistic chat data:** a consented/anonymized group export, or a synthetic Hinglish group chat generated and manually corrected. Target 5,000+ messages.
- **Q&A test set:** 100+ questions in English and Hinglish, each labeled with the correct source messages.
- **Extraction test set:** 150+ labeled messages for action items and decisions.
- **Summary test set:** 20 segments with human-written reference summaries.

### 12.2 Metrics

| Module | Metrics |
| --- | --- |
| Retrieval | Recall@k, MRR, nDCG; compare vector-only vs BM25-only vs hybrid vs hybrid + rerank |
| Answering | Faithfulness, answer relevance, "no-answer" correctness |
| Summarization | Human rating, ROUGE/BERTScore (secondary), factual accuracy checks |
| Action items | Precision, recall, F1; deadline resolution accuracy |
| Decisions | Precision, recall, F1 |
| Topics | Coherence score, human label quality |
| System | Latency, memory use |

### 12.3 Ablation studies (for the report)

- English embedding model vs multilingual model on Hinglish queries.
- Effect of chunking strategy (single message vs window vs time-gap).
- Effect of query rewriting.
- Effect of reranking.
- Different LLMs (Gemini 3.5 Flash-Lite vs 3.8 Flash).

---

## 13. Privacy, Legal and Ethical Considerations

- **Terms of Service:** unofficial WhatsApp libraries violate WhatsApp's ToS and carry a ban risk. Use a dedicated spare number and document this limitation clearly.
- **Consent:** inform group members that a bot is reading and indexing messages; get admin approval. Provide a way to delete a group's data (`/purge`).
- **Data minimization:** store phone numbers hashed where possible; keep data local.
- **Sensitive content:** do not expose a user's messages to non-members. Enforce group-level access control.
- **Transparency:** every answer shows its sources; the bot labels AI-generated content.
- **Test data:** use only anonymized or synthetic chats in demos and the report.
- **Legal context:** processing personal data should follow applicable Indian data protection norms (DPDP Act, 2023); note this in the report.

---

## 14. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| WhatsApp bans the bot number | Medium | High | Use spare number; keep `.txt` import as a fallback path for the demo |
| Poor Hinglish retrieval | Medium | High | Multilingual embeddings, normalization, hybrid search, query rewriting |
| LLM hallucination | Medium | High | Strict grounding prompt, citations, "no answer" behavior, reranking |
| Slow responses on weak hardware | High | Medium | Quantized/smaller models, caching, background indexing |
| Invalid JSON from LLM extractors | Medium | Medium | Schema validation, retry, constrained decoding |
| Wrong date resolution | Medium | Medium | Resolve dates in code with dateparser, not in the LLM |
| No real test data | Medium | High | Build a synthetic Hinglish dataset early |
| Scope creep | High | High | Strict P0/P1/P2 prioritization; freeze scope by Week 8 |
| Library breaks after WhatsApp update | Medium | Medium | Pin versions; modular gateway so it can be swapped |

---

## 15. Milestones and Timeline (suggested, 16 weeks)

| Phase | Weeks | Deliverables |
| --- | --- | --- |
| 1. Foundation | 1-2 | Finalize PRD, set up repo, environment, Gemini API access, chat parser, synthetic dataset plan |
| 2. Ingestion and indexing | 3-4 | Parser for Android/iOS formats, cleaning, chunking, embeddings, vector DB, BM25 |
| 3. Core RAG | 5-6 | Hybrid retrieval, reranking, answer generation with citations, no-answer handling |
| 4. Bot integration | 7-8 | WhatsApp gateway, commands, `/ask`, `/import`, `/help`. **Scope freeze.** |
| 5. Summarization | 9 | Map-reduce summarizer, unread tracking, length options |
| 6. Time-filtered queries | 10 | Time expression parser (English and Hinglish), filter integration |
| 7. Extraction | 11-12 | Action item and decision extraction, task commands, decision log |
| 8. Topic clustering | 13 | Clustering, labeling, charts, `/topics` |
| 9. Evaluation | 14 | Test sets, metrics, ablations |
| 10. Polish and docs | 15-16 | Bug fixes, demo script, final report, presentation, viva prep |

---

## 16. Demo Plan

A 10-minute demo that shows:

1. Importing a Hinglish group chat export.
2. A vague question ("woh payment wali baat kab hui thi?") answered with citations.
3. A time-filtered query ("pichhle hafte budget pe kya decide hua?").
4. An unread summary after a burst of live messages.
5. `/tasks` showing owners and deadlines, then `/done`.
6. `/decisions` log.
7. `/topics` with a chart.
8. Evaluation results slide comparing retrieval strategies.

---

## 17. Deliverables

- Source code (bot gateway, backend, extraction, topic modules)
- Docker Compose setup and README
- Labeled datasets and evaluation scripts
- Final project report (with ablation results)
- Presentation slides and demo video
- Architecture and API documentation

---

## 18. Open Questions

1. What hardware (CPU, RAM, GPU/VRAM) will be used for development and demo?
2. Where will chat data for testing come from: real consented groups or a synthetic dataset?
3. Should the bot reply inside the group, privately in DM, or both? (Current default: DM for summaries, group for short answers if mentioned.)
4. Is a minimal web dashboard for topics and analytics desired, or is chat-only output enough?
5. How many groups and members are expected in the demo?
6. Will the project guide require a specific methodology or report format?

---

## 19. Future Scope (post v1)

Voice note transcription (Whisper), daily digests, image and document understanding, multi-user web dashboard, cloud deployment, cross-lingual answers (e.g., Hindi in Devanagari), fine-tuned Hinglish embeddings, and optional upgrade to larger or API-based models.

---

## 20. Glossary

- **RAG:** Retrieval-Augmented Generation, where an LLM answers using retrieved documents.
- **Hybrid retrieval:** combining semantic (vector) and keyword (BM25) search.
- **RRF:** Reciprocal Rank Fusion, a method to merge ranked lists.
- **Reranker:** a model that rescores retrieved results for relevance.
- **Hinglish:** Hindi written in Roman script mixed with English.
- **Map-reduce summarization:** summarize parts separately, then summarize the summaries.
- **LangChain:** a Python framework that provides standard interfaces for LLMs, embeddings, vector stores, and retrievers, plus a way to compose them into pipelines.
- **LCEL:** LangChain Expression Language; pipelines written as `prompt | model | parser` chains of runnables.
