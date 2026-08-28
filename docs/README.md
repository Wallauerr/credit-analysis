# Análise de Crédito Automatizada (Serasa → PDF)

Ferramenta que automatiza o processo de avaliação de crédito B2B:

1. Lê o **PDF do Serasa** automaticamente (CNPJ, score, capital social, faturamento, restrições, etc.)
2. Você informa apenas o **limite solicitado** (em reais, com formatação automática) e o **responsável**
3. Calcula score interno, classificação final e recomendação (regras configuráveis)
4. **Gera um relatório PDF formatado** (com logo, pronto para enviar) e registra no **histórico**
5. Permite **consultar o histórico** das análises direto no app e **abrir o PDF** de cada uma

> Não depende mais de Excel: toda a lógica de cálculo vive no app e o resultado sai em PDF.

---

## Requisitos

- **Windows** com Python 3 instalado
  - Baixe em: <https://www.python.org/downloads/>
  - Na instalação, marque a opção **"Add Python to PATH"**
- **Microsoft Edge/Chrome ou leitor de PDF** para abrir os relatórios gerados

## Como usar

### Opção A — Executável (.exe)

Se você recebeu o arquivo `Analise de Credito.exe`, **basta dar dois cliques** nele para
abrir a janela da aplicação (não precisa instalar Python nem dependências).

### Opção B — Via código (Python)

1. **Instale as dependências uma vez:**

   ```bat
   pip install -r requirements.txt
   ```

2. **Abra a interface:**

   ```bat
   python src\app.py
   ```

## Usando a interface

1. Gere o **PDF do Serasa** do CNPJ desejado (como já faz hoje).
2. Abra a aplicação (`.exe` ou `python src\app.py`).

### Aba "Nova Análise"

3. Clique em **"Procurar..."** para selecionar o PDF do Serasa — os dados são **extraídos
   automaticamente** e aparecem na tela para conferência.
4. Preencha os dados manuais:
   - **Limite solicitado** (R$) — com vírgulas/separador de milhar automáticos
   - **Responsável**
   - **Referências comerciais** (Sim/Não) e **observações** (opcionais)
   - As **notas 1-5** ficam numa seção "avançada" (opcional) e assumem valor 3 por padrão
5. Clique em **"Executar análise"**.
6. O resultado (score, classificação e recomendação) aparece na tela, e o programa salva:
   - O **relatório PDF** formatado na pasta `Análises de Crédito/relatorios/`
   - O **histórico** em `Análises de Crédito/analysis_history.json`
   - (tudo dentro da pasta `Documentos`)

### Aba "Histórico"

- Lista **todas as análises salvas** (data, razão social, CNPJ, score, classe, recomendação, analista).
- Selecione uma e clique em **"Abrir PDF selecionado"** para reabrir o relatório gerado.

### Aba "Configuração"

- Permite **editar a lógica de cálculo** sem mexer no código:
  - Pesos das notas
  - Limites de classificação interna e Serasa
  - Percentuais do faturamento para o limite sugerido
  - Índices de exposição
- As alterações são salvas em `params_config.json` e valem para as próximas análises.
- O botão **"Restaurar padrões"** volta aos valores iniciais.

> **Alternativa por linha de comando:** execute `python main.py` e siga as instruções no terminal.

## O que é gerado

Todas as informações são organizadas numa pasta **dentro de Documentos**, com nomes em pt-BR:

```
Documentos/Análises de Crédito/
├── configs/                    ← configurações e log
│   ├── credit_analysis_config.json  (último PDF/analista)
│   ├── params_config.json           (parâmetros de cálculo editáveis)
│   └── credit-analysis.log          (log de erros para diagnóstico)
├── relatorios/                 ← relatórios PDF gerados
│   └── Relatorio_<RAZAO>_<DATA>.pdf  (relatório formatado)
└── analysis_history.json       ← registro cumulativo das análises (na raiz)
```

## Estrutura do projeto

```
credit-analysis/
├── src/
│   ├── app.py            # interface gráfica (abas: Nova Análise/Histórico/Configuração)
│   ├── processor.py      # orquestra o fluxo completo da análise
│   ├── pdf_extractor.py  # extração dos dados do PDF
│   ├── calculations.py   # regras/fórmulas de cálculo (parâmetros editáveis)
│   ├── pdf_report.py     # geração do relatório PDF formatado
│   ├── history.py        # histórico em JSON para consulta no app
│   ├── config_handler.py # persistência de config e parâmetros
│   ├── paths.py          # resolução de caminhos (fonte e EXE/PyInstaller)
│   └── logger.py         # logging centralizado (credit-analysis.log)
├── assets/               # logo e ícone (Sulmag)
├── docs/                 # documentação
├── main.py               # interface por linha de comando (CLI)
├── app.spec              # configuração do PyInstaller (.exe)
├── pyproject.toml        # metadados e dependências
└── build_exe.bat         # gera o executável .exe (Windows)
```

## Como gerar o executável (.exe)

O projeto é empacotado em **um único `.exe` standalone** com PyInstaller. O executável
**já inclui o Python e todas as bibliotecas**, então quem receber o arquivo **não precisa
instalar nada** — basta dar dois cliques para rodar.

> A geração precisa ser feita **no Windows** (o PyInstaller gera o `.exe` da plataforma onde roda).

### Passo a passo (no Windows)

1. **Instale as dependências** (incluindo o PyInstaller) uma vez:

   ```bat
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **Crie o executável:**

   ```bat
   build_exe.bat
   ```

   ou, manualmente:

   ```bat
   pyinstaller --clean --noconfirm app.spec
   ```

3. O executável será gerado em:

   ```
   dist\Analise de Credito.exe
   ```

4. Para distribuir, basta enviar esse arquivo único a quem precisar usar a ferramenta.

### Observações sobre o `.exe`

- O arquivo **`app.spec`** já está configurado para gerar um **`.exe` sem console** (só a janela
  gráfica) e **embutir o logo** (usado no relatório PDF) e o ícone do app.
- Como o `.exe` é "portátil", os dados gerados (`relatorios/`, `configs/`, `analysis_history.json`)
  ficam **centralizados na pasta `Documentos/Análises de Crédito/`** — não ao lado do `.exe`.
  Assim, é fácil achar e fazer backup, e não depende da pasta onde o executável está.

## Ajustar a lógica de cálculo

Pelo **app**: abra a aba **"Configuração"**, edite os valores e clique em **"Salvar"**.

Pelo **arquivo**: edite o `params_config.json` (gerado em `Documentos/Análises de Crédito/configs/`)
ou os padrões em `DEFAULT_PARAMS` em `src/calculations.py`.

Exemplo de `params_config.json`:

```json
{
  "weight_financial": 0.4,
  "weight_payment_history": 0.3,
  "weight_operational": 0.2,
  "weight_legal": 0.1,
  "low_risk_min_internal": 80,
  "moderate_min_internal": 60,
  "limit_pct_low": 0.2,
  "limit_pct_moderate": 0.1,
  "limit_pct_high": 0.0,
  "exposure_alert": 1.0,
  "exposure_critical": 2.0,
  "serasa_low_min": 700,
  "serasa_moderate_min": 400
}
```
