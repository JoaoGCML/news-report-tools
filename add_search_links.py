#!/usr/bin/env python3
"""
add_search_links.py
Injeta um link direto ("Estou com sorte") em relatórios HTML de monitoramento de notícias.

Quando o veículo é reconhecido, usa site:dominio.com para ir direto ao artigo.
Quando não é reconhecido, busca título + nome do veículo e vai ao primeiro resultado.

Uso:
    python3 add_search_links.py BRA-2026-05-08.html
    python3 add_search_links.py BRA-2026-05-08.html --output BRA-2026-05-08-links.html
"""

import sys
import re
import argparse
from pathlib import Path
from urllib.parse import quote_plus

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


def lucky_url(query: str) -> str:
    """Redireciona direto para o primeiro resultado do Google."""
    return f"https://www.google.com/search?q={quote_plus(query)}&btnI=1"


def search_url(query: str) -> str:
    """Abre a página de resultados do Google."""
    return f"https://www.google.com/search?q={quote_plus(query)}"


def build_link(title: str, source: str) -> str:
    """
    Retorna dois botões:
      🔗 Acessar    — vai direto ao artigo original (I'm feeling lucky + site:)
      🌐 Alternativa — busca resultados em outras fontes (exclui domínio original)
    """
    short_title = title[:80].rstrip()
    source_key = source.lower().strip()
    domain = SOURCE_DOMAINS.get(source_key)

    # --- botão 1: artigo original ---
    if domain:
        primary_query = f'"{short_title}" site:{domain}'
    else:
        primary_query = f'"{short_title}" {source}'
    btn1 = (
        f'<a href="{lucky_url(primary_query)}" target="_blank" '
        f'rel="noopener" style="{STYLE_PRIMARY}">🔗 Acessar</a>'
    )

    # --- botão 2: alternativa aberta ---
    if domain:
        # exclui o veículo original para mostrar cobertura de outras fontes
        alt_query = f'"{short_title}" -{domain}'
    else:
        # sem domínio conhecido: busca ampla pelo título
        alt_query = f'"{short_title}"'
    btn2 = (
        f'<a href="{search_url(alt_query)}" target="_blank" '
        f'rel="noopener" style="{STYLE_ALT}">🌐 Alternativa</a>'
    )

    return f'&nbsp;{btn1}&nbsp;{btn2}'


def process_html(html: str) -> str:
    """Encontra padrões <b>Título - Veículo</b> e injeta o link direto."""

    def replace_bold(match: re.Match) -> str:
        inner = match.group(1)
        sep_idx = inner.rfind(" - ")
        if sep_idx == -1:
            return match.group(0)
        title = inner[:sep_idx].strip()
        source = inner[sep_idx + 3:].strip()
        return f"<b>{inner}</b>{build_link(title, source)}"

    pattern = re.compile(r"<b>([^<]+)</b>", re.IGNORECASE)
    return pattern.sub(replace_bold, html)


def main():
    parser = argparse.ArgumentParser(description="Injeta links diretos em relatório HTML de notícias")
    parser.add_argument("input", help="Arquivo HTML de entrada")
    parser.add_argument("--output", "-o", help="Arquivo HTML de saída (padrão: input com sufixo -links)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Erro: arquivo '{input_path}' não encontrado.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "-links")

    html = input_path.read_text(encoding="utf-8")
    modified = process_html(html)
    output_path.write_text(modified, encoding="utf-8")

    n = modified.count("🌐 Alternativa")
    print(f"✓ {n} links diretos inseridos → {output_path}")


if __name__ == "__main__":
    main()
