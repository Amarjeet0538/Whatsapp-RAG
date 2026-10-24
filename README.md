# Whatsapp BOT

A WhatsApp bot that answers questions about a group chat (English / Hindi / Hinglish) with cited sources, summarizes unread messages, and tracks action items, decisions, and topics. Built with a Node.js gateway (whatsapp-web.js), a FastAPI backend whose pipelines are LangChain (LCEL) chains, Ollama for the local LLM, BGE-M3 embeddings, and ChromaDB + SQLite FTS5 for hybrid retrieval. Everything runs locally.

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
