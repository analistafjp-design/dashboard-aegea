# Dashboard Executivo

Plataforma web em Python que consolida, em um único sistema, as informações
hoje distribuídas em três arquivos Power BI:

- **Termos / Faturamento**
- **Venda / Implantação**
- **Programação Diária**

Os dados são atualizados pelo navegador, enviando as planilhas Excel — sem
necessidade de editar código.

## Requisitos

- Python 3.11 ou superior

## Instalação

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Configuração opcional: copie `.env.example` para `.env`.

A documentação completa (instalação, páginas, dicionário de indicadores e
conferência com o Power BI) acompanha a aplicação.
