#!/usr/bin/env python3
"""
gui.py — Interface gráfica para add_search_links.py
Arraste um ou mais arquivos HTML para a janela e clique "Abrir" no resultado.

Uso:
    python3 gui.py
"""

import threading
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font as tkfont

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from add_search_links import process_html

# ── cores ──────────────────────────────────────────────────────────────────
BG         = "#f5f6f8"
WHITE      = "#ffffff"
BLUE       = "#1a73e8"
GREEN      = "#1e7e34"
YELLOW     = "#f0a500"
GRAY       = "#6c757d"
BORDER     = "#c8cdd5"
TEXT       = "#1a1a2e"
SUBTEXT    = "#555555"


class App(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("News Report — Injetor de Links")
        self.configure(bg=BG)
        self.resizable(False, False)

        # ── fontes ──
        self.f_title  = tkfont.Font(family="SF Pro Display", size=15, weight="bold")
        self.f_sub    = tkfont.Font(family="SF Pro Text",    size=11)
        self.f_small  = tkfont.Font(family="SF Pro Text",    size=10)
        self.f_mono   = tkfont.Font(family="Menlo",          size=10)

        self._build_ui()
        self._center()

    # ── layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = dict(padx=24, pady=0)

        # título
        tk.Label(self, text="News Report — Injetor de Links",
                 font=self.f_title, bg=BG, fg=TEXT).pack(pady=(28, 4))
        tk.Label(self, text="Arraste arquivos HTML aqui para adicionar links diretos às notícias.",
                 font=self.f_sub, bg=BG, fg=SUBTEXT).pack(pady=(0, 20))

        # zona de drop
        self.drop_frame = tk.Frame(self, bg=WHITE, bd=0,
                                   highlightthickness=2, highlightbackground=BORDER,
                                   width=480, height=160)
        self.drop_frame.pack(**pad, pady=(0, 20))
        self.drop_frame.pack_propagate(False)

        self.drop_icon  = tk.Label(self.drop_frame, text="⬆", font=("SF Pro Display", 32),
                                   bg=WHITE, fg=BLUE)
        self.drop_icon.pack(pady=(28, 4))

        self.drop_label = tk.Label(self.drop_frame,
                                   text="Arraste arquivos HTML\nou clique para selecionar",
                                   font=self.f_sub, bg=WHITE, fg=SUBTEXT,
                                   justify="center")
        self.drop_label.pack()

        # habilita drag-and-drop
        if HAS_DND:
            for w in (self.drop_frame, self.drop_icon, self.drop_label):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>",   self._on_drop)
                w.dnd_bind("<<DragEnter>>", lambda e: self._set_hover(True))
                w.dnd_bind("<<DragLeave>>", lambda e: self._set_hover(False))

        # clique para abrir seletor
        for w in (self.drop_frame, self.drop_icon, self.drop_label):
            w.bind("<Button-1>", self._browse)

        # barra de progresso (oculta inicialmente)
        self.progress_var   = tk.DoubleVar()
        self.progress_label = tk.Label(self, text="", font=self.f_small,
                                       bg=BG, fg=SUBTEXT)
        self.progress_label.pack(**pad)

        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var,
                                            maximum=100, length=480, mode="determinate")
        self.progress_bar.pack(**pad, pady=(4, 16))
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()

        # lista de resultados
        self.results_frame = tk.Frame(self, bg=BG)
        self.results_frame.pack(**pad, pady=(0, 24), fill="x")

        self.geometry("528x320")

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    # ── drag-and-drop ──────────────────────────────────────────────────────

    def _set_hover(self, active: bool):
        color = "#e8f0fe" if active else WHITE
        border = BLUE if active else BORDER
        self.drop_frame.configure(bg=color, highlightbackground=border)
        self.drop_icon.configure(bg=color)
        self.drop_label.configure(bg=color)

    def _on_drop(self, event):
        self._set_hover(False)
        paths = self.tk.splitlist(event.data)
        html_files = [Path(p) for p in paths if p.lower().endswith((".html", ".htm"))]
        if html_files:
            self._process_files(html_files)

    def _browse(self, _event=None):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            title="Selecionar relatórios HTML",
            filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")],
        )
        html_files = [Path(p) for p in paths]
        if html_files:
            self._process_files(html_files)

    # ── processamento ──────────────────────────────────────────────────────

    def _process_files(self, files: list[Path]):
        """Processa lista de arquivos em thread separada para não travar a UI."""
        threading.Thread(target=self._worker, args=(files,), daemon=True).start()

    def _worker(self, files: list[Path]):
        total = len(files)
        self.after(0, self._show_progress, 0, f"Processando 0 / {total}…")

        for i, path in enumerate(files):
            self.after(0, self._show_progress,
                       int(i / total * 100),
                       f"Processando {i+1} / {total} — {path.name}")
            try:
                html     = path.read_text(encoding="utf-8")
                modified, direct, fallback = process_html(html)
                out_path = path.with_stem(path.stem + "-links")
                out_path.write_text(modified, encoding="utf-8")
                self.after(0, self._add_result, path.name, out_path, direct, fallback)
            except Exception as exc:
                self.after(0, self._add_error, path.name, str(exc))

        self.after(0, self._hide_progress)

    # ── UI helpers ─────────────────────────────────────────────────────────

    def _show_progress(self, pct: float, label: str):
        self.progress_label.configure(text=label)
        self.progress_var.set(pct)
        self.progress_label.pack(padx=24, pady=(8, 2))
        self.progress_bar.pack(padx=24, pady=(0, 8))
        self._grow()

    def _hide_progress(self):
        self.progress_label.pack_forget()
        self.progress_bar.pack_forget()

    def _add_result(self, name: str, out_path: Path, direct: int, fallback: int):
        card = tk.Frame(self.results_frame, bg=WHITE,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(0, 8))

        inner = tk.Frame(card, bg=WHITE)
        inner.pack(fill="x", padx=14, pady=10)

        # nome do arquivo
        tk.Label(inner, text=name, font=self.f_small, bg=WHITE,
                 fg=TEXT, anchor="w").pack(side="left")

        # botão abrir
        btn = tk.Button(inner, text="Abrir",
                        font=self.f_small, bg=BLUE, fg=WHITE,
                        activebackground="#1558b0", activeforeground=WHITE,
                        relief="flat", padx=12, pady=3, cursor="hand2",
                        command=lambda p=out_path: subprocess.run(["open", str(p)]))
        btn.pack(side="right", padx=(8, 0))

        # estatísticas
        stats = f"🔗 {direct} diretos"
        if fallback:
            stats += f"  🔍 {fallback} buscas"
        tk.Label(inner, text=stats, font=self.f_small, bg=WHITE,
                 fg=SUBTEXT).pack(side="right")

        self._grow()

    def _add_error(self, name: str, msg: str):
        card = tk.Frame(self.results_frame, bg="#fff3f3",
                        highlightthickness=1, highlightbackground="#f5c6cb")
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text=f"✗  {name}: {msg}", font=self.f_small,
                 bg="#fff3f3", fg="#d93025", anchor="w").pack(padx=14, pady=8)
        self._grow()

    def _grow(self):
        """Expande a janela verticalmente conforme resultados são adicionados."""
        self.update_idletasks()
        h = self.winfo_reqheight()
        self.geometry(f"528x{max(320, h)}")


if __name__ == "__main__":
    if not HAS_DND:
        print("Instale tkinterdnd2 para arrastar arquivos:  pip install tkinterdnd2")
    app = App()
    app.mainloop()
