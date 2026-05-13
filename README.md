# news-report-tools

Ferramentas para enriquecer relatórios HTML de monitoramento de notícias prjt com links diretos aos artigos.

---

## add_search_links.py

Para cada notícia no formato `<b>Título - Veículo</b>`, injeta dois botões:

| Button | Colour | Action |
|---|---|---|
| 🔗 Access | Blue | Direct link to the original article (resolved via DuckDuckGo) |
| 🔍 Quick Search | Yellow | Fallback — site-specific Google search when the direct URL is not found |
| 🌐 Related | Grey | Broad Google search — other sources covering the same story |

### Instalação

```bash
pip install ddgs
```

### Uso como script

```bash
# arquivo único
python3 add_search_links.py relatorio.html

# múltiplos arquivos com pasta de saída
python3 add_search_links.py rel1.html rel2.html --output-dir ./processados/
```

### Uso como módulo em pipelines

```python
from pathlib import Path
from add_search_links import process_html, resolve_url, SOURCE_DOMAINS

# processar um HTML
html = Path("relatorio.html").read_text(encoding="utf-8")
modified, direct, fallback = process_html(html)
# modified  → HTML com botões injetados
# direct    → quantidade de links diretos resolvidos
# fallback  → quantidade que caiu na busca Google

# resolver URL de um artigo individualmente
url = resolve_url("Título do artigo", "Nome do Veículo", domain="dominio.com.br")

# adicionar veículos ao mapeamento
SOURCE_DOMAINS["novo veículo"] = "novodominio.com.br"
```

---

## Página web (preview rápido)

[joaogcml.github.io/news-report-tools](https://joaogcml.github.io/news-report-tools)

Versão simplificada no browser — gera os botões com buscas Google (sem resolução de URL direta).
Útil para demonstração ou uso ocasional sem Python.
