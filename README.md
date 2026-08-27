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

1. Coloque o arquivo **`pICOLI E DENEGA.xlsx`** (seu modelo) na MESMA pasta deste programa.
2. Dê dois cliques em **`install.bat`** e aguarde concluir. (só precisa fazer uma vez)

## Como usar

1. Gere o **PDF do Serasa** do CNPJ desejado (como já faz hoje).
2. Dê dois cliques em **`start.bat`**.
3. No prompt, **arraste o arquivo PDF** para a janela e pressione Enter
   (ou digite o caminho completo).
4. Informe:
   - **Limite solicitado** (R$)
   - **Notas 1-5** para: capacidade financeira, histórico de pagamento, perfil operacional e risco jurídico
   - **Referências comerciais** (Sim/Não)
   - **Responsável** e **observações**
5. Pronto! O programa mostra o resultado e salva:
   - O **Excel** preenchido na pasta `outputs/`
   - O **histórico** em `analysis_history.csv`

## O que é gerado

```
outputs/
  Credit_Analysis_<RAZAO>_<CNPJ>_<DATA>.xlsx   ← arquivo preenchido (histórico)
analysis_history.csv                           ← registro cumulativo de todas as análises
```

## Arquivos

| Arquivo | Função |
|---|---|
| `start.bat` | Executa a análise (dê 2 cliques) |
| `install.bat` | Instala dependências (1x) |
| `main.py` | Programa principal |
| `pdf_extractor.py` | Extração dos dados do PDF |
| `calculations.py` | Regras/fórmulas de cálculo |
| `excel_writer.py` | Preenche e salva o Excel |
| `history.py` | Registro no CSV de histórico |

## Ajustar parâmetros

As faixas, pesos e percentuais são lidos da aba **Parâmetros** do Excel. Para mudar regras
de crédito, edite a aba Parâmetros do modelo — as fórmulas do Excel recalculam sozinhas.
Se você quiser que o programa também mude as regras internas, avise o responsável técnico.
