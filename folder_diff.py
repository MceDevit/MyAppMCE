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
DANGER    = "#ff1744"   # bright red — good on dark
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

APP_NAME    = "Folder Differences"
APP_VERSION = "v17"

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
        # Base-14 PDF fonts cover Latin-1 (French accents) reliably.
        FNORM = "Helvetica"
        FBOLD = "Helvetica-Bold"
        FMONO = "Courier"
    except ImportError:
        return False, "reportlab not installed.\nRun: pip3 install reportlab"

    from xml.sax.saxutils import escape as _xml_escape

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
                              leading=26, textColor=C_TITLE,
                              spaceAfter=10, alignment=TA_LEFT)
    sub_s   = ParagraphStyle("S", fontName=FNORM, fontSize=10,
                              leading=12, textColor=C_HDR,
                              spaceBefore=2, spaceAfter=2, alignment=TA_LEFT)
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
        ("BACKGROUND",    (0,0),(0,-1), colors.HexColor("#fff8e1")),
        ("BACKGROUND",    (1,0),(1,-1), colors.white),
        ("TEXTCOLOR",     (0,0),(0,-1), colors.HexColor("#b45309")),
        ("TEXTCOLOR",     (1,0),(1,-1), C_BODY),
        ("FONTNAME",      (0,0),(0,-1), FBOLD),
        ("FONTNAME",      (1,0),(1,-1), FNORM),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.HexColor("#e5d3a3")),
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
        fname = _xml_escape(Path(f["src"]).name)
        src_p = _xml_escape(f["src"])
        dst_p = _xml_escape(f["dst"])
        cell = Paragraph(
            f'{fname}<br/><font name="{FMONO}" size="8" color="#444746">{src_p}</font>',
            fname_s
        )
        dest_cell = Paragraph(dst_p, path_s)
        dir_cell  = Paragraph(direction,
                               ParagraphStyle("d", fontName=FBOLD, fontSize=9,
                                              textColor=dir_color))
        table_data.append([str(i), dir_cell, cell, dest_cell])

    bg_a = colors.HexColor("#f5f5f5")
    bg_b = colors.white
    file_tbl = Table(table_data, colWidths=COL_W, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (0,0),(-1,0),  C_HDR),
        ("GRID",          (0,0),(-1,-1), 0.3, colors.HexColor("#cccccc")),
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

def compare_folders(folder_a, folder_b, progress_cb, done_cb, quick=False):
    """
    Walk both folders and return:
      only_a  : files only in A  (rel_path → abs_path_a)
      only_b  : files only in B  (rel_path → abs_path_b)
      different: files in both but with different content
                (rel_path → (abs_a, abs_b))
    """
    def collect(folder):
        result = {}
        if os.path.isfile(folder):
            name = os.path.basename(folder)
            if not _is_temp_file(name):
                result[name] = folder
            return result
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
            for name in files:
                if _is_temp_file(name):
                    continue
                abs_p = os.path.join(root, name)
                rel   = os.path.relpath(abs_p, folder)
                result[rel] = abs_p
        return result

    # Single-file mode: search folder_b recursively
    if os.path.isfile(folder_a):
        src_name = os.path.basename(folder_a)

        if quick:
            # Filename-only match
            matches = []
            for root, dirs, files in os.walk(folder_b):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for name in files:
                    if name == src_name:
                        matches.append(os.path.join(root, name))
            progress_cb(1, 1, src_name)
            if matches:
                done_cb({}, {}, {}, {src_name: matches})
            else:
                done_cb({src_name: folder_a}, {}, {}, {})
            return

        try:
            src_size  = os.path.getsize(folder_a)
            src_quick = file_quick_hash(folder_a)
            src_full  = file_hash(folder_a)
        except OSError:
            done_cb({src_name: folder_a}, {}, {}, {})
            return

        candidates = []
        for root, dirs, files in os.walk(folder_b):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for name in files:
                if _is_temp_file(name):
                    continue
                fp = os.path.join(root, name)
                try:
                    if os.path.getsize(fp) == src_size:
                        candidates.append(fp)
                except OSError:
                    pass

        matches = []
        total = max(len(candidates), 1)
        last = 0
        for i, fp in enumerate(candidates, 1):
            if file_quick_hash(fp) == src_quick and file_hash(fp) == src_full:
                matches.append(fp)
            if i - last >= 25 or i == len(candidates):
                progress_cb(i, total, fp)
                last = i

        if matches:
            done_cb({}, {}, {}, {src_name: matches})
        else:
            done_cb({src_name: folder_a}, {}, {}, {})
        return

    files_a = collect(folder_a)
    files_b = collect(folder_b)

    keys_a = set(files_a)
    keys_b = set(files_b)

    only_a   = {k: files_a[k] for k in keys_a - keys_b}
    only_b   = {k: files_b[k] for k in keys_b - keys_a}
    common   = sorted(keys_a & keys_b)

    different = {}
    total = len(common)

    # Quick mode: filename-only — common files are assumed identical
    if quick:
        progress_cb(total, max(total, 1), "")
        done_cb(only_a, only_b, different, {})
        return

    if total == 0:
        done_cb(only_a, only_b, different, {})
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

    done_cb(only_a, only_b, different, {})


# ── App ───────────────────────────────────────────────────────────────────────

class FolderDiffApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1500x900")
        self.minsize(1000, 680)
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
        self._pdf_var    = tk.BooleanVar(value=True)
        self._comparing  = False  # prevent concurrent compare operations
        self._size_a     = tk.StringVar(value="")
        self._size_b     = tk.StringVar(value="")
        self._iid_data   = {}   # iid -> dict (status, name, rel, data, tags)
        self._selectable_iids = []
        self._anchor_iid      = None  # anchor for Shift+Arrow range selection
        self._matched_source = None  # set when a single-file match is found
        self._quick_check    = tk.BooleanVar(value=False)  # filenames-only mode


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

        self._build_folder_row(pickers, "Folder 1", self._folder_a, self._browse_a, ONLY_A, self._size_a,
                                browse_folder_cmd=self._browse_a_folder)
        self._build_folder_row(pickers, "Folder 2", self._folder_b, self._browse_b, ONLY_B, self._size_b)

        # ── Compare button ──
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=28, pady=(12, 0))
        self._compare_btn = self._make_btn(btn_row, "  Compare Folders  ",
                                            self._start_compare,
                                            bg=ACCENT, fg="#ffffff", pad=(20, 0))
        self._compare_btn.pack(side="left")

        tk.Checkbutton(
            btn_row,
            text="  Quick check (filenames only — skip content hashing)",
            variable=self._quick_check,
            font=FONT_SMALL, bg=BG, fg=FG_DIM,
            selectcolor=CARD, activebackground=BG, activeforeground=FG,
            relief="flat", bd=0, cursor="hand2"
        ).pack(side="left", padx=(20, 0))

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

        # ── Match action (single-file match) — packed only when populated
        self._match_actions = tk.Frame(self, bg=BG)

        # ── Results tree ──
        results_frame = tk.Frame(self, bg=SURFACE,
                                  highlightthickness=1, highlightbackground=BORDER)
        results_frame.pack(fill="both", expand=True, padx=28, pady=(8, 0))

        cols = ("status", "file", "rel_path", "action")
        self._tree = ttk.Treeview(results_frame, columns=cols,
                                   show="headings", selectmode="extended")
        self._tree.bind("<<TreeviewSelect>>", lambda _: self._update_selection_count())
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

        self._tree.bind("<Double-1>",         self._on_double_click)
        self._tree.bind("<Return>",            self._on_return_key)
        self._tree.bind("<Command-a>",         self._on_select_all_key)
        self._tree.bind("<Escape>",            lambda _: self._deselect_all())
        self._tree.bind("<space>",             self._on_space_key)
        self._tree.bind("<Button-1>",          lambda _: self.after(10, self._set_anchor_and_update))
        self._tree.bind("<Shift-Button-1>",    lambda _: self.after(10, self._update_selection_count))
        self._tree.bind("<KeyRelease-Up>",     self._on_plain_arrow_release)
        self._tree.bind("<KeyRelease-Down>",   self._on_plain_arrow_release)
        self._tree.bind("<Shift-Up>",          lambda _: self._on_shift_arrow("up"))
        self._tree.bind("<Shift-Down>",        lambda _: self._on_shift_arrow("down"))

        # ── Copy buttons ──
        copy_bar = tk.Frame(self, bg=BG)
        copy_bar.pack(fill="x", padx=28, pady=(10, 0))

        self._make_btn(copy_bar, "→  Copy selected to Folder 1",
                       lambda: self._copy_selected("to_a"),
                       bg=ONLY_A, fg="#ffffff", pad=(10, 0)).pack(side="left", padx=(0, 6))

        self._make_btn(copy_bar, "←  Copy selected to Folder 2",
                       lambda: self._copy_selected("to_b"),
                       bg=ONLY_B, fg="#ffffff", pad=(10, 0)).pack(side="left", padx=(0, 6))

        self._make_btn(copy_bar, "⇒  Move selected to Folder 2",
                       lambda: self._copy_selected("to_b", move=True),
                       bg=ONLY_B, fg="#ffffff", pad=(10, 0)).pack(side="left", padx=(0, 6))

        self._make_btn(copy_bar, "⇐  Move selected to Folder 1",
                       lambda: self._copy_selected("to_a", move=True),
                       bg=ONLY_A, fg="#ffffff", pad=(10, 0)).pack(side="left", padx=(0, 6))

        self._make_btn(copy_bar, "Reveal in Finder",
                       self._reveal_selected,
                       bg=CARD, fg=FG, pad=(10, 0)).pack(side="left", padx=(0, 6))

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

    def _build_folder_row(self, parent, label, var, browse_cmd, color, size_var,
                          browse_folder_cmd=None):
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

        file_label = "File…" if browse_folder_cmd else "Browse…"
        self._make_btn(row, file_label, browse_cmd,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left")
        if browse_folder_cmd:
            self._make_btn(row, "Folder…", browse_folder_cmd,
                           bg=CARD, fg=FG, pad=(14, 0)).pack(side="left", padx=(6, 0))

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
        """Return human-readable total size of a folder or single file."""
        total = 0
        if os.path.isfile(folder):
            try:
                total = os.path.getsize(folder)
            except OSError:
                pass
        else:
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
        path = filedialog.askopenfilename(title="Choose a file (Folder 1)")
        if path:
            self._real_a = path
            self._folder_a.set(path)
            self._size_a.set("calculating…")
            threading.Thread(
                target=lambda: self.after(0, lambda:
                    self._size_a.set(self._folder_size(path))),
                daemon=True
            ).start()

    def _browse_a_folder(self):
        folder = filedialog.askdirectory(title="Choose a folder (Folder 1)")
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
        if self._comparing:
            return
        
        a = self._real_a or self._folder_a.get().strip()
        b = self._real_b or self._folder_b.get().strip()

        if not a or not (os.path.isfile(a) or os.path.isdir(a)):
            messagebox.showwarning("Missing folder", "Please choose Folder 1 first.")
            return
        if not b or not os.path.isdir(b):
            messagebox.showwarning("Missing folder", "Please choose Folder 2 first.")
            return
        
        self._comparing = True

        self._tree.delete(*self._tree.get_children())
        self._iid_data = {}
        self._selectable_iids = []
        for w in self._match_actions.winfo_children():
            w.destroy()
        self._match_actions.pack_forget()
        self._matched_source = None
        self._clear_stats()
        self._progress["value"] = 0
        self._progress_label.config(text="Comparing…")
        self._compare_btn.config(text="Comparing…")
        self.update_idletasks()

        def on_progress(done, total, name):
            if total:
                self.after(0, lambda:
                    self._progress.configure(value=(done/total)*100))
            self.after(0, lambda n=Path(name).name:
                self._progress_label.config(text=f"Checking: {n}"))

        def on_done(only_a, only_b, different, matched):
            self.after(0, lambda: self._render(only_a, only_b, different, matched))

        quick = bool(self._quick_check.get())
        threading.Thread(target=compare_folders,
                         args=(a, b, on_progress, on_done),
                         kwargs={"quick": quick},
                         daemon=True).start()

    def _render(self, only_a, only_b, different, matched=None):
        self._comparing = False
        self._only_a    = only_a
        self._only_b    = only_b
        self._different = different
        matched = matched or {}

        self._tree.delete(*self._tree.get_children())
        self._iid_data = {}
        self._selectable_iids = []
        self._anchor_iid = None
        self._progress["value"] = 0
        self._progress_label.config(text="")
        self._compare_btn.config(text="  Compare Folders  ")

        # Reset match-action bar
        for w in self._match_actions.winfo_children():
            w.destroy()
        self._match_actions.pack_forget()
        self._matched_source = None
        if matched and len(matched) == 1:
            src_path = self._real_a or self._folder_a.get().strip()
            if src_path and os.path.isfile(src_path):
                self._matched_source = src_path
                self._make_btn(
                    self._match_actions,
                    f"🗑  Delete “{Path(src_path).name}” from Folder 1 (it exists in Folder 2)",
                    self._delete_matched_source,
                    bg=DANGER, fg="#ffffff", pad=(16, 0),
                ).pack(side="left")
                self._match_actions.pack(fill="x", padx=28, pady=(6, 0),
                                          before=self._tree.master)

        self._clear_stats()
        total = len(only_a) + len(only_b) + len(different)
        match_count = sum(len(v) for v in matched.values())
        self._add_stat("Only in Folder 1", str(len(only_a)),    ONLY_A)
        self._add_stat("Only in Folder 2", str(len(only_b)),    ONLY_B)
        self._add_stat("Differences", str(len(different)), DIFF)
        self._add_stat("Total differences", str(total),          ACCENT)
        if matched:
            self._add_stat("Matches in Folder 2", str(match_count), ONLY_B)

        if total == 0 and not matched:
            self._tree.insert("", "end",
                               values=("✅  Folders are identical", "", "", ""),
                               tags=("section",))
            return

        # Build all rows up front, insert in batches
        rows = []
        if matched:
            for src_name, paths in matched.items():
                rows.append(("section_b",
                             (f"── Match found in Folder 2 for “{src_name}”  ({len(paths)} file(s))", "", "", "")))
                for p in paths:
                    rows.append(("only_b",
                                 ("Match in Folder 2", Path(p).name, p, p)))
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
            self._progress["value"] = 0
            self._update_selection_count()
            self.update_idletasks()

    # ── Selection ─────────────────────────────────────────────────────────────

    def _on_plain_arrow_release(self, event):
        """KeyRelease-Up/Down — only reset anchor when Shift is not held."""
        if event.state & 0x0001:  # Shift modifier: skip so anchor stays fixed
            return
        self._set_anchor_and_update()

    def _set_anchor_and_update(self):
        """Called after plain arrow-key or click — update anchor to focused row."""
        focused = self._tree.focus()
        selectable = set(self._selectable_iids)
        if focused and focused in selectable:
            self._anchor_iid = focused
        self._update_selection_count()

    def _on_shift_arrow(self, direction):
        """Shift+Up/Down — range-select from anchor to next selectable neighbour."""
        children = list(self._tree.get_children())
        focused = self._tree.focus()
        if not focused or focused not in children:
            return "break"

        selectable = set(self._selectable_iids)
        step = 1 if direction == "down" else -1

        # Find the next selectable row in the given direction.
        target = None
        i = children.index(focused) + step
        while 0 <= i < len(children):
            if children[i] in selectable:
                target = children[i]
                break
            i += step
        if not target:
            return "break"

        self._tree.focus(target)
        self._tree.see(target)

        # If no anchor yet, establish one at the current focused row.
        if self._anchor_iid is None or self._anchor_iid not in children:
            self._anchor_iid = focused if focused in selectable else target

        # Select exactly the contiguous range [anchor … target], deselecting
        # anything outside it so moving back toward anchor shrinks the selection.
        anchor_idx = children.index(self._anchor_iid)
        target_idx = children.index(target)
        lo, hi = min(anchor_idx, target_idx), max(anchor_idx, target_idx)
        self._tree.selection_set(
            [iid for iid in children[lo : hi + 1] if iid in selectable]
        )
        self._update_selection_count()
        return "break"

    def _on_return_key(self, _):
        """Enter key — reveal the focused row in Finder."""
        iid = self._tree.focus()
        if not iid:
            return
        tags = self._tree.item(iid, "tags")
        if any(tag.startswith("section") for tag in tags):
            return
        vals = self._tree.item(iid, "values")
        if not vals:
            return
        data = vals[3]
        path = data.split("||")[0] if "||" in data else data
        if os.path.exists(path):
            try:
                subprocess.run(["open", "-R", path], timeout=5, check=False)
            except Exception:
                pass
        return "break"

    def _on_space_key(self, _):
        """Space — toggle selection of the focused row and reset anchor."""
        iid = self._tree.focus()
        if not iid or iid not in self._selectable_iids:
            return "break"
        if iid in self._tree.selection():
            self._tree.selection_remove(iid)
        else:
            self._tree.selection_add(iid)
        self._anchor_iid = iid
        self._update_selection_count()
        return "break"

    def _on_select_all_key(self, _):
        """Cmd+A handler to select all selectable files."""
        targets = list(self._selectable_iids)
        if targets:
            self._anchor_iid = None
            self._tree.selection_set(targets)
            self._update_selection_count()
        return "break"

    def _update_selection_count(self):
        pass

    def _select_all(self):
        self._tree.selection_set([])
        targets = list(self._selectable_iids)
        if not targets:
            return
        self._progress_label.config(text=f"Selecting… 0 / {len(targets)}")
        self.update_idletasks()
        self.after(1, lambda: self._batch_select(targets, 0))

    def _deselect_all(self):
        """Clear all selections."""
        self._tree.selection_set([])
        self._update_selection_count()

    def _batch_select(self, iids, start, chunk=100):
        end = min(start + chunk, len(iids))
        self._tree.selection_add(*iids[start:end])
        if end < len(iids):
            self._progress_label.config(text=f"Selecting… {end} / {len(iids)}")
            self.update_idletasks()
            self.after(1, lambda: self._batch_select(iids, end, chunk))
        else:
            self._update_selection_count()

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

    # ── Delete matched single source ──────────────────────────────────────────

    def _delete_matched_source(self):
        src = self._matched_source
        if not src or not os.path.isfile(src):
            messagebox.showwarning("No file", "No matched source file to delete.")
            return
        if not messagebox.askyesno(
            "Move to Trash",
            f"Move “{Path(src).name}” to the Trash?\n\n"
            f"The matching file in Folder 2 will be kept.\n"
            f"This can be undone from the Trash.",
            icon="warning",
        ):
            return
        try:
            escaped = src.replace('"', '\\"')
            script  = f'tell application "Finder" to delete POSIX file "{escaped}"'
            result  = subprocess.run(["osascript", "-e", script],
                                     capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Finder refused the delete")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        messagebox.showinfo("Deleted", f"Moved to Trash: {Path(src).name}")
        self._real_a = ""
        self._folder_a.set("")
        self._size_a.set("")
        self._tree.delete(*self._tree.get_children())
        self._iid_data = {}
        self._selectable_iids = []
        for w in self._match_actions.winfo_children():
            w.destroy()
        self._match_actions.pack_forget()
        self._matched_source = None
        self._clear_stats()

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
                try:
                    subprocess.run(["open", "-R", path], timeout=5, check=False)
                except Exception:
                    pass

    # ── Double-click ──────────────────────────────────────────────────────────

    def _on_double_click(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        vals = self._tree.item(iid, "values")
        tags = self._tree.item(iid, "tags")
        if not vals or any(tag.startswith("section") for tag in tags):
            return
        data = vals[3]
        path = data.split("||")[0] if "||" in data else data
        if os.path.exists(path):
            try:
                subprocess.run(["open", "-R", path], timeout=5, check=False)
            except Exception:
                pass

    # ── Copy ──────────────────────────────────────────────────────────────────

    def _copy_selected(self, direction, move=False):
        """direction: 'to_a' or 'to_b'.  If move=True, source files are deleted after copy."""
        items = self._get_selected_items()
        if not items:
            messagebox.showinfo("Nothing selected", "Select one or more files first.")
            return

        dest_folder = self._real_a if direction == "to_a" else self._real_b
        dest_label  = "Folder 1" if direction == "to_a" else "Folder 2"
        verb        = "Move" if move else "Copy"
        
        if os.path.isfile(dest_folder):
            messagebox.showwarning(
                "Invalid destination",
                "Cannot copy files to a single file destination. "
                "Please choose a folder for " + dest_label + "."
            )
            return

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
                f"Nothing to {verb.lower()}",
                f"Selected files already exist in {dest_label} with identical content."
            )
            return

        confirm_extra = ("Source files will be removed."
                         if move else "Existing files will be overwritten.")
        if not messagebox.askyesno(
            f"{verb} files",
            f"{verb} {len(copyable)} file(s) to {dest_label}?\n\n{confirm_extra}",
            icon="warning" if move else "question",
        ):
            return

        self._progress["value"] = 0
        self._progress_label.config(text=f"{verb}ing… 0 / {len(copyable)}")
        self.update_idletasks()

        def worker():
            errors = []
            copied = []
            total = len(copyable)
            for i, (rel, src, _) in enumerate(copyable, 1):
                dst = os.path.join(dest_folder, rel)
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if move:
                        shutil.move(src, dst)
                    else:
                        shutil.copy2(src, dst)
                    copied.append({"src": src, "dst": dst, "direction": direction})
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")
                if i % 5 == 0 or i == total:
                    self.after(0, lambda done=i, t=total:
                        (self._progress.configure(value=(done/t)*100),
                         self._progress_label.config(text=f"{verb}ing… {done} / {t}")))

            self.after(0, lambda: self._after_copy(copied, errors, dest_label, move))

        threading.Thread(target=worker, daemon=True).start()

    def _after_copy(self, copied, errors, dest_label, move=False):
        self._progress["value"] = 0
        self._progress_label.config(text="")

        verb_past = "moved" if move else "copied"
        if errors:
            messagebox.showerror("Some errors", "\n".join(errors[:5]))
        else:
            messagebox.showinfo("Done", f"{len(copied)} file(s) {verb_past} to {dest_label}.")

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
