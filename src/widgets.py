"""
Reusable tkinter widgets for the credit analysis GUI.
"""

import tkinter as tk
from tkinter import ttk


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
