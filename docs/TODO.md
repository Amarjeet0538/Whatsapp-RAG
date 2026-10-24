# TODO

## Phase 1: Foundation (LangChain setup)

- [x] Create a Gemini API key and set `GOOGLE_API_KEY` in `.env`
- [x] Pin exact versions in `api/requirements.txt` (LangChain packages, chromadb, sentence-transformers)
- [ ] Add new config keys from TRD §8 (`reranker_model`, `rerank_top_n`, `rrf_k`, `chroma_dir`) to `config.yaml` and `api/app/config.py`
- [ ] `app/llm/`: factories for `ChatGoogleGenerativeAI` (Gemini 3.5 Flash-Lite), `HuggingFaceEmbeddings` (BGE-M3), cross-encoder reranker
- [ ] Smoke test: `ChatGoogleGenerativeAI.with_structured_output(...)` returns valid Pydantic output on a Hinglish prompt
- [ ] `/health` checks DB, Chroma, and Gemini key
- [ ] Chat export parser (Android + iOS) with unit tests
- [ ] Synthetic Hinglish dataset plan (`data/`, `eval/datasets/`)
