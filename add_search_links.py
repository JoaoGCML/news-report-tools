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

    🔗 Acessar    — link direto ao artigo original
    🌐 Alternativa — busca Google excluindo o veículo original
                     (útil para encontrar cobertura aberta do mesmo fato)

Quando a URL real não é encontrada (artigo muito recente, paywall forte,
veículo não indexado), o botão 🔍 Buscar abre a busca site-específica
no Google como fallback.

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
import argparse
from pathlib import Path
from urllib.parse import quote_plus, urlparse

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    print("Aviso: instale ddgs para links diretos  →  pip install ddgs", file=sys.stderr)


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
_STYLE_DIRECT   = "display:inline-block;margin-left:8px;padding:2px 8px;background:#1a73e8;color:#fff;font-size:11px;font-weight:600;border-radius:4px;text-decoration:none;font-family:sans-serif;vertical-align:middle;line-height:1.6;"
_STYLE_FALLBACK = "display:inline-block;margin-left:8px;padding:2px 8px;background:#f0a500;color:#fff;font-size:11px;font-weight:600;border-radius:4px;text-decoration:none;font-family:sans-serif;vertical-align:middle;line-height:1.6;"
_STYLE_ALT      = "display:inline-block;margin-left:4px;padding:2px 8px;background:#6c757d;color:#fff;font-size:11px;font-weight:600;border-radius:4px;text-decoration:none;font-family:sans-serif;vertical-align:middle;line-height:1.6;"


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

    # verifica overlap de palavras título ↔ slug apenas quando o slug é legível
    slug_words = re.findall(r"\w{4,}", _normalize(path))
    if len(slug_words) >= 3 and title:
        title_words = set(re.findall(r"\w{5,}", _normalize(title)))
        matches = sum(1 for w in title_words if w in path.lower())
        if matches < 3:
            return False

    return True


def resolve_url(title: str, source: str, domain: str | None = None) -> str | None:
    """
    Resolve a URL real de um artigo via DuckDuckGo.

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
    short = title[:120].rstrip()
    query = f'"{short}" site:{domain}' if domain else f'"{short}" {source}'
    try:
        with DDGS() as ddgs:
            # 1ª tentativa: últimos 30 dias — evita artigos antigos com título similar
            # (ex: "PCC há 20 anos" não retorna artigos de 2006)
            try:
                results = list(ddgs.text(query, max_results=2, timelimit="m"))
            except Exception:
                results = []

            # 2ª tentativa: sem filtro de tempo se não encontrou no mês
            if not results:
                results = list(ddgs.text(query, max_results=2))

        # filtra URLs inválidas e artigos claramente errados
        articles = [r for r in results if _is_article_url(r["href"], title)]
        if articles:
            return articles[0]["href"]
    except Exception:
        pass
    return None


def _build_buttons(title: str, source: str) -> str:
    """Retorna o HTML dos botões para um par (título, veículo)."""
    short  = title[:120].rstrip()
    domain = SOURCE_DOMAINS.get(source.lower().strip())

    direct = resolve_url(short, source, domain)
    time.sleep(0.4)  # cadência para não ser bloqueado pelo DDG

    if direct:
        btn1 = f'<a href="{direct}" target="_blank" rel="noopener" style="{_STYLE_DIRECT}">🔗 Acessar</a>'
    else:
        fallback_q = f'"{short}" site:{domain}' if domain else f'"{short}" {source}'
        btn1 = f'<a href="{_google(fallback_q)}" target="_blank" rel="noopener" style="{_STYLE_FALLBACK}" title="URL direta não encontrada — abre busca">🔍 Buscar</a>'

    # Alternativa: sem aspas e sem exclusão — busca ampla pelo mesmo fato,
    # inclui o veículo original para garantir resultados
    alt_q = title[:80].rstrip()
    btn2 = f'<a href="{_google(alt_q)}" target="_blank" rel="noopener" style="{_STYLE_ALT}">🌐 Alternativa</a>'

    return f'&nbsp;{btn1}&nbsp;{btn2}'


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
    direct_count = fallback_count = 0

    def _replace(match: re.Match) -> str:
        nonlocal direct_count, fallback_count
        inner = match.group(1)
        sep = inner.rfind(" - ")
        if sep == -1:
            return match.group(0)
        title  = inner[:sep].strip()
        source = inner[sep + 3:].strip()
        buttons = _build_buttons(title, source)
        if "🔗 Acessar" in buttons:
            direct_count += 1
        else:
            fallback_count += 1
        return f"<b>{inner}</b>{buttons}"

    modified = re.compile(r"<b>([^<]+)</b>", re.IGNORECASE).sub(_replace, html)
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
        html = input_path.read_text(encoding="utf-8")
        modified, direct, fallback = process_html(html)
        output_path.write_text(modified, encoding="utf-8")
        print(f"  ✓ {direct} links diretos  |  {fallback} fallbacks  →  {output_path}")


if __name__ == "__main__":
    main()
