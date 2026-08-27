# Análise de Crédito Automatizada (Serasa → Excel)

Ferramenta que automatiza o processo de avaliação de crédito B2B:

1. Lê o **PDF do Serasa** automaticamente (CNPJ, score, capital social, faturamento, restrições, etc.)
2. Você informa apenas os dados manuais: **limite solicitado**, **4 notas (1-5)** e **responsável**
3. Calcula score interno, classificação final e recomendação (mesmas regras da planilha)
4. **Preenche o Excel modelo** e salva como novo arquivo (histórico)
5. Registra tudo em um **CSV de histórico** (nunca mais perde uma análise)

---

## Requisitos

- **Windows** com Python 3 instalado
  - Baixe em: https://www.python.org/downloads/
  - Na instalação, marque a opção **"Add Python to PATH"**
- **Microsoft Excel** (para abrir os arquivos gerados)

## Instalação (primeira vez)

1. Coloque o arquivo **`pICOLI E DENEGA.xlsx`** (seu modelo) na pasta raiz do programa.
2. Dê dois cliques em **`install.bat`** e aguarde concluir. (só precisa fazer uma vez)

## Como usar (interface gráfica)

1. Gere o **PDF do Serasa** do CNPJ desejado (como já faz hoje).
2. Dê dois cliques em **`start.bat`** — abre a janela da aplicação.
3. Clique em **"Procurar..."** para selecionar o PDF do Serasa.
4. Clique em **"Extrair"** para ler os dados do PDF (aparecem na tela para conferência).
5. Preencha os dados manuais:
   - **Limite solicitado** (R$)
   - **Notas 1-5** para: capacidade financeira, histórico de pagamento, perfil operacional e risco jurídico
   - **Referências comerciais** (Sim/Não)
   - **Responsável** e **observações**
6. Clique em **"Analisar"**.
7. O resultado (score, classificação e recomendação) aparece na tela, e o programa salva:
   - O **Excel** preenchido na pasta `outputs/`
   - O **histórico** em `analysis_history.csv`
8. Use **"Abrir pasta de saída"** para abrir a pasta dos arquivos gerados.

> **Alternativa por linha de comando:** execute `python main.py` e siga as instruções no terminal.

## O que é gerado

```
outputs/
  Credit_Analysis_<RAZAO>_<CNPJ>_<DATA>.xlsx   ← arquivo preenchido (histórico)
analysis_history.csv                           ← registro cumulativo de todas as análises
credit-analysis.log                            ← log de erros (para diagnóstico)
```

## Estrutura do projeto

```
credit-analysis/
├── src/                # código-fonte
│   ├── app.py          # interface gráfica (tkinter)
│   ├── processor.py    # orquestra o fluxo completo da análise
│   ├── pdf_extractor.py# extração dos dados do PDF
│   ├── calculations.py # regras/fórmulas de cálculo
│   ├── excel_writer.py # preenche e salva o Excel
│   ├── history.py      # registro no CSV de histórico
│   ├── config_handler.py # lembra o último PDF/responsável
│   └── logger.py       # logging centralizado (credit-analysis.log)
├── assets/             # recursos (ícones)
├── docs/               # documentação
├── main.py             # interface por linha de comando (CLI)
├── app.spec            # configuração do PyInstaller (.exe)
├── pyproject.toml      # metadados e dependências do projeto
├── install.bat         # instala dependências (1x)
└── start.bat           # inicia a interface gráfica
```

## Geração de executável (.exe) com PyInstaller

Com as dependências instaladas (incluindo o grupo dev com PyInstaller):

```bash
pip install -e ".[dev]"
pyinstaller app.spec
```

O executável será gerado em `dist/`. O arquivo `app.spec` já está configurado para:
- Gerar um **.exe sem console** (janela gráfica apenas)
- Compactar e incluir via `--onefile`/dependências automaticamente

## Ajustar parâmetros

As faixas, pesos e percentuais são lidos da aba **Parâmetros** do Excel. Para mudar regras
de crédito, edite a aba Parâmetros do modelo — as fórmulas do Excel recalculam sozinhas.
Se você quiser que o programa também mude as regras internas, ajuste o dicionário `PARAMS`
em `src/calculations.py`.
