#!/usr/bin/env python3
"""
add_search_links.py
Resolve URLs reais dos artigos via DuckDuckGo e injeta links diretos em relatórios
HTML de monitoramento de notícias (Factiva / Quarto).

Requer: pip install ddgs

Uso:
    python3 add_search_links.py BRA-2026-05-08.html
    python3 add_search_links.py BRA-2026-05-08.html --output BRA-2026-05-08-links.html
"""

import sys
import re
import time
import argparse
from pathlib import Path
from urllib.parse import quote_plus

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    print("Aviso: instale ddgs para links diretos (pip install ddgs)", file=sys.stderr)

# Mapeamento de nomes de veículos → domínios para busca site-specific
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

STYLE_PRIMARY = (
    "display:inline-block;margin-left:8px;padding:2px 8px;"
    "background:#1a73e8;color:#fff;font-size:11px;font-weight:600;"
    "border-radius:4px;text-decoration:none;font-family:sans-serif;"
    "vertical-align:middle;line-height:1.6;"
)

STYLE_ALT = (
    "display:inline-block;margin-left:4px;padding:2px 8px;"
    "background:#6c757d;color:#fff;font-size:11px;font-weight:600;"
    "border-radius:4px;text-decoration:none;font-family:sans-serif;"
    "vertical-align:middle;line-height:1.6;"
)

STYLE_FALLBACK = (
    "display:inline-block;margin-left:8px;padding:2px 8px;"
    "background:#f0a500;color:#fff;font-size:11px;font-weight:600;"
    "border-radius:4px;text-decoration:none;font-family:sans-serif;"
    "vertical-align:middle;line-height:1.6;"
)


def search_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


def resolve_url(title: str, source: str, domain: str | None) -> str | None:
    """Busca a URL real do artigo via DuckDuckGo. Retorna None se não encontrar."""
    if not HAS_DDGS:
        return None
    query = f'"{title}" site:{domain}' if domain else f'"{title}" {source}'
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=1))
        if results:
            return results[0]["href"]
    except Exception:
        pass
    return None


def build_buttons(title: str, source: str) -> str:
    short = title[:80].rstrip()
    domain = SOURCE_DOMAINS.get(source.lower().strip())

    # --- botão 1: URL real resolvida (ou fallback para busca) ---
    direct = resolve_url(short, source, domain)
    time.sleep(0.4)  # cadência para não ser bloqueado pelo DDG

    if direct:
        btn1 = (
            f'<a href="{direct}" target="_blank" '
            f'rel="noopener" style="{STYLE_PRIMARY}">🔗 Acessar</a>'
        )
    else:
        # fallback: busca site-specific sem btnI (mais honesto que I'm feeling lucky)
        fallback_q = f'"{short}" site:{domain}' if domain else f'"{short}" {source}'
        btn1 = (
            f'<a href="{search_url(fallback_q)}" target="_blank" '
            f'rel="noopener" style="{STYLE_FALLBACK}" title="Link direto não encontrado — abre busca">🔍 Buscar</a>'
        )

    # --- botão 2: alternativa em outras fontes ---
    alt_q = f'"{short}" -{domain}' if domain else f'"{short}"'
    btn2 = (
        f'<a href="{search_url(alt_q)}" target="_blank" '
        f'rel="noopener" style="{STYLE_ALT}">🌐 Alternativa</a>'
    )

    return f'&nbsp;{btn1}&nbsp;{btn2}'


def process_html(html: str) -> tuple[str, int, int]:
    direct_count = 0
    fallback_count = 0

    def replace_bold(match: re.Match) -> str:
        nonlocal direct_count, fallback_count
        inner = match.group(1)
        sep = inner.rfind(" - ")
        if sep == -1:
            return match.group(0)
        title = inner[:sep].strip()
        source = inner[sep + 3:].strip()
        buttons = build_buttons(title, source)
        if "🔗 Acessar" in buttons:
            direct_count += 1
        else:
            fallback_count += 1
        return f"<b>{inner}</b>{buttons}"

    pattern = re.compile(r"<b>([^<]+)</b>", re.IGNORECASE)
    result = pattern.sub(replace_bold, html)
    return result, direct_count, fallback_count


def main():
    parser = argparse.ArgumentParser(description="Injeta links diretos em relatório HTML de notícias")
    parser.add_argument("input", nargs="+", help="Arquivo(s) HTML de entrada")
    parser.add_argument("--output-dir", "-d", help="Pasta de saída (padrão: mesma pasta do arquivo de entrada)")
    args = parser.parse_args()

    for input_arg in args.input:
        input_path = Path(input_arg)
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
        print(f"  ✓ {direct} links diretos  |  {fallback} buscas fallback  →  {output_path}")


if __name__ == "__main__":
    main()
