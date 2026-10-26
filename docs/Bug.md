# Bug Trail

Start-to-finish records of every bug, so anyone can pick one up cold. Open a record **before** starting a fix and log the trail while working. Related reasoning goes in `Decisions.md` (linked as D-xx).

Format: **Context** · **Investigation / Steps** · **Blockers** · **Resolution** (changes + how it was verified) · **Status**.

_BUG-01 to BUG-11 were backfilled on 2026-10-25 from the MVP work (2026-10-24). Commit refs: `b90736a` (config/env), `cdb5191` (MVP)._

---

## Index

| ID | Summary | Area | Status |
| --- | --- | --- | --- |
| BUG-01 | Ollama: "could not connect to server", and GPU not used | Environment | Closed (superseded by D-03) |
| BUG-02 | `thinking_level="minimal"` rejected by gemini-3.8-flash | LLM config | Closed |
| BUG-03 | Gemini calls take 30-123 s | LLM latency | Closed (D-04) |
| BUG-04 | Intermittent `503 UNAVAILABLE` from Flash-Lite | LLM reliability | Mitigated |
| BUG-05 | `CUDA out of memory` loading embedder + reranker | Local models | Closed (D-06) |
| BUG-06 | Every reranker score is 0.0 | Reranker | Closed (D-07) |
| BUG-07 | Reranker misses Hinglish paraphrases | Retrieval quality | Mitigated (D-08) |
| BUG-08 | Cleaner turns "₹5000" into "₹500" | Ingestion | Closed (D-22) |
| BUG-09 | Dictionary maps "hain" → "hai" | Ingestion | Closed (D-22) |
| BUG-10 | Citation points at the question, not the reply | Ask pipeline | Closed (D-13) |
| BUG-11 | Upload endpoint fails: python-multipart missing | API | Closed |

---

### BUG-01: Ollama "could not connect to server", and GPU not used
- **Context:** `ollama list` failed with "could not connect to ollama server, run 'ollama serve'". Later, with the server up, inference ran on CPU even though the laptop has an RTX 3050.
- **Investigation / Steps:**
  1. `systemctl status ollama`: the unit was `disabled`, so nothing started it after boot. That explains the connection error.
  2. Journal: `inference compute ... library=cpu`, so the GPU wasn't detected.
  3. `nvidia-smi` worked and the `nvidia` kernel module was loaded, so the driver was fine.
  4. `pacman -Qs ollama` showed the `ollama` package, Arch's CPU-only build. The CUDA build is `ollama-cuda`.
- **Blockers:** 4 GB of VRAM can't hold the planned 7B Q4 model (~5 GB) fully on the GPU, even with the CUDA build.
- **Resolution:** Suggested fixes were `systemctl enable --now ollama` and `pacman -S ollama-cuda`. The user then moved the project to a cloud LLM (D-03), so Ollama is no longer used. `langchain-ollama` was uninstalled and removed from requirements (`b90736a`).
- **Status:** Closed, superseded by D-03.

### BUG-02: `thinking_level="minimal"` rejected by gemini-3.8-flash
- **Context:** While measuring latency, a call with `thinking_level="minimal"` failed with `400 INVALID_ARGUMENT: Thinking level MINIMAL is not supported for this model`.
- **Investigation / Steps:** I read the error text. The level is model-specific. LangChain docs list `minimal | low | medium | high` for Gemini 3, but not every model accepts every level.
- **Resolution:** Kept `llm_thinking_level: "low"` (accepted by both 3.8 Flash and 3.5 Flash-Lite). Verified with Flash-Lite through LangChain using the real config.
- **Status:** Closed.

### BUG-03: Gemini calls take 30-123 s
- **Context:** The first `gemini-3.8-flash` test calls took 51 s and 31 s, far over the 10 s `/ask` budget (TRD §11).
- **Investigation / Steps (systematic debugging, one layer at a time):**
  1. Instrumented one call with httpx/httpcore debug logs. There was **one** HTTP request and 0 retries, which ruled out the SDK's hidden tenacity retry loop. TCP connect 1.1 s, TLS 55 ms, then 87 s until `200 OK`. Usage: 18 tokens, 0 thinking tokens, which ruled out thinking.
  2. `curl` on the non-generating `models.get` endpoint: 0.7 s total over IPv4, which ruled out the network. IPv6 had no route, which explains the 1.1 s first connect (a minor, separate issue).
  3. Raw `curl generateContent`, bypassing LangChain and the SDK: 123 s. The `server-timing: dur=122957` header puts the time **on Google's servers**.
  4. Same request with `gemini-3.5-flash-lite`: 2.9 s (server 2.6 s). The cause is specific to the model, not to our code.
- **Blockers:** I can't tell whether 3.8 Flash's free-tier slowness is temporary or lasting. That needs re-measuring over time.
- **Resolution:** Set `llm_model: gemini-3.5-flash-lite` in `config.yaml` and `Settings`; updated PRD, TRD, ROADMAP and CLAUDE.md. Verified at 2.7-5.9 s per call with valid structured output 3 of 3 times, and 3.0-6.5 s end to end for `/ask`.
- **Status:** Closed (D-04). Re-measure 3.8 Flash in Phase 9.

### BUG-04: Intermittent `503 UNAVAILABLE` from Flash-Lite
- **Context:** The first verification call after switching models failed with `503: This model is currently experiencing high demand`.
- **Investigation / Steps:** Retried immediately and 6 of 6 calls succeeded. It's transient free-tier capacity, not something in our code.
- **Resolution:** Added `llm_max_retries: 4` (config and `Settings`), passed as `max_retries` to `ChatGoogleGenerativeAI`, so the SDK retries with backoff. The rewrite step also falls back to the raw question (D-21). TRD §9 updated.
- **Status:** Mitigated. If all retries fail on the **answer** step, it still surfaces as a 500. A friendly error is still to do (Flow.md §2).

### BUG-05: `CUDA out of memory` loading embedder + reranker
- **Context:** The first real load of BGE-M3 plus bge-reranker-v2-m3 crashed with `torch.OutOfMemoryError ... GPU 0 has a total capacity of 3.73 GiB of which 5.00 MiB is free ... 3.60 GiB allocated by PyTorch`.
- **Investigation / Steps:** Each model is about 568M parameters, so ~2.3 GB in fp32. Two of them can't fit in 3.73 GB. I checked the sentence-transformers 6.2 constructors: both accept `model_kwargs` passed through to transformers `from_pretrained`.
- **Resolution:** `app/llm/__init__.py:_device_kwargs()` passes `{"device": "cuda", "model_kwargs": {"dtype": torch.float16}}` (CPU fp32 when there's no GPU). Verified: embedding dim 1024, reranker runs, **2.28 GB** of VRAM total, and fp16 logits match fp32 (−10.906 vs −10.902).
- **Status:** Closed (D-06).

### BUG-06: Every reranker score is 0.0
- **Context:** Right after BUG-05, reranker scores for a relevant pair and two irrelevant pairs all came back `0.0`.
- **Investigation / Steps:**
  1. Hypothesis "fp16 numerics": compared raw logits for CPU fp32 / CUDA fp16 / CUDA bf16. All about −10.9, so **rejected**.
  2. The default activation is `Sigmoid()`, and sigmoid(−10.9) ≈ 1.8e-5, which rounds to 0.0. The model itself was fine.
  3. Probed English vs Hinglish pairs: the reranker separates them well (relevant −1.7 to −5.8, irrelevant ≈ −11).
- **Resolution:** Built the reranker with `activation_fn=torch.nn.Identity()` (raw logits) and changed `min_relevance` from 0.05 to **−8.0** on the logit scale (config and `Settings`, TRD §8 updated).
- **Status:** Closed (D-07). The threshold is provisional, to be calibrated in Phase 9.

### BUG-07: Reranker misses Hinglish paraphrases
- **Context:** Found during the BUG-06 probe. "client ne payment kab bola?" vs "paisa 20 tarikh tak aa jayega" scored −10.8, almost the same as an irrelevant pair. Left alone, this would have triggered false not-found answers on the PRD's flagship example.
- **Investigation / Steps:** Lexical overlap rescues it: "payment kab aayega" vs "payment 20 tarikh tak aa jayega" scores −3.6. The rewrite expansions add exactly those overlapping synonyms.
- **Resolution:** `app/query/rerank.py`: each candidate is scored against `[question, normalized, *expansions]` and keeps its max. Unit test `test_rerank_uses_best_score_across_query_variants`. Verified end to end: "client ne payment kab bola tha?" answers correctly and cites Amit 11:14.
- **Status:** Mitigated (D-08). Measure the remaining risk with the Phase 9 retrieval eval.

### BUG-08: Cleaner turns "₹5000" into "₹500"
- **Context:** Caught by TDD. `clean_text("₹5000 by 20/11 at 5:30")` returned "₹500 ...". This violates TRD §5.3.7: numbers and amounts must stay untouched.
- **Investigation / Steps:** The repeat-collapse regex `(.)\1{2,}` → `\1\1` matched any character, digits included.
- **Resolution:** `_REPEAT = re.compile(r"([^\W\d_])\1{2,}")`, which collapses letters only. The table-driven test `test_clean_text[₹5000...]` passes.
- **Status:** Closed (D-22).

### BUG-09: Dictionary maps "hain" → "hai"
- **Context:** Caught by TDD. "Kl milte hain, hn?" was cleaned to "kal milte hai, haan?".
- **Investigation / Steps:** `hinglish_norm.yaml` listed `hain` as a variant of `hai`, but they're different words (plural vs singular). While reviewing, I found other risky variants: `h` (too short) and `ha` (laughter "ha ha" would become "haan"). A duplicate `paise` entry was also cleaned up.
- **Resolution:** `hai: [hy]`, dropped `hain: []`, `haan: [hn, han, haa]`. All cleaner tests pass.
- **Status:** Closed (D-22).

### BUG-10: Citation points at the question, not the reply
- **Context:** First real end-to-end run. Q1 "client ne payment kab bola tha?" cited Riya's question "Amit ji payment ka kya status hai?" instead of Amit's "paisa 20 tarikh tak". Q3 cited "Rahul tum ... report kab tak bhejoge?" instead of "main kal tak report bhej dunga". The answers themselves were correct.
- **Investigation / Steps:**
  1. Hypothesis: messages were embedded without sender or time, while the answer names both. Offline probe with real BGE-M3 on CPU:
     - Q1 text only: Riya 0.693 > Amit 0.675 (wrong)
     - Q1 formatted `[HH:MM] Sender: text`: Amit 0.808 > Riya 0.738 (fixed)
     - Q3 formatted: Riya 0.698 vs Rahul 0.697 (still a tie)
  2. So similarity alone can't separate a question from its reply. The answer prompt requires "mention who said it and when", and real answers quote the exact time ("11:14", "20:15").
  3. Wrote a failing test first: `test_citation_prefers_message_whose_time_the_answer_mentions`, which failed with `('Riya', '20:10') != ('Rahul', '20:15')`.
- **Resolution:** `app/query/citations.py`: embed the formatted line and add `TIME_MENTION_BOOST = 0.5` when the message's `HH:MM` is in the answer. Verified: the new test passes (56/56), and after restarting the real stack Q1 cites Amit 11:14, Q3 cites Rahul 20:15, and login and deploy cite the right messages.
- **Status:** Closed (D-13). If an answer doesn't quote a time, this falls back to similarity only.

### BUG-11: Upload endpoint fails: python-multipart missing
- **Context:** Test collection for `test_api.py` failed with `RuntimeError: Form data requires "python-multipart" to be installed`.
- **Investigation / Steps:** FastAPI needs `python-multipart` for `UploadFile`, and it isn't a FastAPI dependency.
- **Resolution:** Installed and pinned `python-multipart==0.0.32` in `api/requirements.txt`. The API tests pass.
- **Status:** Closed.

---

## Process notes (self-inflicted, caught before shipping)
- **Line-number `sed` after reformatting:** while fixing a lint error, a `sed '11s/...'` ran after `black` had shifted the lines, and it overwrote the `_URL` regex in `cleaner.py`. Ruff (`F821 Undefined name _URL`) caught it, it was restored, and the URL test passed. This is one reason CLAUDE.md now requires Edit/Write tools instead of shell edits.
- **`pkill -f` killed its own shell:** `pkill -f "uvicorn ... --port 8077"` also matched the shell running it (exit 144), so the cleanup commands chained after it never ran. Run cleanup as a separate command.
