# Whatsapp BOT

A WhatsApp bot that answers questions about a group chat (English / Hindi / Hinglish) with cited sources, summarizes unread messages, and tracks action items, decisions, and topics. Built with a Node.js gateway (whatsapp-web.js), a FastAPI backend whose pipelines are LangChain (LCEL) chains, Gemini 3.5 Flash-Lite (Gemini API) as the LLM, local BGE-M3 embeddings and reranker, and ChromaDB + SQLite FTS5 for hybrid retrieval. Chat storage, embeddings and retrieval run locally; only the question and the top excerpts are sent to Gemini.

See [docs/PRD.md](docs/PRD.md) for what we're building and [docs/TRD.md](docs/TRD.md) for how (LangChain design in TRD §2.5).

## Initialize in your Device

#### Python

```
python -m venv .venv
source .venv/bin/activate

# Windows Git Bash:
   source .venv/Scripts/activate

python -m pip install --upgrade pip

pip install -r api/requirements.txt
```

#### Server Start

```
cd api
uvicorn app.main:app --reload
```

#### Copy env

```
cp .env.example .env
```

Set `GOOGLE_API_KEY` (from https://aistudio.google.com/apikey), `API_KEY` and `ID_HASH_SALT` in `.env`.
The first run downloads BGE-M3 and bge-reranker-v2-m3 (~4.5 GB). On a GPU both load in fp16 (~2.3 GB VRAM).

#### Try the MVP (import a chat, ask a question)

```
make run    # in another terminal

curl -X POST -H "X-API-Key: $API_KEY" \
  -F "file=@data/samples/college_project_android.txt" \
  "localhost:8000/api/v1/groups/final-year/import?name=Final%20Year%20Project"

curl -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  localhost:8000/api/v1/groups/final-year/ask \
  -d '{"question": "client ne payment kab bola tha?", "user_id": "Riya"}'
```

`user_id` must be a member of the group. For imported chats that is the sender's display name.
Interactive API docs: http://localhost:8000/docs

#### Tests and lint

```
make test
make lint
```
