import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config_handler import load_config, save_config
from logger import logger
from processor import process_analysis, find_model
from pdf_extractor import extract_pdf_data

SCORE_LABELS = {
    1: "Muito ruim",
    2: "Ruim",
    3: "Regular",
    4: "Bom",
    5: "Excelente",
}


class CreditAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Análise de Crédito - Serasa")
        self.root.geometry("780x720")
        self.root.minsize(720, 660)

        self.pdf_path = None
        self.pdf_data = None
        self.analysing = False

        config = load_config()
        self.last_pdf_path = config.get("last_pdf_path", "")

        self._build_header()
        self._build_pdf_section()
        self._build_extracted_section()
        self._build_input_section()
        self._build_result_section()
        self._build_footer()

        if self.last_pdf_path:
            self.pdf_var.set(self.last_pdf_path)
            self.pdf_path = self.last_pdf_path

    # ---------- Construção da interface ----------
    def _build_header(self):
        header = ttk.Frame(self.root, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text="Análise de Crédito Automatizada",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(header, text="PDF Serasa  →  Excel com recomendação e histórico",
                  font=("Segoe UI", 10)).pack(anchor="w")

    def _build_pdf_section(self):
        frame = ttk.LabelFrame(self.root, text="1. PDF de origem (Serasa)", padding=12)
        frame.pack(fill="x", padx=16, pady=(4, 8))

        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.pdf_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.pdf_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(row, text="Procurar...", command=self._browse_pdf).pack(side="left")
        ttk.Button(row, text="Extrair", command=self._extract).pack(side="left", padx=(8, 0))

        self.pdf_status = ttk.Label(frame, text="Selecione o PDF do Serasa e clique em 'Extrair'.",
                                    foreground="gray")
        self.pdf_status.pack(anchor="w", pady=(8, 0))

    def _build_extracted_section(self):
        frame = ttk.LabelFrame(self.root, text="Dados extraídos (confira antes da análise)", padding=12)
        frame.pack(fill="x", padx=16, pady=4)

        self.extracted = {}
        labels = [
            ("cnpj", "CNPJ"),
            ("legal_name", "Razão social"),
            ("serasa_score", "Score Serasa"),
            ("share_capital", "Capital social"),
            ("monthly_revenue", "Faturamento mensal"),
        ]
        for key, label in labels:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{label}:", width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value="-")
            ttk.Label(row, textvariable=var, anchor="w").pack(side="left")
            self.extracted[key] = var

    def _build_input_section(self):
        frame = ttk.LabelFrame(self.root, text="2. Dados manuais", padding=12)
        frame.pack(fill="x", padx=16, pady=4)

        grid = ttk.Frame(frame)
        grid.pack(fill="x")

        ttk.Label(grid, text="Limite solicitado (R$):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.limit_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.limit_var, width=24).grid(row=0, column=1, sticky="w", pady=3)

        score_rows = [
            ("Capacidade financeira", "financial"),
            ("Histórico de pagamento", "payment"),
            ("Perfil operacional", "operational"),
            ("Risco jurídico", "legal"),
        ]
        self.score_vars = {}
        for i, (label, key) in enumerate(score_rows, start=1):
            ttk.Label(grid, text=f"{label} (1-5):").grid(row=i, column=0, sticky="w", padx=(0, 8), pady=3)
            self.score_vars[key] = tk.StringVar(value="3")
            ttk.Entry(grid, textvariable=self.score_vars[key], width=24).grid(row=i, column=1, sticky="w", pady=3)

        ttk.Label(grid, text="Referências comerciais OK?:").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=3)
        self.ref_var = tk.StringVar(value="Não")
        ttk.Combobox(grid, textvariable=self.ref_var, values=["Sim", "Não"],
                     state="readonly", width=22).grid(row=5, column=1, sticky="w", pady=3)

        ttk.Label(grid, text="Responsável:").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=3)
        self.analyst_var = tk.StringVar()
        config = load_config()
        self.analyst_var.set(config.get("last_analyst", ""))
        ttk.Entry(grid, textvariable=self.analyst_var, width=24).grid(row=6, column=1, sticky="w", pady=3)

        ttk.Label(grid, text="Observações:").grid(row=7, column=0, sticky="nw", padx=(0, 8), pady=3)
        self.notes_text = tk.Text(grid, width=50, height=3)
        self.notes_text.grid(row=7, column=1, sticky="w", pady=3)

    def _build_result_section(self):
        frame = ttk.LabelFrame(self.root, text="Resultado", padding=12)
        frame.pack(fill="both", expand=True, padx=16, pady=8)

        self.result_var = tk.StringVar(value="Execute a análise para ver a recomendação aqui.")
        ttk.Label(frame, textvariable=self.result_var, wraplength=700, justify="left",
                  font=("Segoe UI", 11)).pack(fill="x")

        self.recommendation_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.recommendation_var,
                  font=("Segoe UI", 14, "bold"), foreground="#1a73e8",
                  wraplength=700, justify="left").pack(anchor="w", pady=(8, 0))

        self.file_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.file_var, foreground="gray", wraplength=700,
                  justify="left").pack(anchor="w", pady=(4, 0))

    def _build_footer(self):
        footer = ttk.Frame(self.root, padding=(16, 10))
        footer.pack(fill="x")
        ttk.Button(footer, text="Analisar", command=self._analyze).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Abrir pasta de saída", command=self._open_output).pack(side="right")
        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 12))

    # ---------- Ações ----------
    def _browse_pdf(self):
        path = filedialog.askopenfilename(
            title="Selecione o PDF do Serasa",
            initialdir=os.path.dirname(self.last_pdf_path) if self.last_pdf_path else "",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.pdf_path = path
            self.pdf_var.set(path)
            save_config(last_pdf_path=path, last_analyst=self.analyst_var.get())
            self.pdf_status.config(text="PDF selecionado. Clique em 'Extrair' para ler os dados.",
                                   foreground="gray")

    def _extract(self):
        if not self.pdf_path:
            messagebox.showwarning("Nenhum PDF", "Selecione um arquivo PDF primeiro.")
            return
        if not os.path.exists(self.pdf_path):
            messagebox.showerror("Erro", f"Arquivo PDF não encontrado:\n{self.pdf_path}")
            return
        try:
            self.pdf_data = extract_pdf_data(self.pdf_path)
        except Exception as e:
            logger.error(f"Falha ao extrair dados do PDF: {e}", exc_info=True)
            messagebox.showerror("Erro de extração", f"Não foi possível ler o PDF:\n{e}")
            return
        self._show_extracted(self.pdf_data)
        self.pdf_status.config(text="Dados extraídos. Confira os valores e preencha os dados manuais.",
                               foreground="green")

    def _show_extracted(self, data):
        self._set_extracted("cnpj", data.get("cnpj", "-"))
        self._set_extracted("legal_name", data.get("legal_name", "-"))
        self._set_extracted("serasa_score", str(data.get("serasa_score", "-")))
        capital = data.get("share_capital")
        self._set_extracted("share_capital", f"R$ {capital:,.2f}" if capital is not None else "-")
        revenue = data.get("monthly_revenue")
        self._set_extracted("monthly_revenue", f"R$ {revenue:,.2f}" if revenue is not None else "-")

    def _set_extracted(self, key, value):
        if key in self.extracted:
            self.extracted[key].set(value)

    def _validate_inputs(self):
        """Valida o formulário. Retorna (inputs, mensagem_de_erro)."""
        if not self.pdf_path:
            return None, "Selecione um arquivo PDF primeiro."
        if self.pdf_data is None:
            return None, "Clique em 'Extrair' para ler os dados do PDF antes de analisar."

        limit_raw = self.limit_var.get().strip()
        if not limit_raw:
            return None, "Informe o limite solicitado."
        limit_str = limit_raw.replace(".", "").replace(",", ".")
        try:
            requested_limit = float(limit_str)
        except ValueError:
            return None, "O limite solicitado deve ser um número."
        if requested_limit < 0:
            return None, "O limite solicitado não pode ser negativo."

        scores = []
        for key in ("financial", "payment", "operational", "legal"):
            raw = self.score_vars[key].get().strip()
            try:
                val = float(raw)
            except ValueError:
                return None, f"A nota de '{key}' deve ser um número."
            if val < 1 or val > 5:
                return None, f"A nota de '{key}' deve estar entre 1 e 5."
            scores.append(val)

        references = "Sim" if self.ref_var.get().strip().lower().startswith("s") else "Não"

        inputs = {
            "requested_limit": requested_limit,
            "scores": tuple(scores),
            "references": references,
            "analyst": self.analyst_var.get().strip(),
            "notes": self.notes_text.get("1.0", "end").strip(),
        }
        return inputs, None

    def _analyze(self):
        if self.analysing:
            return
        inputs, error = self._validate_inputs()
        if error:
            messagebox.showwarning("Verifique os dados", error)
            return

        self.analysing = True
        self.progress.start(12)
        self.result_var.set("Analisando...")
        save_config(last_pdf_path=self.pdf_path, last_analyst=inputs["analyst"])

        thread = threading.Thread(target=self._run_analysis, args=(inputs,), daemon=True)
        thread.start()

    def _run_analysis(self, inputs):
        try:
            result = process_analysis(self.pdf_path, inputs)
            self.root.after(0, self._on_success, result)
        except Exception as e:
            logger.error(f"Falha na análise: {e}", exc_info=True)
            self.root.after(0, self._on_error, str(e))

    def _on_success(self, result):
        self.progress.stop()
        self.analysing = False
        calcs = result["calcs"]

        lines = [
            f"Score interno:       {calcs['internal_score']}",
            f"Classificação interna: {calcs['internal_class']}",
            f"Classificação Serasa:  {calcs['serasa_class']}",
            f"Classificação final:   {calcs['final_class']}",
            f"Limite sugerido:       R$ {calcs['suggested_limit']:,.2f}",
            f"Cobertura:             {calcs['coverage']}",
            f"Índice de exposição:   {calcs['exposure_index']:.3f}",
            f"Alerta de capital:     {calcs['capital_alert']}",
        ]
        self.result_var.set("\n".join(lines))
        self.recommendation_var.set(">>> " + calcs["recommendation"])
        self.file_var.set(f"Arquivo salvo: {result['excel_path']}\n"
                          f"Histórico: {result['history_path']}")

    def _on_error(self, error):
        self.progress.stop()
        self.analysing = False
        self.result_var.set("Falha na análise.")
        self.recommendation_var.set("")
        self.file_var.set("")
        messagebox.showerror("Erro na análise", error)

    def _open_output(self):
        out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(out_dir)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", out_dir])
        else:
            subprocess.Popen(["xdg-open", out_dir])


def main():
    try:
        root = tk.Tk()

        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "credit-analysis.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)

        if not find_model():
            messagebox.showwarning(
                "Modelo Excel não encontrado",
                "Coloque o arquivo 'pICOLI E DENEGA.xlsx' na mesma pasta do programa.",
            )

        app = CreditAnalysisApp(root)
        root.mainloop()
    except Exception as error:
        logger.error(f"Erro ao executar o aplicativo: {error}", exc_info=True)
        messagebox.showerror(
            "Erro",
            "Ocorreu um erro inesperado. Verifique o arquivo credit-analysis.log para mais detalhes.",
        )


if __name__ == "__main__":
    main()
