# news-report-tools

Scripts para enriquecimento de relatórios HTML de monitoramento de notícias (Factiva / Quarto).

## add_search_links.py

Injeta links de acesso direto em relatórios HTML com snippets no formato Factiva.

Para cada notícia (`<b>Título - Veículo</b>`), adiciona dois botões:

- **🔗 Acessar** — vai direto ao artigo no veículo original via Google ("Estou com sorte" + `site:dominio.com`)
- **🌐 Alternativa** — abre resultados do Google excluindo o domínio original, para encontrar cobertura aberta do mesmo fato

### Uso

```bash
python3 add_search_links.py relatorio.html
python3 add_search_links.py relatorio.html --output relatorio-links.html
```

O arquivo de saída é o HTML original com os botões injetados ao lado de cada headline. Sem dependências externas — só biblioteca padrão do Python 3.

### Adicionar novos veículos

No dicionário `SOURCE_DOMAINS` dentro do script:

```python
"nome do veículo": "dominio.com.br",
```
