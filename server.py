#!/usr/bin/env python3
"""
server.py — servidor local para resolução de URLs de artigos via DuckDuckGo.

Uso:
    pip install fastapi uvicorn ddgs
    python3 server.py

Depois abra http://localhost:8000 no browser.
"""

import time
import webbrowser
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ddgs import DDGS

SOURCE_DOMAINS = {
    "folha de são paulo": "folha.uol.com.br",
    "folha de s.paulo": "folha.uol.com.br",
    "folha de pernambuco": "folhape.com.br",
    "gazeta do povo": "gazetadopovo.com.br",
    "veja": "veja.abril.com.br",
    "estado de minas": "em.com.br",
    "correio braziliense": "correiobraziliense.com.br",
    "o globo": "oglobo.globo.com",
    "jc online": "jconline.ne10.uol.com.br",
    "jornal grande bahia": "jornalgrandebahia.com.br",
    "consultor juridico": "conjur.com.br",
    "el país": "elpais.com",
    "el pais": "elpais.com",
    "monitor mercantil": "monitormercantil.com.br",
    "correio do brasil": "correiodobrasil.com.br",
    "infobae": "infobae.com",
    "el nacional": "el-nacional.com",
    "extra online": "extra.globo.com",
    "la prensa": "laprensa.com",
    "milenio": "milenio.com",
    "observador": "observador.pt",
    "ibahia": "ibahia.com",
    "o dia": "odia.com.br",
    "agence france presse": "afpforum.com",
}

app = FastAPI(title="News Report Link Resolver")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HERE = Path(__file__).parent


@app.get("/")
def serve_index():
    """Serve a página web diretamente — sem problema de mixed content."""
    return FileResponse(HERE / "index.html")


class Article(BaseModel):
    title: str
    source: str


class ResolveRequest(BaseModel):
    articles: list[Article]


def resolve_one(title: str, source: str) -> str | None:
    short = title[:80].rstrip()
    domain = SOURCE_DOMAINS.get(source.lower().strip())
    query = f'"{short}" site:{domain}' if domain else f'"{short}" {source}'
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=1))
        if results:
            return results[0]["href"]
    except Exception:
        pass
    return None


@app.get("/ping")
def ping():
    """A página usa este endpoint para detectar se o servidor está ativo."""
    return {"status": "ok"}


@app.post("/resolve")
def resolve(req: ResolveRequest):
    """Recebe lista de artigos e devolve URLs reais para cada um."""
    results = []
    for art in req.articles:
        url = resolve_one(art.title, art.source)
        results.append({
            "title": art.title,
            "source": art.source,
            "url": url,          # None se não encontrado
        })
        time.sleep(0.4)          # cadência para não ser bloqueado pelo DDG
    return {"results": results}


if __name__ == "__main__":
    print("🚀  Servidor iniciado em http://localhost:8000")
    print("    Abrindo o browser automaticamente…\n")
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
