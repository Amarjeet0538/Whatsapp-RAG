from fastapi import FastAPI

app = FastAPI(title="WhatsApp RAG Assistant", version="0.1.0")


@app.get("/api/v1/health")
def health():
    return {"status": "I am just fine gng!!"}
