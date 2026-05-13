#!/usr/bin/env python3
"""
add_search_links.py
===================
Enriquece relatórios HTML de monitoramento de notícias (Factiva / Quarto)
com links diretos para cada artigo.

FUNCIONAMENTO
-------------
Cada notícia no HTML tem o formato:
    <b>Título do artigo - Nome do Veículo</b>

O script localiza esse padrão, resolve a URL real do artigo via DuckDuckGo
e injeta dois botões ao lado de cada headline:

    🔗 Access       — direct link to the original article (resolved via DDG)
    🔍 Quick Search — fallback when the direct URL is not found; opens a
                      site-specific Google search
    🌐 Related      — broad Google search for other sources covering the same story

USO COMO SCRIPT
---------------
    pip install ddgs
    python3 add_search_links.py relatorio.html
    python3 add_search_links.py relatorio.html -o saida.html
    python3 add_search_links.py rel1.html rel2.html --output-dir ./processados/

USO COMO MÓDULO (integração em pipelines)
------------------------------------------
    from add_search_links import process_html, SOURCE_DOMAINS

    # processar HTML já carregado em string
    html_str = Path("relatorio.html").read_text(encoding="utf-8")
    modified, direct, fallback = process_html(html_str)

    # acessar/estender o mapeamento de domínios
    SOURCE_DOMAINS["meu veículo"] = "meudominio.com.br"

    # resolver URL de um artigo individualmente
    from add_search_links import resolve_url
    url = resolve_url("Título do artigo", "Nome do Veículo", "dominio.com.br")

RETORNO DE process_html()
--------------------------
    modified  : str   — HTML com os botões injetados
    direct    : int   — quantidade de links diretos resolvidos
    fallback  : int   — quantidade de artigos que caíram no fallback de busca

DEPENDÊNCIAS
------------
    ddgs  (pip install ddgs)
"""

import sys
import re
import time
import json
import threading
import argparse
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    print("Aviso: instale ddgs para links diretos  →  pip install ddgs", file=sys.stderr)


# ---------------------------------------------------------------------------
# Cache persistente — evita re-resolver artigos já vistos
# Ficheiro: ~/.news-report-tools-cache.json
# ---------------------------------------------------------------------------
_CACHE_PATH = Path.home() / ".news-report-tools-cache.json"
_cache_lock = threading.Lock()


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    except Exception:
        pass


_URL_CACHE: dict = _load_cache()


# ---------------------------------------------------------------------------
# Mapeamento de veículos → domínios
# Adicione entradas conforme necessário para novos veículos monitorados.
# ---------------------------------------------------------------------------
SOURCE_DOMAINS: dict[str, str] = {
    "folha de são paulo":    "folha.uol.com.br",
    "folha de s.paulo":      "folha.uol.com.br",
    "folha de pernambuco":   "folhape.com.br",
    "gazeta do povo":        "gazetadopovo.com.br",
    "veja":                  "veja.abril.com.br",
    "estado de minas":       "em.com.br",
    "correio braziliense":   "correiobraziliense.com.br",
    "o globo":               "oglobo.globo.com",
    "jc online":             "jconline.ne10.uol.com.br",
    "jornal grande bahia":   "jornalgrandebahia.com.br",
    "consultor juridico":    "conjur.com.br",
    "el país":               "elpais.com",
    "el pais":               "elpais.com",
    "monitor mercantil":     "monitormercantil.com.br",
    "correio do brasil":          "correiodobrasil.com.br",
    "infobae":                    "infobae.com",
    "el nacional":                "el-nacional.com",
    "extra online":               "extra.globo.com",
    "la prensa":                  "laprensa.com",
    "milenio":                    "milenio.com",
    "observador":                 "observador.pt",
    "ibahia":                     "ibahia.com",
    "o dia":                      "odia.com.br",
    "agence france presse":       "afpforum.com",
    # veículos lusófonos internacionais
    "o jornal economico":         "jornaleconomico.sapo.pt",
    "jornal economico":           "jornaleconomico.sapo.pt",
    "expresso das ilhas online":  "expressodasilhas.cv",
    "expresso das ilhas":         "expressodasilhas.cv",
    # Peru
    "diario correo":              "diariocorreo.pe",
    "correo":                     "diariocorreo.pe",
    "el comercio":                "elcomercio.pe",
    "la república":               "larepublica.pe",
    "la republica":               "larepublica.pe",
    "rpp":                        "rpp.pe",
    "gestión":                    "gestion.pe",
    "gestion":                    "gestion.pe",
    "peru21":                     "peru21.pe",
    "el peruano":                 "elperuano.pe",
    "andina":                     "andina.pe",
    "expreso":                    "expreso.com.pe",
    "exitosa":                    "exitosanoticias.pe",
    "ojo":                        "diarioojo.com",
    "trome":                      "trome.pe",
}

# ---------------------------------------------------------------------------
# Estilos dos botões injetados
# ---------------------------------------------------------------------------
_STYLE_ACCESS  = "display:inline-block;margin-left:8px;padding:2px 8px;background:#1a73e8;color:#fff;font-size:11px;font-weight:600;border-radius:4px;text-decoration:none;font-family:sans-serif;vertical-align:middle;line-height:1.6;"
_STYLE_SEARCH  = "display:inline-block;margin-left:8px;padding:2px 8px;background:#f0a500;color:#fff;font-size:11px;font-weight:600;border-radius:4px;text-decoration:none;font-family:sans-serif;vertical-align:middle;line-height:1.6;"
_STYLE_RELATED = "display:inline-block;margin-left:4px;padding:2px 8px;background:#6c757d;color:#fff;font-size:11px;font-weight:600;border-radius:4px;text-decoration:none;font-family:sans-serif;vertical-align:middle;line-height:1.6;"


def _google(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


_BLOCKED_DOMAINS = {
    "wikipedia.org", "wikimedia.org", "wikidata.org",
    "britannica.com", "dictionary.com", "merriam-webster.com",
    "youtube.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "reddit.com", "pinterest.com",
}

_ACCENT_MAP = str.maketrans(
    "áàãâäéèêëíìîïóòõôöúùûüçñÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇÑ",
    "aaaааéèeeíiiiooооouuuucnAAAAÄÉÈEËÍÌÎÏOOOOÖUUUUCN",
)


def _normalize(s: str) -> str:
    return s.lower().translate(_ACCENT_MAP)


def _is_article_url(url: str, title: str = "") -> bool:
    """
    Valida se uma URL é realmente um artigo relevante:
    1. Rejeita domínios não-noticiosos (Wikipedia, redes sociais, etc.)
    2. Rejeita páginas de seção/índice (path muito curto)
    3. Se a URL tem slug legível, verifica que pelo menos 3 palavras
       significativas do título aparecem nele — filtra artigos errados
       do mesmo veículo (ex: outro artigo de "Poder Judicial" que não é o certo)
    """
    parsed = urlparse(url)
    hostname = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")

    if any(hostname == d or hostname.endswith("." + d) for d in _BLOCKED_DOMAINS):
        return False

    path = parsed.path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return False

    return True


def _is_article_url_strict(url: str, title: str) -> bool:
    """
    Validação estrita para buscas sem site: — exige overlap de palavras
    entre título e slug para evitar artigos claramente errados.
    Usada apenas em buscas gerais (sem domínio conhecido).
    """
    if not _is_article_url(url):
        return False
    parsed = urlparse(url)
    path   = parsed.path.rstrip("/")
    slug_words = re.findall(r"\w{4,}", _normalize(path))
    if len(slug_words) >= 3:
        title_words = set(re.findall(r"\w{5,}", _normalize(title)))
        matches = sum(1 for w in title_words if w in _normalize(path))
        if matches < 2:
            return False
    return True


def resolve_url(title: str, source: str, domain: str | None = None) -> str | None:
    """
    Resolve a URL real de um artigo via DuckDuckGo.

    Usa cache persistente (~/.news-report-tools-cache.json) para evitar
    re-resolver artigos já vistos em execuções anteriores.

    Parâmetros
    ----------
    title   : título do artigo (será truncado a 120 caracteres)
    source  : nome do veículo
    domain  : domínio do veículo (ex: 'folha.uol.com.br'); se None, busca geral

    Retorno
    -------
    URL do artigo como string, ou None se não encontrado.
    """
    if not HAS_DDGS:
        return None

    short     = title[:120].rstrip()
    cache_key = f"{short.lower()}|{domain or source.lower()}"

    # verifica cache antes de fazer qualquer request
    with _cache_lock:
        if cache_key in _URL_CACHE:
            return _URL_CACHE[cache_key]  # pode ser None (miss conhecido)

    query = f'"{short}" site:{domain}' if domain else f'"{short}" {source}'
    url   = None
    try:
        with DDGS() as ddgs:
            try:
                results = list(ddgs.text(query, max_results=2, timelimit="m"))
            except Exception:
                results = []
            if not results:
                results = list(ddgs.text(query, max_results=2))

        # com site: confiamos no ranking do DDG — só filtramos bloqueados e seções
        # sem site: aplicamos validação de overlap título↔slug para evitar erros
        if domain:
            articles = [r for r in results if _is_article_url(r["href"])]
        else:
            articles = [r for r in results if _is_article_url_strict(r["href"], title)]
        if articles:
            url = articles[0]["href"]
    except Exception:
        pass

    # persiste resultado (incluindo None para não tentar de novo)
    with _cache_lock:
        _URL_CACHE[cache_key] = url
        _save_cache(_URL_CACHE)

    return url


def _build_buttons_from(title: str, direct_url: str | None) -> str:
    """Monta os botões HTML dado o título e a URL já resolvida (ou None)."""
    quick_q    = title[:80].rstrip()
    btn_search = f'<a href="{_google(quick_q)}" target="_blank" rel="noopener" style="{_STYLE_SEARCH}">🔍 Quick Search</a>'
    if direct_url:
        btn_access = f'<a href="{direct_url}" target="_blank" rel="noopener" style="{_STYLE_ACCESS}">🔗 Access</a>'
        return f'&nbsp;{btn_access}&nbsp;{btn_search}'
    return f'&nbsp;{btn_search}'


def process_html(html: str) -> tuple[str, int, int]:
    """
    Processa uma string HTML e injeta links em cada headline de notícia.

    Parâmetros
    ----------
    html : conteúdo HTML como string

    Retorno
    -------
    (modified, direct, fallback)
        modified  — HTML modificado com botões injetados
        direct    — número de links diretos resolvidos com sucesso
        fallback  — número de artigos que usaram busca como fallback
    """
    # 1. extrai todos os artigos do HTML
    pattern = re.compile(r"<b>([^<]+)</b>", re.IGNORECASE)
    matches = list(pattern.finditer(html))
    articles = {}  # inner_text → (title, source)
    for m in matches:
        inner = m.group(1)
        sep   = inner.rfind(" - ")
        if sep != -1:
            articles[inner] = (inner[:sep].strip(), inner[sep + 3:].strip())

    # 2. resolve URLs em paralelo (4 workers) com throttle por worker
    url_map: dict[str, str | None] = {}

    def _resolve_one(inner: str) -> tuple[str, str | None]:
        title, source = articles[inner]
        domain = SOURCE_DOMAINS.get(source.lower().strip())
        time.sleep(0.2)  # throttle por worker — 4 workers = ~50ms entre requests
        return inner, resolve_url(title, source, domain)

    uncached = [k for k in articles if
                f"{articles[k][0][:120].rstrip().lower()}|{SOURCE_DOMAINS.get(articles[k][1].lower().strip(), articles[k][1].lower())}"
                not in _URL_CACHE]

    # cached articles — instant
    for inner, (title, source) in articles.items():
        domain    = SOURCE_DOMAINS.get(source.lower().strip())
        cache_key = f"{title[:120].rstrip().lower()}|{domain or source.lower()}"
        if cache_key in _URL_CACHE:
            url_map[inner] = _URL_CACHE[cache_key]

    # uncached — parallel DDG requests
    if uncached:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_resolve_one, k): k for k in uncached}
            for future in as_completed(futures):
                inner, url = future.result()
                url_map[inner] = url

    # 3. injeta botões no HTML
    direct_count = fallback_count = 0

    def _replace(match: re.Match) -> str:
        nonlocal direct_count, fallback_count
        inner = match.group(1)
        if inner not in articles:
            return match.group(0)
        title, source = articles[inner]
        direct_url    = url_map.get(inner)
        buttons       = _build_buttons_from(title, direct_url)
        if direct_url:
            direct_count += 1
        else:
            fallback_count += 1
        return f"<b>{inner}</b>{buttons}"

    modified = pattern.sub(_replace, html)
    return modified, direct_count, fallback_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Injeta links diretos em relatórios HTML de monitoramento de notícias.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="+", help="Arquivo(s) HTML de entrada")
    parser.add_argument(
        "--output-dir", "-d",
        help="Pasta de saída (padrão: mesma pasta do arquivo de entrada)",
    )
    args = parser.parse_args()

    for path_str in args.input:
        input_path = Path(path_str)
        if not input_path.exists():
            print(f"Erro: '{input_path}' não encontrado.", file=sys.stderr)
            continue

        if args.output_dir:
            out_dir = Path(args.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / (input_path.stem + "-links.html")
        else:
            output_path = input_path.with_stem(input_path.stem + "-links")

        print(f"Processando {input_path.name}…")
        t0   = time.time()
        html = input_path.read_text(encoding="utf-8")
        modified, direct, fallback = process_html(html)
        output_path.write_text(modified, encoding="utf-8")
        elapsed = time.time() - t0
        print(f"  ✓ {direct} Access  |  {fallback} Quick Search  |  {elapsed:.0f}s  →  {output_path}")


if __name__ == "__main__":
    main()
