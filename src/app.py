import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config_handler import load_config, save_config, load_params, save_params
from logger import logger
from processor import process_analysis
from pdf_extractor import extract_pdf_data
from history import load_history
from calculations import DEFAULT_PARAMS
from paths import reports_dir, assets_dir

SCORE_LABELS = {
    1: "Muito ruim",
    2: "Ruim",
    3: "Regular",
    4: "Bom",
    5: "Excelente",
}


class CurrencyEntry(ttk.Entry):
    """Campo de entrada monetária em reais com formatação automática.

    O usuário digita o valor (inteiros) e o campo insere o separador de
    milhar (ponto) automaticamente. Uma vírgula pode ser digitada para as
    casas decimais. Ex.: digitar 15000 mostra "15.000"; 15000,5 -> "15.000,5".

    Retorna o valor numérico via .get_value().
    """

    def __init__(self, master, **kwargs):
        self._value_var = tk.StringVar()
        kwargs["textvariable"] = self._value_var
        super().__init__(master, justify="right", **kwargs)
        self._value_var.trace_add("write", self._format)

    def _format(self, *args):
        # Remove os próximos callbacks deste rastreio antes de alterar o valor
        for _mode, cb in list(self._value_var.trace_info()):
            self._value_var.trace_remove("write", cb)

        text = self._value_var.get()

        # Separa parte inteira da decimal (vírgula = separador decimal)
        if "," in text:
            int_raw, dec_raw = text.split(",", 1)
            dec = "".join(c for c in dec_raw if c.isdigit())[:2]
        else:
            int_raw, dec = text, ""
        int_raw = "".join(c for c in int_raw if c.isdigit())

        int_fmt = f"{int(int_raw):,}".replace(",", ".") if int_raw else ""
        new_text = int_fmt if not dec else f"{int_fmt},{dec}"
        if new_text != text:
            self._value_var.set(new_text)

        # Reinscreve o rastreio
        self._value_var.trace_add("write", self._format)

    def get_value(self):
        """Return the numeric float, or None if empty/invalid."""
        raw = self._value_var.get().strip()
        if not raw:
            return None
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None


class ScrollableFrame(ttk.Frame):
    """A frame whose content scrolls vertically, so it stays usable in small
    windows. Child widgets must be added to the `.inner` frame."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self.canvas)
        self._window_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )

        self._can_scroll = False

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Rolagem por mouse wheel (diferentes plataformas)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner.bind("<MouseWheel>", self._on_mousewheel)
        self.vscroll.bind("<MouseWheel>", self._on_mousewheel)

    def _update_scrollability(self):
        """Mostra a scrollbar (e habilita o scroll) apenas quando o conteúdo
        excede a altura visível do canvas."""
        content_h = self.canvas.bbox("all")
        content_h = content_h[3] if content_h else 0
        vis_h = self.canvas.winfo_height()

        overflow = content_h > vis_h + 1
        self._can_scroll = overflow

        if overflow:
            self.vscroll.pack(side="right", fill="y")
        else:
            self.vscroll.pack_forget()
            self.canvas.yview_moveto(0.0)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollability()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window_id, width=event.width)
        self._update_scrollability()

    def _on_mousewheel(self, event):
        if not self._can_scroll:
            return
        # Windows/macOS: delta é ±120; Linux: pode ser ±1 (units) ou evento diferente
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-int(event.delta / 120), "units")


class CreditAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Análise de Crédito - Serasa")
        self.root.geometry("820x780")
        self.root.minsize(760, 700)

        self.pdf_path = None
        self.pdf_data = None
        self.analysing = False

        config = load_config()
        self.last_pdf_path = config.get("last_pdf_path", "")

        # Notebook with tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_analysis = ttk.Frame(self.notebook)
        self.tab_history = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_analysis, text="Nova Análise")
        self.notebook.add(self.tab_history, text="Histórico")
        self.notebook.add(self.tab_config, text="Configuração")

        self._build_analysis_tab()
        self._build_history_tab()
        self._build_config_tab()

        if self.last_pdf_path:
            self.pdf_var.set(self.last_pdf_path)
            self.pdf_path = self.last_pdf_path

        self._refresh_history()

    # ================= ABAS =================
    def _build_analysis_tab(self):
        tab = self.tab_analysis

        scroller = ScrollableFrame(tab)
        scroller.pack(fill="both", expand=True, padx=4)
        body = scroller.inner

        self._build_header(body)
        self._build_pdf_section(body)
        self._build_extracted_section(body)
        self._build_input_section(body)
        self._build_result_section(body)
        self._build_footer(body)

    def _build_history_tab(self):
        tab = self.tab_history

        scroller = ScrollableFrame(tab)
        scroller.pack(fill="both", expand=True, padx=4)
        body = scroller.inner

        top = ttk.Frame(body, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(
            top, text="Histórico de análises", font=("Segoe UI", 14, "bold")
        ).pack(side="left")
        ttk.Button(top, text="Atualizar", command=self._refresh_history).pack(
            side="right"
        )

        info = ttk.Label(
            body,
            text="A lista mostra todas as análises salvas. Selecione uma e clique "
            "em 'Abrir PDF' para visualizar o relatório gerado.",
            foreground="gray",
            wraplength=750,
            justify="left",
        )
        info.pack(anchor="w", padx=12, pady=(0, 6))

        columns = (
            "date",
            "name",
            "cnpj",
            "score",
            "class",
            "recommendation",
            "analyst",
        )
        body_list = ttk.Frame(body)
        body_list.pack(fill="both", expand=True, padx=(12, 0), pady=6)
        self.history_tree = ttk.Treeview(
            body_list,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=12,
        )
        self.history_tree.heading("date", text="Data")
        self.history_tree.heading("name", text="Razão social")
        self.history_tree.heading("cnpj", text="CNPJ")
        self.history_tree.heading("score", text="Score")
        self.history_tree.heading("class", text="Classe")
        self.history_tree.heading("recommendation", text="Recomendação")
        self.history_tree.heading("analyst", text="Analista")

        self.history_tree.column("date", width=130, anchor="center")
        self.history_tree.column("name", width=220)
        self.history_tree.column("cnpj", width=130, anchor="center")
        self.history_tree.column("score", width=55, anchor="center")
        self.history_tree.column("class", width=110, anchor="center")
        self.history_tree.column("recommendation", width=200)
        self.history_tree.column("analyst", width=90)

        vsb = ttk.Scrollbar(
            body_list, orient="vertical", command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=vsb.set)
        self.history_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        bottom = ttk.Frame(body, padding=12)
        bottom.pack(fill="x")
        ttk.Button(
            bottom, text="Abrir PDF selecionado", command=self._open_selected_report
        ).pack(side="left")
        ttk.Button(
            bottom, text="Abrir pasta de relatórios", command=self._open_output
        ).pack(side="left", padx=(8, 0))

    def _build_config_tab(self):
        tab = self.tab_config
        scroller = ScrollableFrame(tab)
        scroller.pack(fill="both", expand=True, padx=4)
        padding = ttk.Frame(scroller.inner, padding=16)
        padding.pack(fill="x")

        ttk.Label(
            padding,
            text="Configuração de parâmetros de cálculo",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            padding,
            text="Edite os parâmetros usados na lógica de cálculo. As alterações "
            "são salvas em params_config.json e valem para as próximas análises.",
            foreground="gray",
            wraplength=750,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self.params_vars = {}

        def group(title):
            f = ttk.LabelFrame(padding, text=title, padding=10)
            f.pack(fill="x", pady=4)
            return f

        # Weights
        fw = group("Pesos das notas (devem somar 1.0)")
        weight_rows = [
            ("weight_financial", "Capacidade financeira"),
            ("weight_payment_history", "Histórico de pagamento"),
            ("weight_operational", "Perfil operacional"),
            ("weight_legal", "Risco jurídico"),
        ]
        self._add_param_row(fw, weight_rows)

        # Internal classification
        fi = group("Classificação interna (limites de score 0-100)")
        internal_rows = [
            ("low_risk_min_internal", "Baixo risco a partir de"),
            ("moderate_min_internal", "Risco moderado a partir de"),
        ]
        self._add_param_row(fi, internal_rows)

        # SERASA classification
        fs = group("Classificação Serasa (limites de score 0-1000)")
        serasa_rows = [
            ("serasa_low_min", "Baixo risco a partir de"),
            ("serasa_moderate_min", "Risco moderado a partir de"),
        ]
        self._add_param_row(fs, serasa_rows)

        # Limit percentages
        fl = group("Percentual do faturamento p/ limite sugerido")
        limit_rows = [
            ("limit_pct_low", "Baixo risco"),
            ("limit_pct_moderate", "Risco moderado"),
            ("limit_pct_high", "Alto risco"),
        ]
        self._add_param_row(fl, limit_rows)

        # Exposure
        fe = group("Índices de exposição (limite solicitado / capital social)")
        exposure_rows = [
            ("exposure_alert", "Acima do capital social se"),
            ("exposure_critical", "Exposição muito alta se"),
        ]
        self._add_param_row(fe, exposure_rows)

        # Actions
        actions = ttk.Frame(padding)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Salvar", command=self._save_params).pack(side="left")
        ttk.Button(actions, text="Restaurar padrões", command=self._reset_params).pack(
            side="left", padx=(8, 0)
        )
        self.params_status = ttk.Label(actions, text="", foreground="green")
        self.params_status.pack(side="left", padx=(12, 0))

    def _add_param_row(self, parent, rows):
        for i, (key, label) in enumerate(rows):
            rowf = ttk.Frame(parent)
            rowf.pack(fill="x", pady=2)
            ttk.Label(rowf, text=label + ":", width=38, anchor="w").pack(side="left")
            var = tk.StringVar()
            rowf_entry = ttk.Entry(rowf, textvariable=var, width=18)
            rowf_entry.pack(side="left")
            self.params_vars[key] = var
        self._load_params_into_vars()

    def _load_params_into_vars(self):
        params = load_params()
        merged = dict(DEFAULT_PARAMS)
        merged.update({k: v for k, v in params.items() if k in DEFAULT_PARAMS})
        for key, var in self.params_vars.items():
            var.set(merged.get(key, ""))

    # ================= NOVA ANÁLISE =================
    def _build_header(self, parent):
        header = ttk.Frame(parent, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Análise de Crédito Automatizada",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="PDF Serasa  →  Relatório PDF formatado + histórico",
            font=("Segoe UI", 10),
        ).pack(anchor="w")

    def _build_pdf_section(self, parent):
        frame = ttk.LabelFrame(parent, text="1. PDF de origem (Serasa)", padding=12)
        frame.pack(fill="x", padx=16, pady=(4, 8))

        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.pdf_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.pdf_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(row, text="Procurar...", command=self._browse_pdf).pack(side="left")

        self.pdf_status = ttk.Label(
            frame,
            text="Selecione o PDF do Serasa. Os dados são extraídos automaticamente.",
            foreground="gray",
        )
        self.pdf_status.pack(anchor="w", pady=(8, 0))

    def _build_extracted_section(self, parent):
        frame = ttk.LabelFrame(
            parent, text="Dados extraídos (confira antes da análise)", padding=12
        )
        frame.pack(fill="x", padx=16, pady=4)

        self.extracted = {}
        labels = [
            ("cnpj", "CNPJ"),
            ("legal_name", "Razão social"),
            ("serasa_score", "Score Serasa"),
            ("share_capital", "Capital social"),
            ("monthly_revenue", "Faturamento mensal"),
            ("segment", "Segmento"),
        ]
        for key, label in labels:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{label}:", width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value="-")
            ttk.Label(row, textvariable=var, anchor="w").pack(side="left")
            self.extracted[key] = var

    def _build_input_section(self, parent):
        frame = ttk.LabelFrame(parent, text="2. Dados da análise", padding=12)
        frame.pack(fill="x", padx=16, pady=4)

        grid = ttk.Frame(frame)
        grid.pack(fill="x")

        # Campos principais
        ttk.Label(grid, text="Limite solicitado (R$):").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3
        )
        self.limit_entry = CurrencyEntry(grid, width=24)
        self.limit_entry.grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(grid, text="Responsável:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3
        )
        self.analyst_var = tk.StringVar()
        config = load_config()
        self.analyst_var.set(config.get("last_analyst", ""))
        ttk.Entry(grid, textvariable=self.analyst_var, width=24).grid(
            row=1, column=1, sticky="w", pady=3
        )

        ttk.Label(grid, text="Referências comerciais OK?:").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3
        )
        self.ref_var = tk.StringVar(value="Não")
        ttk.Combobox(
            grid,
            textvariable=self.ref_var,
            values=["Sim", "Não"],
            state="readonly",
            width=22,
        ).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(grid, text="Observações:").grid(
            row=3, column=0, sticky="nw", padx=(0, 8), pady=3
        )
        self.notes_text = tk.Text(grid, width=50, height=2)
        self.notes_text.grid(row=3, column=1, sticky="w", pady=3)

        # Seção avançada (notas 1-5) - opcional, pode ser expandida
        self.adv_open = False
        adv_header = ttk.Frame(frame)
        adv_header.pack(fill="x", pady=(10, 0))
        self.adv_btn = ttk.Button(
            adv_header,
            text="▶ Notas da análise (opcional - ver/ajustar)",
            command=self._toggle_advanced,
        )
        self.adv_btn.pack(anchor="w")

        self.adv_frame = ttk.Frame(frame)
        # Note grid will be built inside adv_frame when expanded

        self.adv_hint = ttk.Label(
            adv_header,
            text="As notas permitem ajustar a avaliação (1 a 5). "
            "Por padrão são calculadas automaticamente a partir do PDF do Serasa.",
            foreground="gray",
            wraplength=700,
            justify="left",
        )
        self.adv_hint.pack(anchor="w", pady=(2, 0))

        # Auto-scores toggle (default on)
        self.auto_scores_enabled = tk.BooleanVar(value=True)

        self.auto_toggle = ttk.Checkbutton(
            adv_header,
            text="Calcular notas automaticamente a partir do PDF",
            variable=self.auto_scores_enabled,
            command=self._toggle_auto_scores,
        )
        self.auto_toggle.pack(anchor="w", pady=(4, 0))

        # Score vars (default 3)
        self.score_vars = {
            "financial": tk.StringVar(value="3"),
            "payment": tk.StringVar(value="3"),
            "operational": tk.StringVar(value="3"),
            "legal": tk.StringVar(value="3"),
        }

        analyze_btn = ttk.Button(
            frame, text="Executar análise", command=self._analyze, width=40
        )
        analyze_btn.pack(anchor="w", pady=(12, 0))

    def _toggle_advanced(self):
        self.adv_open = not self.adv_open
        if self.adv_open:
            self.adv_btn.config(text="▼ Notas da análise (clique para ocultar)")
            self.adv_hint.pack_forget()
            self._build_advanced_notes()
        else:
            self.adv_btn.config(text="▶ Notas da análise (opcional - ver/ajustar)")
            self.adv_hint.pack(anchor="w", pady=(2, 0))
            for child in self.adv_frame.winfo_children():
                child.destroy()
            self.adv_frame.pack_forget()

    def _toggle_auto_scores(self):
        """Habilita/desabilita o cálculo automático das notas."""
        enabled = self.auto_scores_enabled.get()
        # Recalcula as notas a partir do PDF ao reabilitar
        if enabled and self.pdf_data is not None:
            self._apply_auto_scores()
            self._refresh_notes_reasons()
        self._update_auto_status()

    def _refresh_notes_reasons(self):
        """Recria a área de notas para atualizar as justificativas."""
        if self.adv_open:
            for child in self.adv_frame.winfo_children():
                child.destroy()
            self._build_advanced_notes()

    def _apply_auto_scores(self):
        """Preenche as 4 notas com os valores calculados automaticamente."""
        if self.pdf_data is None:
            return
        from auto_scores import calculate_auto_scores

        requested_limit = self.limit_entry.get_value() or 0
        auto = calculate_auto_scores(self.pdf_data, requested_limit)
        mapping = {
            "financial": auto["financial"][0],
            "payment": auto["payment_history"][0],
            "operational": auto["operational"][0],
            "legal": auto["legal"][0],
        }
        for key, value in mapping.items():
            self.score_vars[key].set(str(int(value)))

    def _build_advanced_notes(self):
        """Preenche a área das notas 1-5 (gerada sob demanda)."""
        grid = ttk.Frame(self.adv_frame)
        grid.pack(fill="x", pady=(6, 0))
        score_rows = [
            ("Capacidade financeira", "financial"),
            ("Histórico de pagamento", "payment"),
            ("Perfil operacional", "operational"),
            ("Risco jurídico", "legal"),
        ]

        # Cabeçalho de status
        status_label = ttk.Label(
            grid,
            text="",
            foreground="green",
            wraplength=680,
            justify="left",
        )
        status_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.auto_status_label = status_label

        reasons = self._get_auto_reasons()

        for i, (label, key) in enumerate(score_rows, start=1):
            ttk.Label(grid, text=f"{label} (1-5):").grid(
                row=i, column=0, sticky="w", padx=(0, 8), pady=3
            )
            ttk.Entry(grid, textvariable=self.score_vars[key], width=24).grid(
                row=i, column=1, sticky="w", pady=3
            )
            self.score_vars[key].trace_add(
                "write", lambda *a, k=key: self._on_score_change(k)
            )
            if reasons and key in reasons:
                ttk.Label(
                    grid,
                    text=f"({reasons[key]})",
                    foreground="gray",
                    wraplength=420,
                    justify="left",
                ).grid(row=i, column=2, sticky="w", padx=(6, 0), pady=3)

        self._update_auto_status()
        self.adv_frame.pack(fill="x", padx=(4, 0))

    def _get_auto_reasons(self):
        """Calcula as justificativas das notas automáticas (retorna dict key->reason)."""
        if self.pdf_data is None or not self.auto_scores_enabled.get():
            return {}
        from auto_scores import calculate_auto_scores

        requested_limit = self.limit_entry.get_value() or 0
        auto = calculate_auto_scores(self.pdf_data, requested_limit)
        return {
            "financial": auto["financial"][1],
            "payment": auto["payment_history"][1],
            "operational": auto["operational"][1],
            "legal": auto["legal"][1],
        }

    def _update_auto_status(self):
        """Atualiza o status de auto/manual na área de notas."""
        if hasattr(self, "auto_status_label"):
            if self.auto_scores_enabled.get():
                self.auto_status_label.config(
                    text="✓ Notas calculadas automaticamente a partir do PDF. "
                    "Desmarque a opção acima para editar manualmente.",
                    foreground="green",
                )
            else:
                self.auto_status_label.config(
                    text="✗ Edição manual habilitada. As notas serão usadas como estão.",
                    foreground="orange",
                )

    def _on_score_change(self, key):
        """Reage à edição manual de uma nota (desativa o auto para essa nota)."""
        pass

    def _build_result_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Resultado", padding=12)
        frame.pack(fill="both", expand=True, padx=16, pady=8)

        self.result_var = tk.StringVar(
            value="Execute a análise para ver a recomendação aqui."
        )
        ttk.Label(
            frame,
            textvariable=self.result_var,
            wraplength=700,
            justify="left",
            font=("Segoe UI", 11),
        ).pack(fill="x")

        self.recommendation_var = tk.StringVar()
        ttk.Label(
            frame,
            textvariable=self.recommendation_var,
            font=("Segoe UI", 14, "bold"),
            foreground="#1a73e8",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        self.file_var = tk.StringVar()
        ttk.Label(
            frame,
            textvariable=self.file_var,
            foreground="gray",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _build_footer(self, parent):
        footer = ttk.Frame(parent, padding=(16, 10))
        footer.pack(fill="x")
        ttk.Button(footer, text="Abrir pasta de saída", command=self._open_output).pack(
            side="right"
        )
        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 12))

    # ================= AÇÕES: NOVA ANÁLISE =================
    def _browse_pdf(self):
        path = filedialog.askopenfilename(
            title="Selecione o PDF do Serasa",
            initialdir=os.path.dirname(self.last_pdf_path)
            if self.last_pdf_path
            else "",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.pdf_path = path
            self.pdf_var.set(path)
            save_config(last_pdf_path=path, last_analyst=self.analyst_var.get())
            self._extract()

    def _extract(self):
        if not self.pdf_path:
            messagebox.showwarning("Nenhum PDF", "Selecione um arquivo PDF primeiro.")
            return
        if not os.path.exists(self.pdf_path):
            messagebox.showerror(
                "Erro", f"Arquivo PDF não encontrado:\n{self.pdf_path}"
            )
            return
        try:
            self.pdf_data = extract_pdf_data(self.pdf_path)
        except Exception as e:
            logger.error(f"Falha ao extrair dados do PDF: {e}", exc_info=True)
            messagebox.showerror(
                "Erro de extração", f"Não foi possível ler o PDF:\n{e}"
            )
            return
        self._show_extracted(self.pdf_data)
        # Preenche as notas automáticas se a opção estiver habilitada
        if self.auto_scores_enabled.get():
            self._apply_auto_scores()
        self.pdf_status.config(
            text="Dados extraídos. Confira os valores e preencha os dados manuais.",
            foreground="green",
        )
        # Se faltarem dados essenciais, abre modal para preenchimento manual
        if self._get_missing_essential_fields():
            self.root.after(200, self._open_missing_data_modal)

    def _show_extracted(self, data):
        self._set_extracted("cnpj", data.get("cnpj", "-"))
        self._set_extracted("legal_name", data.get("legal_name", "-"))
        self._set_extracted("serasa_score", str(data.get("serasa_score", "-")))
        capital = data.get("share_capital")
        self._set_extracted(
            "share_capital", f"R$ {capital:,.2f}" if capital is not None else "-"
        )
        revenue = data.get("monthly_revenue")
        self._set_extracted(
            "monthly_revenue", f"R$ {revenue:,.2f}" if revenue is not None else "-"
        )
        self._set_extracted("segment", data.get("segment", "-"))

    def _set_extracted(self, key, value):
        if key in self.extracted:
            self.extracted[key].set(value)

    # Campos essenciais considerados para a análise mínima
    ESSENTIAL_FIELDS = [
        ("cnpj", "CNPJ", "text"),
        ("legal_name", "Razão social", "text"),
        ("serasa_score", "Score Serasa (0-1000)", "int"),
        ("share_capital", "Capital social (R$)", "money"),
        ("monthly_revenue", "Faturamento mensal estimado (R$)", "money"),
    ]

    def _get_missing_essential_fields(self):
        """Retorna a lista de campos essenciais ausentes no pdf_data."""
        if not self.pdf_data:
            return list(self.ESSENTIAL_FIELDS)
        missing = []
        for key, label, ftype in self.ESSENTIAL_FIELDS:
            val = self.pdf_data.get(key)
            if val is None or val == "":
                missing.append((key, label, ftype))
        return missing

    def _open_missing_data_modal(self):
        """Abre um modal para preencher manualmente os campos essenciais ausentes."""
        missing = self._get_missing_essential_fields()
        if not missing:
            return

        modal = tk.Toplevel(self.root)
        modal.title("Informações em falta no PDF")
        modal.geometry("520x420")
        modal.transient(self.root)
        modal.grab_set()

        wrap = ttk.Frame(modal, padding=16)
        wrap.pack(fill="both", expand=True)

        ttk.Label(
            wrap,
            text=(
                "O documento não contém todas as informações essenciais para "
                "a análise.\nPreencha os campos abaixo para continuar:"
            ),
            wraplength=470,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        grid = ttk.Frame(wrap)
        grid.pack(fill="x")

        entries = {}
        for i, (key, label, ftype) in enumerate(missing):
            ttk.Label(grid, text=f"{label}:").grid(
                row=i, column=0, sticky="w", padx=(0, 8), pady=6
            )
            if ftype == "money":
                entry = CurrencyEntry(grid, width=24)
            else:
                entry = ttk.Entry(grid, width=24)
            entry.grid(row=i, column=1, sticky="w", pady=6)
            entries[key] = (entry, ftype)

        def on_ok():
            # Valida e grava os valores no pdf_data
            for key, (entry, ftype) in entries.items():
                raw = entry.get().strip()
                if not raw:
                    messagebox.showwarning(
                        "Campo vazio", "Preencha todos os campos para continuar.",
                        parent=modal,
                    )
                    return
                try:
                    if ftype == "int":
                        value = int(raw)
                    elif ftype == "money":
                        value = self._parse_money_input(raw)
                    else:
                        value = raw
                except ValueError:
                    messagebox.showwarning(
                        "Valor inválido", f"Valor inválido para o campo: {raw}",
                        parent=modal,
                    )
                    return
                self.pdf_data[key] = value
            modal.destroy()
            # Re-exibe os dados e recalcula as notas automáticas
            self._show_extracted(self.pdf_data)
            if self.auto_scores_enabled.get():
                self._apply_auto_scores()

        def on_cancel():
            modal.destroy()

        btns = ttk.Frame(wrap)
        btns.pack(side="bottom", pady=(12, 0))
        ttk.Button(btns, text="Cancelar", command=on_cancel).pack(
            side="right", padx=6
        )
        ttk.Button(btns, text="Salvar", command=on_ok).pack(side="right")

        modal.bind("<Return>", lambda e: on_ok())
        modal.bind("<Escape>", lambda e: on_cancel())

    @staticmethod
    def _parse_money_input(raw):
        """Converte entrada monetária brasileira (ex.: '15000' ou '15.000,50')."""
        text = raw.strip().replace("R$", "").replace(" ", "")
        neg = text.startswith("-")
        if neg:
            text = text[1:]
        text = text.replace(".", "").replace(",", ".")
        try:
            val = float(text)
        except ValueError:
            raise ValueError(raw)
        return -val if neg else val

    def _validate_inputs(self):
        if not self.pdf_path:
            return None, "Selecione um arquivo PDF primeiro."
        if self.pdf_data is None:
            return (
                None,
                "Selecione o PDF do Serasa para extrair os dados antes de analisar.",
            )

        requested_limit = self.limit_entry.get_value()
        if requested_limit is None:
            return None, "Informe o limite solicitado."
        if requested_limit <= 0:
            return None, "O limite solicitado deve ser maior que zero."

        # Recalcula as notas automáticas com o limite já preenchido, para que
        # elas não fiquem com valores residuais calculados na extração do PDF
        # (quando o limite ainda estava vazio).
        if self.auto_scores_enabled.get() and self.pdf_data is not None:
            self._apply_auto_scores()

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

        references = (
            "Sim" if self.ref_var.get().strip().lower().startswith("s") else "Não"
        )

        inputs = {
            "requested_limit": requested_limit,
            "auto_scores": self.auto_scores_enabled.get(),
            "scores": tuple(scores),
            "references": references,
            "analyst": self.analyst_var.get().strip(),
            "notes": self.notes_text.get("1.0", "end").strip(),
        }

        # Se auto_scores estiver habilitado, envia as notas atuais como overrides manuais
        if self.auto_scores_enabled.get():
            inputs["manual_overrides"] = {
                "financial": scores[0],
                "payment_history": scores[1],
                "operational": scores[2],
                "legal": scores[3],
            }
        return inputs, None

    def _analyze(self):
        if self.analysing:
            return
        inputs, error = self._validate_inputs()
        if error:
            messagebox.showwarning("Verifique os dados", error)
            return
        assert inputs is not None

        self.analysing = True
        self.progress.start(12)
        self.result_var.set("Analisando...")
        save_config(last_pdf_path=self.pdf_path or "", last_analyst=inputs["analyst"])

        thread = threading.Thread(
            target=self._run_analysis, args=(inputs,), daemon=True
        )
        thread.start()

    def _run_analysis(self, inputs):
        try:
            result = process_analysis(
                self.pdf_path, inputs, pdf_data=self.pdf_data
            )
            self.root.after(0, self._on_success, result)
        except Exception as e:
            logger.error(f"Falha na análise: {e}", exc_info=True)
            self.root.after(0, self._on_error, str(e))

    @staticmethod
    def _fmt_brl(value):
        if value is None:
            return "-"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _fmt_num(value, decimals=3):
        if value is None:
            return "-"
        return f"{value:.{decimals}f}".replace(".", ",")

    def _on_success(self, result):
        self.progress.stop()
        self.analysing = False
        calcs = result["calcs"]

        lines = [
            f"Score interno:         {calcs['internal_score']}",
            f"Classificação interna: {calcs['internal_class']}",
            f"Classificação Serasa:  {calcs['serasa_class']}",
            f"Classificação final:   {calcs['final_class']}",
            f"Limite sugerido:       {self._fmt_brl(calcs['suggested_limit'])}",
            f"Cobertura:             {calcs['coverage']}",
            f"Índice de exposição:   {self._fmt_num(calcs['exposure_index'])}",
            f"Alerta de capital:     {calcs['capital_alert']}",
        ]
        self.result_var.set("\n".join(lines))
        self.recommendation_var.set(">>> " + calcs["recommendation"])

        self._refresh_history()

    def _on_error(self, error):
        self.progress.stop()
        self.analysing = False
        self.result_var.set("Falha na análise.")
        self.recommendation_var.set("")
        self.file_var.set("")
        messagebox.showerror("Erro na análise", error)

    # ================= AÇÕES: HISTÓRICO =================
    def _refresh_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        records = load_history()
        for rec in reversed(records):
            self.history_tree.insert(
                "",
                "end",
                values=(
                    rec.get("analysis_date", ""),
                    rec.get("legal_name", ""),
                    rec.get("cnpj", ""),
                    rec.get("internal_score", ""),
                    rec.get("final_class", ""),
                    rec.get("recommendation", ""),
                    rec.get("analyst", ""),
                ),
            )

    def _open_selected_report(self):
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo(
                "Seleção",
                "Selecione uma análise na lista.\n\nO relatório PDF será aberto.",
            )
            return
        # Map tree display back to record by using its displayed row index
        records = list(reversed(load_history()))
        index = self.history_tree.index(selection[0])
        if index < len(records):
            report_path = records[index].get("report_path", "")
            if report_path and os.path.exists(report_path):
                self._open_file(report_path)
            else:
                messagebox.showinfo(
                    "Não encontrado", f"O PDF não foi encontrado:\n{report_path}"
                )
        else:
            messagebox.showinfo("Seleção", "Nenhuma análise selecionada.")

    # ================= AÇÕES: CONFIGURAÇÃO =================
    def _save_params(self):
        try:
            new_params = {}
            for key, var in self.params_vars.items():
                raw = var.get().strip().replace(",", ".")
                new_params[key] = float(raw)
            # Validate weights sum ~ 1.0
            weights = sum(
                new_params[k]
                for k in (
                    "weight_financial",
                    "weight_payment_history",
                    "weight_operational",
                    "weight_legal",
                )
            )
            if abs(weights - 1.0) > 0.001:
                messagebox.showwarning(
                    "Pesos inválidos",
                    f"A soma dos pesos deve ser 1.0, mas é {weights:.3f}. Corrija antes de salvar.",
                )
                return
            save_params(new_params)
            self.params_status.config(
                text="Parâmetros salvos com sucesso!", foreground="green"
            )
            self.params_status.after(4000, lambda: self.params_status.config(text=""))
        except ValueError:
            messagebox.showerror(
                "Valor inválido", "Todos os parâmetros devem ser números."
            )
        except Exception as e:
            logger.error(f"Falha ao salvar parâmetros: {e}", exc_info=True)
            messagebox.showerror("Erro", f"Não foi possível salvar os parâmetros:\n{e}")

    def _reset_params(self):
        for key, var in self.params_vars.items():
            var.set(DEFAULT_PARAMS.get(key, ""))
        self.params_status.config(
            text="Valores padrão restaurados. Clique em 'Salvar' para aplicar.",
            foreground="blue",
        )

    # ================= UTILITÁRIOS =================
    def _open_output(self):
        self._open_file(reports_dir())

    def _open_file(self, path):
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


def main():
    try:
        root = tk.Tk()

        icon_path = os.path.join(assets_dir(), "credit-analysis.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)

        CreditAnalysisApp(root)
        root.mainloop()
    except Exception as error:
        logger.error(f"Erro ao executar o aplicativo: {error}", exc_info=True)
        messagebox.showerror(
            "Erro",
            "Ocorreu um erro inesperado. Verifique o arquivo credit-analysis.log para mais detalhes.",
        )


if __name__ == "__main__":
    main()
