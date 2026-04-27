#!/usr/bin/env python3
"""
Folder Diff — macOS Desktop App
Compare two folders and copy files between them.
Run with: python3 folder_diff.py
Requires: pip3 install reportlab
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import hashlib
import threading
import shutil
from pathlib import Path
import subprocess
import datetime

# ── Colour palette — Black / Yellow / Blue ───────────────────────────────────
BG        = "#0a0a0a"   # near-black background
SURFACE   = "#141414"   # dark surface
CARD      = "#1e1e1e"   # slightly lighter card
ACCENT    = "#ff6d00"   # vivid orange — neutral UI accent (not folder 1 or 2)
ACCENT2   = "#ffab40"   # lighter orange for hover/highlights
DANGER    = "#ff1744"   # bright red — good on dark
SUCCESS   = "#00e676"   # neon green — readable on dark
MUTED     = "#757575"   # mid grey
FG        = "#f5f5f5"   # near-white — max contrast
FG_DIM    = "#9e9e9e"   # grey — secondary text
BORDER    = "#2c2c2c"   # subtle dark border

# Per-folder colours
ONLY_A    = "#2979ff"   # electric blue — folder 1
ONLY_B    = "#ffd600"   # yellow        — folder 2
DIFF      = "#ff6d00"   # vivid orange  — differences / other

FONT_TITLE = ("Verdana", 22, "bold")
FONT_LABEL = ("Verdana", 13)
FONT_SMALL = ("Verdana", 11)
FONT_MONO  = ("Verdana", 10)
FONT_BTN   = ("Verdana", 13, "bold")


# ── PDF Report ────────────────────────────────────────────────────────────────

def generate_pdf_report(copied_files, folder_a, folder_b, output_path):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import reportlab as _rl, os as _os
        _fonts = _os.path.join(_os.path.dirname(_rl.__file__), "fonts")
        pdfmetrics.registerFont(TTFont("Vera",   _os.path.join(_fonts, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("VeraBd", _os.path.join(_fonts, "VeraBd.ttf")))
        pdfmetrics.registerFont(TTFont("VeraIt", _os.path.join(_fonts, "VeraIt.ttf")))
        FNORM = "Vera"
        FBOLD = "VeraBd"
        FMONO = "Vera"
    except ImportError:
        return False, "reportlab not installed.\nRun: pip3 install reportlab"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    C_HDR    = colors.HexColor("#1c1c1c")   # dark header
    C_TITLE  = colors.HexColor("#0a0a0a")
    C_ONLY_A = colors.HexColor("#2979ff")   # electric blue
    C_ONLY_B = colors.HexColor("#ffd600")   # yellow
    C_DIFF   = colors.HexColor("#ff6d00")   # orange
    C_BODY   = colors.HexColor("#1c1b1f")
    C_MUTED  = colors.HexColor("#757575")
    C_PATH   = colors.HexColor("#444746")
    C_ACCENT = colors.HexColor("#ffd600")   # yellow accent

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Folder Differences — Copy Report"
    )

    title_s = ParagraphStyle("T", fontName=FBOLD, fontSize=22,
                              textColor=C_TITLE, spaceAfter=3, alignment=TA_LEFT)
    sub_s   = ParagraphStyle("S", fontName=FNORM, fontSize=10,
                              textColor=C_HDR, spaceAfter=2, alignment=TA_LEFT)
    sec_s   = ParagraphStyle("Sec", fontName=FBOLD, fontSize=12,
                              textColor=C_HDR, spaceBefore=12, spaceAfter=5)
    note_s  = ParagraphStyle("N", fontName=FNORM, fontSize=8,
                              textColor=C_MUTED, spaceAfter=2)
    fname_s = ParagraphStyle("FN", fontName=FBOLD, fontSize=11,
                              textColor=C_BODY, leading=14)
    path_s  = ParagraphStyle("P", fontName=FMONO, fontSize=8,
                              textColor=C_PATH, leading=10)

    story = []

    story.append(Paragraph("Folder Differences", title_s))
    story.append(Paragraph("File Copy Report", sub_s))
    story.append(HRFlowable(width="100%", thickness=2, color=C_HDR, spaceAfter=8))

    summary_data = [
        ["Date",      now],
        ["Folder 1",  folder_a],
        ["Folder 2",  folder_b],
        ["Files copied", str(len(copied_files))],
    ]
    sum_tbl = Table(summary_data, colWidths=[3.5*cm, 23*cm])
    sum_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,-1), colors.HexColor("#1a1a00")),
        ("BACKGROUND",    (1,0),(1,-1), colors.HexColor("#1e1e1e")),
        ("TEXTCOLOR",     (0,0),(0,-1), C_ACCENT),
        ("TEXTCOLOR",     (1,0),(1,-1), C_BODY),
        ("FONTNAME",      (0,0),(0,-1), FBOLD),
        ("FONTNAME",      (1,0),(1,-1), FNORM),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.HexColor("#333300")),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Copied Files", sec_s))
    story.append(Paragraph("Direction: → copied to Folder 1,  ← copied to Folder 2", note_s))
    story.append(Spacer(1, 5))

    def hdr(t):
        return Paragraph(f"<b>{t}</b>",
                         ParagraphStyle("h", fontName=FBOLD, fontSize=9,
                                        textColor=colors.white))

    table_data = [[ hdr("#"), hdr("Direction"), hdr("File Name  /  Path"), hdr("Destination") ]]
    COL_W = [1*cm, 2.5*cm, 14*cm, 10*cm]

    for i, f in enumerate(copied_files, 1):
        direction = "→ to Folder 1" if f["direction"] == "to_a" else "← to Folder 2"
        dir_color = C_ONLY_B if f["direction"] == "to_a" else C_ONLY_A
        fname = Path(f["src"]).name
        cell = Paragraph(
            f'{fname}<br/><font name="{FMONO}" size="8" color="#444746">{f["src"]}</font>',
            fname_s
        )
        dest_cell = Paragraph(f["dst"], path_s)
        dir_cell  = Paragraph(direction,
                               ParagraphStyle("d", fontName=FBOLD, fontSize=9,
                                              textColor=dir_color))
        table_data.append([str(i), dir_cell, cell, dest_cell])

    bg_a = colors.HexColor("#1a1a1a")
    bg_b = colors.white
    file_tbl = Table(table_data, colWidths=COL_W, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (0,0),(-1,0),  C_HDR),
        ("GRID",          (0,0),(-1,-1), 0.3, colors.HexColor("#2c2c2c")),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
    ]
    for i in range(1, len(table_data)):
        style_cmds.append(("BACKGROUND", (0,i),(-1,i), bg_a if i%2==0 else bg_b))
    file_tbl.setStyle(TableStyle(style_cmds))
    story.append(file_tbl)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=C_ACCENT, spaceAfter=6))
    story.append(Paragraph("Generated by Folder Differences  •  A comparison and sync tool.", note_s))

    doc.build(story)
    return True, output_path


# ── Diff engine ───────────────────────────────────────────────────────────────

import re as _re

_TEMP_PATTERNS = _re.compile(
    r"(\.(tmp|temp|bak|cache|lock)$"
    r"|~\$"
    r"|\.[a-zA-Z]{2,4}[A-F0-9]{2,4}$"
    r"|\.part$"
    r")", _re.IGNORECASE
)

def _is_temp_file(name):
    if name.startswith("~$") or name.startswith("."):
        return True
    if _TEMP_PATTERNS.search(name):
        return True
    return False

def file_hash(path, buf=1024 * 1024):
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            while chunk := f.read(buf):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def file_quick_hash(path, sample=65536):
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            h.update(f.read(sample))
        return h.hexdigest()
    except (OSError, PermissionError):
        return None

def compare_folders(folder_a, folder_b, progress_cb, done_cb):
    """
    Walk both folders and return:
      only_a  : files only in A  (rel_path → abs_path_a)
      only_b  : files only in B  (rel_path → abs_path_b)
      different: files in both but with different content
                (rel_path → (abs_a, abs_b))
    """
    def collect(folder):
        result = {}
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
            for name in files:
                if _is_temp_file(name):
                    continue
                abs_p = os.path.join(root, name)
                rel   = os.path.relpath(abs_p, folder)
                result[rel] = abs_p
        return result

    files_a = collect(folder_a)
    files_b = collect(folder_b)

    keys_a = set(files_a)
    keys_b = set(files_b)

    only_a   = {k: files_a[k] for k in keys_a - keys_b}
    only_b   = {k: files_b[k] for k in keys_b - keys_a}
    common   = sorted(keys_a & keys_b)

    different = {}
    total = len(common)
    if total == 0:
        done_cb(only_a, only_b, different)
        return

    # Stage 0: skip files whose sizes differ (cheap, no read)
    size_match = []
    for rel in common:
        try:
            if os.path.getsize(files_a[rel]) != os.path.getsize(files_b[rel]):
                different[rel] = (files_a[rel], files_b[rel])
            else:
                size_match.append(rel)
        except OSError:
            pass

    # Stage 1: quick hash on first 64KB
    quick_match = []
    done = 0
    last = 0
    n_quick = len(size_match)
    overall_total = n_quick * 2 or 1
    for rel in size_match:
        qa = file_quick_hash(files_a[rel])
        qb = file_quick_hash(files_b[rel])
        if qa and qb:
            if qa != qb:
                different[rel] = (files_a[rel], files_b[rel])
            else:
                quick_match.append(rel)
        done += 1
        if done - last >= 25 or done == n_quick:
            progress_cb(done, overall_total, rel)
            last = done

    # Stage 2: full hash only on quick-hash matches
    n_full = len(quick_match)
    overall_total = n_quick + n_full or 1
    last = 0
    full_done = 0
    for rel in quick_match:
        ha = file_hash(files_a[rel])
        hb = file_hash(files_b[rel])
        if ha and hb and ha != hb:
            different[rel] = (files_a[rel], files_b[rel])
        full_done += 1
        if full_done - last >= 25 or full_done == n_full:
            progress_cb(n_quick + full_done, overall_total, rel)
            last = full_done

    done_cb(only_a, only_b, different)


# ── App ───────────────────────────────────────────────────────────────────────

class FolderDiffApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Folder Differences v2")
        self.geometry("1300x800")
        self.minsize(1000, 600)
        self.configure(bg=BG)

        try:
            self.tk.call("::tk::unsupported::MacWindowStyle",
                         "style", self._w, "document", "")
        except Exception:
            pass

        self._folder_a   = tk.StringVar(value="")
        self._folder_b   = tk.StringVar(value="")
        self._real_a     = ""
        self._real_b     = ""
        self._only_a     = {}
        self._only_b     = {}
        self._different  = {}
        self._copied     = []   # log for PDF
        self._pdf_var    = tk.BooleanVar(value=True)
        self._size_a     = tk.StringVar(value="")
        self._size_b     = tk.StringVar(value="")
        self._iid_data   = {}   # iid -> dict (status, name, rel, data, tags)
        self._selectable_iids = []

        self._build_ui()

        try:
            menubar  = tk.Menu(self)
            app_menu = tk.Menu(menubar, name="apple")
            menubar.add_cascade(menu=app_menu)
            app_menu.add_command(label="About Folder Differences")
            app_menu.add_separator()
            app_menu.add_command(label="Quit Folder Differences",
                                  command=self.destroy, accelerator="Cmd+Q")
            self.config(menu=menubar)
            self.bind_all("<Command-q>", lambda e: self.destroy())
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(24, 0))
        tk.Label(hdr, text="⇄  Folder Differences",
                 font=FONT_TITLE, bg=BG, fg=FG).pack(side="left")

        # ── Folder pickers ──
        pickers = tk.Frame(self, bg=BG)
        pickers.pack(fill="x", padx=28, pady=(16, 0))

        self._build_folder_row(pickers, "Folder 1", self._folder_a, self._browse_a, ONLY_A, self._size_a)
        self._build_folder_row(pickers, "Folder 2", self._folder_b, self._browse_b, ONLY_B, self._size_b)

        # ── Compare button ──
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=28, pady=(12, 0))
        self._compare_btn = self._make_btn(btn_row, "  Compare Folders  ",
                                            self._start_compare,
                                            bg=ACCENT, fg="#ffffff", pad=(20, 0))
        self._compare_btn.pack(side="left")

        # ── Progress ──
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=28, pady=(10, 0))
        self._progress_label = tk.Label(prog_frame, text="",
                                        font=FONT_SMALL, bg=BG, fg=FG_DIM)
        self._progress_label.pack(anchor="w")
        self._progress = ttk.Progressbar(prog_frame, mode="determinate")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TProgressbar", troughcolor=CARD, background=ACCENT,
                         thickness=4, borderwidth=0)
        self._progress.pack(fill="x", pady=(4, 0))

        # ── Stats ──
        self._stats_frame = tk.Frame(self, bg=BG)
        self._stats_frame.pack(fill="x", padx=28, pady=(10, 0))

        # ── Legend ──
        leg = tk.Frame(self, bg=BG)
        leg.pack(fill="x", padx=28, pady=(6, 0))
        for color, label in [(ONLY_A, "Only in Folder 1"),
                              (ONLY_B, "Only in Folder 2"),
                              (DIFF,   "Differences")]:
            f = tk.Frame(leg, bg=BG)
            f.pack(side="left", padx=(0, 18))
            dot = tk.Frame(f, bg=color, width=12, height=12)
            dot.pack(side="left", padx=(0, 5))
            dot.pack_propagate(False)
            tk.Label(f, text=label, font=FONT_SMALL, bg=BG, fg=FG_DIM).pack(side="left")

        # ── Results tree ──
        results_frame = tk.Frame(self, bg=SURFACE,
                                  highlightthickness=1, highlightbackground=BORDER)
        results_frame.pack(fill="both", expand=True, padx=28, pady=(8, 0))

        cols = ("status", "file", "rel_path", "action")
        self._tree = ttk.Treeview(results_frame, columns=cols,
                                   show="headings", selectmode="extended")
        style.configure("Treeview",
                         background=SURFACE, foreground=FG,
                         fieldbackground=SURFACE, rowheight=30,
                         borderwidth=0, font=FONT_SMALL)
        style.configure("Treeview.Heading",
                         background=CARD, foreground=FG_DIM,
                         relief="flat", font=FONT_SMALL)
        style.map("Treeview", background=[("selected", ACCENT)])

        self._tree.heading("status",   text="Status")
        self._tree.heading("file",     text="File Name")
        self._tree.heading("rel_path", text="Relative Path")
        self._tree.heading("action",   text="")

        self._tree.column("status",   width=150,  minwidth=150,  stretch=False)
        self._tree.column("file",     width=280,  minwidth=280,  stretch=False)
        self._tree.column("rel_path", width=800,  minwidth=800,  stretch=False)
        self._tree.column("action",   width=0,    stretch=False)  # hidden data col

        self._tree.tag_configure("only_a",  foreground=ONLY_A)
        self._tree.tag_configure("only_b",  foreground=ONLY_B)
        self._tree.tag_configure("diff",    foreground=DIFF)
        self._tree.tag_configure("section_a",
                                  background="#0a1530",
                                  foreground=ONLY_A,
                                  font=(*FONT_SMALL[:2], "bold"))
        self._tree.tag_configure("section_b",
                                  background="#1a1a00",
                                  foreground=ONLY_B,
                                  font=(*FONT_SMALL[:2], "bold"))
        self._tree.tag_configure("section_diff",
                                  background="#2a1500",
                                  foreground=DIFF,
                                  font=(*FONT_SMALL[:2], "bold"))
        self._tree.tag_configure("section",
                                  background="#1a1a1a",
                                  foreground=ACCENT,
                                  font=(*FONT_SMALL[:2], "bold"))

        vsb = ttk.Scrollbar(results_frame, orient="vertical",
                             command=self._tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal",
                             command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(side="left", fill="both", expand=True)

        self._tree.bind("<Double-1>", self._on_double_click)

        # ── Copy buttons ──
        copy_bar = tk.Frame(self, bg=BG)
        copy_bar.pack(fill="x", padx=28, pady=(10, 0))

        self._make_btn(copy_bar, "→  Copy selected to Folder 1",
                       lambda: self._copy_selected("to_a"),
                       bg=ONLY_A, fg="#ffffff", pad=(16, 0)).pack(side="left", padx=(0, 8))

        self._make_btn(copy_bar, "←  Copy selected to Folder 2",
                       lambda: self._copy_selected("to_b"),
                       bg=ONLY_B, fg="#ffffff", pad=(16, 0)).pack(side="left", padx=(0, 8))

        tk.Frame(copy_bar, bg=BG).pack(side="left", expand=True)

        self._make_btn(copy_bar, "Reveal in Finder",
                       self._reveal_selected,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left", padx=(0, 8))

        self._make_btn(copy_bar, "Select All",
                       self._select_all,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left", padx=(0, 8))

        # ── PDF + Quit row ──
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=28, pady=(6, 16))

        tk.Checkbutton(
            bottom,
            text="  Generate PDF report when copying files",
            variable=self._pdf_var,
            font=FONT_SMALL, bg=BG, fg=FG_DIM,
            selectcolor=CARD, activebackground=BG, activeforeground=FG,
            relief="flat", bd=0, cursor="hand2"
        ).pack(side="left")
        tk.Label(bottom, text="(saved to Desktop)",
                 font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="left", padx=(6, 0))

        tk.Frame(bottom, bg=BG).pack(side="left", expand=True)
        self._make_btn(bottom, "✕  Quit", self.destroy,
                       bg=CARD, fg=FG_DIM, pad=(14, 0)).pack(side="right")

    def _build_folder_row(self, parent, label, var, browse_cmd, color, size_var):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 8))

        indicator = tk.Frame(row, bg=color, width=4, height=32)
        indicator.pack(side="left", padx=(0, 8))
        indicator.pack_propagate(False)

        tk.Label(row, text=label, font=FONT_LABEL,
                 bg=BG, fg=color, width=8, anchor="w").pack(side="left")

        entry = tk.Entry(row, textvariable=var,
                         font=FONT_MONO, bg=CARD, fg=FG, relief="flat",
                         insertbackground=color, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=color)
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 10))

        tk.Label(row, textvariable=size_var, font=FONT_SMALL,
                 bg=BG, fg=color, width=10, anchor="e").pack(side="left", padx=(0, 8))

        self._make_btn(row, "Browse…", browse_cmd,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_btn(self, parent, text, cmd, bg=CARD, fg=FG, pad=(14, 0)):
        btn = tk.Label(parent, text=text, font=FONT_BTN,
                       bg=bg, fg=fg, cursor="hand2", padx=pad[0], pady=7)
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>",    lambda e: btn.config(bg=self._lighten(bg)))
        btn.bind("<Leave>",    lambda e: btn.config(bg=bg))
        return btn

    @staticmethod
    def _lighten(hex_color):
        try:
            r, g, b = (int(hex_color[i:i+2], 16) for i in (1, 3, 5))
            return f"#{min(255,r+25):02x}{min(255,g+25):02x}{min(255,b+25):02x}"
        except Exception:
            return hex_color

    def _clear_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()

    def _add_stat(self, label, value, color=FG):
        f = tk.Frame(self._stats_frame, bg=BG)
        f.pack(side="left", padx=(0, 24))
        tk.Label(f, text=label, font=FONT_SMALL, bg=BG, fg=FG_DIM).pack(anchor="w")
        tk.Label(f, text=value, font=(*FONT_LABEL[:2], "bold"),
                 bg=BG, fg=color).pack(anchor="w")

    # ── Browse ────────────────────────────────────────────────────────────────

    @staticmethod
    def _folder_size(folder):
        """Return human-readable total size of a folder."""
        total = 0
        try:
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        except OSError:
            pass
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if total < 1024:
                return f"{total:.1f} {unit}"
            total /= 1024
        return f"{total:.1f} TB"

    def _browse_a(self):
        folder = filedialog.askdirectory(title="Choose Folder 1")
        if folder:
            self._real_a = folder
            self._folder_a.set(folder)
            self._size_a.set("calculating…")
            threading.Thread(
                target=lambda: self.after(0, lambda:
                    self._size_a.set(self._folder_size(folder))),
                daemon=True
            ).start()

    def _browse_b(self):
        folder = filedialog.askdirectory(title="Choose Folder 2")
        if folder:
            self._real_b = folder
            self._folder_b.set(folder)
            self._size_b.set("calculating…")
            threading.Thread(
                target=lambda: self.after(0, lambda:
                    self._size_b.set(self._folder_size(folder))),
                daemon=True
            ).start()

    # ── Compare ───────────────────────────────────────────────────────────────

    def _start_compare(self):
        a = self._real_a or self._folder_a.get().strip()
        b = self._real_b or self._folder_b.get().strip()

        if not a or not os.path.isdir(a):
            messagebox.showwarning("Missing folder", "Please choose Folder 1 first.")
            return
        if not b or not os.path.isdir(b):
            messagebox.showwarning("Missing folder", "Please choose Folder 2 first.")
            return

        self._tree.delete(*self._tree.get_children())
        self._clear_stats()
        self._progress["value"] = 0
        self._progress_label.config(text="Comparing…")
        self._compare_btn.config(text="Comparing…")

        def on_progress(done, total, name):
            if total:
                self.after(0, lambda:
                    self._progress.configure(value=(done/total)*100))
            self.after(0, lambda n=Path(name).name:
                self._progress_label.config(text=f"Checking: {n}"))

        def on_done(only_a, only_b, different):
            self.after(0, lambda: self._render(only_a, only_b, different))

        threading.Thread(target=compare_folders,
                         args=(a, b, on_progress, on_done),
                         daemon=True).start()

    def _render(self, only_a, only_b, different):
        self._only_a    = only_a
        self._only_b    = only_b
        self._different = different

        self._tree.delete(*self._tree.get_children())
        self._iid_data = {}
        self._selectable_iids = []
        self._progress["value"] = 100
        self._progress_label.config(text="")
        self._compare_btn.config(text="  Compare Folders  ")

        self._clear_stats()
        total = len(only_a) + len(only_b) + len(different)
        self._add_stat("Only in Folder 1", str(len(only_a)),    ONLY_A)
        self._add_stat("Only in Folder 2", str(len(only_b)),    ONLY_B)
        self._add_stat("Differences", str(len(different)), DIFF)
        self._add_stat("Total differences", str(total),          ACCENT)

        if total == 0:
            self._tree.insert("", "end",
                               values=("✅  Folders are identical", "", "", ""),
                               tags=("section",))
            return

        # Build all rows up front, insert in batches
        rows = []
        if only_a:
            rows.append(("section_a",
                         (f"── Only in Folder 1  ({len(only_a)} files)", "", "", "")))
            for rel, abs_p in sorted(only_a.items()):
                rows.append(("only_a",
                             ("Only in Folder 1", Path(rel).name, rel, abs_p)))
        if only_b:
            rows.append(("section_b",
                         (f"── Only in Folder 2  ({len(only_b)} files)", "", "", "")))
            for rel, abs_p in sorted(only_b.items()):
                rows.append(("only_b",
                             ("Only in Folder 2", Path(rel).name, rel, abs_p)))
        if different:
            rows.append(("section_diff",
                         (f"── Differences  ({len(different)} files)", "", "", "")))
            for rel, (abs_a, abs_b) in sorted(different.items()):
                rows.append(("diff",
                             ("Differences", Path(rel).name, rel, f"{abs_a}||{abs_b}")))

        self._progress_label.config(text=f"Loading… 0 / {len(rows)}")
        self.update_idletasks()
        self.after(1, lambda: self._insert_rows_batch(rows, 0))

    def _insert_rows_batch(self, rows, start, chunk=100):
        end = min(start + chunk, len(rows))
        for tag, values in rows[start:end]:
            iid = self._tree.insert("", "end", values=values, tags=(tag,))
            if not tag.startswith("section"):
                self._iid_data[iid] = {
                    "status": values[0], "name": values[1],
                    "rel": values[2], "data": values[3], "tag": tag,
                }
                self._selectable_iids.append(iid)
        if end < len(rows):
            self._progress_label.config(text=f"Loading… {end} / {len(rows)}")
            self.update_idletasks()
            self.after(1, lambda: self._insert_rows_batch(rows, end, chunk))
        else:
            self._progress_label.config(text="")

    # ── Selection ─────────────────────────────────────────────────────────────

    def _select_all(self):
        self._tree.selection_set([])
        targets = list(self._selectable_iids)
        if not targets:
            return
        self._progress_label.config(text=f"Selecting… 0 / {len(targets)}")
        self.update_idletasks()
        self.after(1, lambda: self._batch_select(targets, 0))

    def _batch_select(self, iids, start, chunk=100):
        end = min(start + chunk, len(iids))
        self._tree.selection_add(*iids[start:end])
        if end < len(iids):
            self._progress_label.config(text=f"Selecting… {end} / {len(iids)}")
            self.update_idletasks()
            self.after(1, lambda: self._batch_select(iids, end, chunk))
        else:
            self._progress_label.config(text=f"Selected {len(iids)} files.")

    def _get_selected_items(self):
        result = []
        for iid in self._tree.selection():
            d = self._iid_data.get(iid)
            if not d:
                continue
            result.append({
                "iid":    iid,
                "status": d["status"],
                "name":   d["name"],
                "rel":    d["rel"],
                "data":   d["data"],
                "tags":   (d["tag"],),
            })
        return result

    # ── Reveal ────────────────────────────────────────────────────────────────

    def _reveal_selected(self):
        items = self._get_selected_items()
        if not items:
            messagebox.showinfo("Nothing selected", "Select a file first.")
            return
        for item in items[:5]:
            data = item["data"]
            path = data.split("||")[0] if "||" in data else data
            if os.path.exists(path):
                subprocess.run(["open", "-R", path])

    # ── Double-click ──────────────────────────────────────────────────────────

    def _on_double_click(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        vals = self._tree.item(iid, "values")
        tags = self._tree.item(iid, "tags")
        if not vals or "section" in tags:
            return
        data = vals[3]
        path = data.split("||")[0] if "||" in data else data
        if os.path.exists(path):
            subprocess.run(["open", "-R", path])

    # ── Copy ──────────────────────────────────────────────────────────────────

    def _copy_selected(self, direction):
        """direction: 'to_a' (copy to folder 1) or 'to_b' (copy to folder 2)"""
        items = self._get_selected_items()
        if not items:
            messagebox.showinfo("Nothing selected", "Select one or more files first.")
            return

        dest_folder = self._real_a if direction == "to_a" else self._real_b
        dest_label  = "Folder 1" if direction == "to_a" else "Folder 2"

        # Validate copyable items
        copyable = []
        for item in items:
            data = item["data"]
            if "only_a" in item["tags"] and direction == "to_b":
                copyable.append((item["rel"], data, None))
            elif "only_b" in item["tags"] and direction == "to_a":
                copyable.append((item["rel"], data, None))
            elif "diff" in item["tags"]:
                parts = data.split("||")
                src = parts[0] if direction == "to_b" else parts[1]
                copyable.append((item["rel"], src, None))

        if not copyable:
            messagebox.showinfo(
                "Nothing to copy",
                f"Selected files already exist in {dest_label} with identical content."
            )
            return

        if not messagebox.askyesno(
            "Copy files",
            f"Copy {len(copyable)} file(s) to {dest_label}?\n\n"
            f"Existing files will be overwritten.",
            icon="question"
        ):
            return

        self._progress["value"] = 0
        self._progress_label.config(text=f"Copying… 0 / {len(copyable)}")
        self.update_idletasks()

        def worker():
            errors = []
            copied = []
            total = len(copyable)
            for i, (rel, src, _) in enumerate(copyable, 1):
                dst = os.path.join(dest_folder, rel)
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    copied.append({"src": src, "dst": dst, "direction": direction})
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")
                if i % 5 == 0 or i == total:
                    self.after(0, lambda done=i, t=total:
                        (self._progress.configure(value=(done/t)*100),
                         self._progress_label.config(text=f"Copying… {done} / {t}")))

            self.after(0, lambda: self._after_copy(copied, errors, dest_label))

        threading.Thread(target=worker, daemon=True).start()

    def _after_copy(self, copied, errors, dest_label):
        self._progress["value"] = 100
        self._progress_label.config(text="")

        if errors:
            messagebox.showerror("Some errors", "\n".join(errors[:5]))
        else:
            messagebox.showinfo("Done", f"{len(copied)} file(s) copied to {dest_label}.")

        if self._pdf_var.get() and copied:
            def make_pdf():
                try:
                    ts      = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    pdf_out = os.path.expanduser(f"~/Desktop/FolderDiffReport_{ts}.pdf")
                    a = self._real_a or self._folder_a.get().strip()
                    b = self._real_b or self._folder_b.get().strip()
                    ok, res = generate_pdf_report(copied, a, b, pdf_out)
                    if ok and os.path.exists(pdf_out):
                        self.after(0, lambda p=pdf_out: subprocess.run(["open", p]))
                    else:
                        self.after(0, lambda r=res:
                            messagebox.showwarning("PDF not generated", r))
                except Exception as e:
                    self.after(0, lambda err=str(e):
                        messagebox.showwarning("PDF error", err))
            threading.Thread(target=make_pdf, daemon=True).start()

        self._start_compare()


if __name__ == "__main__":
    app = FolderDiffApp()
    app.mainloop()
