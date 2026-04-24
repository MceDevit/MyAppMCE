#!/usr/bin/env python3
"""
Duplicate File Finder — macOS Desktop App
Run with: python3 duplicate_finder.py
Requires: pip3 install reportlab
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import hashlib
import threading
from collections import defaultdict
from pathlib import Path
import subprocess
import shutil
import datetime

# ── Colour palette — Modern light grey ──────────────────────────────────────
BG        = "#f0f2f5"   # light grey background
SURFACE   = "#ffffff"   # white panels
CARD      = "#e8eaed"   # slightly darker grey cards
ACCENT    = "#1a73e8"   # Google-blue — vivid, modern
ACCENT2   = "#0d47a1"   # deeper blue for highlights
DANGER    = "#d32f2f"   # strong red — good contrast on light
SUCCESS   = "#2e7d32"   # deep green — readable on light
MUTED     = "#5f6368"   # Google grey — AA contrast on white
FG        = "#1c1b1f"   # near-black — max contrast
FG_DIM    = "#444746"   # dark grey — still very readable
BORDER    = "#c4c7c5"   # subtle grey border

FONT_TITLE  = ("SF Pro Display", 22, "bold")
FONT_LABEL  = ("SF Pro Text",    13)
FONT_SMALL  = ("SF Pro Text",    11)
FONT_MONO   = ("SF Mono",        11)
FONT_BTN    = ("SF Pro Text",    13, "bold")


# ── PDF Report ───────────────────────────────────────────────────────────────

def generate_pdf_report(groups, folder, output_path):
    """
    Generate a landscape PDF report.
    groups = list of dicts:
      { "source": {"path": ..., "size": ...},
        "deleted": [{"path": ..., "size": ...}, ...] }
    """
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
        import reportlab, os as _os
        _fonts = _os.path.join(_os.path.dirname(reportlab.__file__), "fonts")
        pdfmetrics.registerFont(TTFont("Vera",   _os.path.join(_fonts, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("VeraBd", _os.path.join(_fonts, "VeraBd.ttf")))
        pdfmetrics.registerFont(TTFont("VeraIt", _os.path.join(_fonts, "VeraIt.ttf")))
        pdfmetrics.registerFont(TTFont("VeraBI", _os.path.join(_fonts, "VeraBI.ttf")))
        pdfmetrics.registerFont(TTFont("VeraMono", _os.path.join(_fonts, "VeraBd.ttf")))
        FONT_NORMAL = "Vera"
        FONT_BOLD   = "VeraBd"
        FONT_ITALIC = "VeraIt"
        FONT_MONO   = "VeraMono"
    except ImportError:
        return False, "reportlab not installed.\nRun: pip3 install reportlab"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Warm colour palette
    C_HEADER_BG   = colors.HexColor("#b45309")   # amber-700  — table header
    C_SEP_BG      = colors.HexColor("#fef3c7")   # amber-100  — group separator
    C_SEP_TEXT    = colors.HexColor("#92400e")   # amber-800
    C_SRC_BG      = colors.HexColor("#fef9ee")   # warm cream — source row
    C_SRC_LABEL   = colors.HexColor("#b45309")   # amber-700
    C_DEL_BG_A    = colors.HexColor("#fff7ed")   # orange-50
    C_DEL_BG_B    = colors.HexColor("#ffffff")
    C_DEL_LABEL   = colors.HexColor("#c2410c")   # orange-700
    C_PATH        = colors.HexColor("#78350f")   # amber-900
    C_TITLE       = colors.HexColor("#7c2d12")   # orange-900
    C_ACCENT      = colors.HexColor("#b45309")   # amber-700
    C_SUMMARY_KEY = colors.HexColor("#92400e")
    C_BODY        = colors.HexColor("#1c1917")   # stone-900

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Duplicate Files - Deletion Report"
    )

    title_style = ParagraphStyle(
        "T", fontName=FONT_BOLD, fontSize=22,
        textColor=C_TITLE, spaceAfter=3, alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "S", fontName=FONT_NORMAL, fontSize=10,
        textColor=C_ACCENT, spaceAfter=2, alignment=TA_LEFT,
    )
    section_style = ParagraphStyle(
        "Sec", fontName=FONT_BOLD, fontSize=12,
        textColor=C_ACCENT, spaceBefore=12, spaceAfter=5,
    )
    note_style = ParagraphStyle(
        "N", fontName="Helvetica-Oblique", fontSize=8,
        textColor=colors.HexColor("#a16207"), spaceAfter=2,
    )
    # File name — bigger, bold, warm dark
    fname_style = ParagraphStyle(
        "FN", fontName=FONT_BOLD, fontSize=11,
        textColor=C_BODY, leading=14,
    )
    # Path — monospace, smaller, muted warm
    path_style = ParagraphStyle(
        "P", fontName=FONT_MONO, fontSize=8,
        textColor=C_PATH, leading=10,
    )

    def fmt_size(n):
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    all_deleted = [f for g in groups for f in g["deleted"]]

    story = []

    # ── Header ──
    story.append(Paragraph("Duplicate File Finder", title_style))
    story.append(Paragraph("Deletion Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=C_ACCENT, spaceAfter=8))

    # ── Summary ──
    summary_data = [
        ["Date",             now],
        ["Folder scanned",   folder],
        ["Duplicate groups", str(len(groups))],
        ["Files deleted",    str(len(all_deleted))],
    ]
    summary_table = Table(summary_data, colWidths=[4*cm, 22*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#fef3c7")),
        ("BACKGROUND",    (1, 0), (1, -1), colors.HexColor("#fffbeb")),
        ("TEXTCOLOR",     (0, 0), (0, -1), C_SUMMARY_KEY),
        ("TEXTCOLOR",     (1, 0), (1, -1), C_BODY),
        ("FONTNAME",      (0, 0), (0, -1), FONT_BOLD),
        ("FONTNAME",      (1, 0), (1, -1), FONT_NORMAL),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#fcd34d")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # ── Per-group table ──
    # Columns: # | Role | File Name + Path (2 lines) | (no size)
    COL_W = [1*cm, 2.2*cm, 22.5*cm]

    story.append(Paragraph("Duplicate Groups", section_style))
    story.append(Paragraph(
        "Each group shows the kept original (SOURCE) followed by deleted duplicates (DELETED). "
        "Deleted files are in the macOS Trash and can be restored.",
        note_style
    ))
    story.append(Spacer(1, 5))

    def make_h(text):
        return Paragraph(f"<b>{text}</b>",
                         ParagraphStyle("h", fontName=FONT_BOLD, fontSize=9,
                                        textColor=colors.white))

    header_row = [make_h("#"), make_h("Role"), make_h("File Name  /  Path")]
    table_data = [header_row]
    row_colors = []

    row_idx = 1
    for g_idx, group in enumerate(groups):
        bg_del = C_DEL_BG_A if g_idx % 2 == 0 else C_DEL_BG_B

        # separator
        sep_text = f"Group {g_idx + 1}  —  {len(group['deleted'])} duplicate(s) deleted"
        table_data.append([
            Paragraph(sep_text,
                      ParagraphStyle("sep", fontName=FONT_BOLD, fontSize=8,
                                     textColor=C_SEP_TEXT)),
            "", ""
        ])
        row_colors.append((row_idx, C_SEP_BG))
        row_idx += 1

        # source row — file name + path on second line
        src = group["source"]
        src_name = Path(src["path"]).name
        src_cell = Paragraph(
            f'{src_name}<br/>'
            f'<font name="{FONT_MONO}" size="8" color="#78350f">{src["path"]}</font>',
            fname_style
        )
        table_data.append([
            str(g_idx + 1),
            Paragraph("SOURCE",
                      ParagraphStyle("src", fontName=FONT_BOLD, fontSize=9,
                                     textColor=C_SRC_LABEL)),
            src_cell,
        ])
        row_colors.append((row_idx, C_SRC_BG))
        row_idx += 1

        # deleted rows
        for f in group["deleted"]:
            fname = Path(f["path"]).name
            del_cell = Paragraph(
                f'{fname}<br/>'
                f'<font name="{FONT_MONO}" size="8" color="#78350f">{f["path"]}</font>',
                fname_style
            )
            table_data.append([
                "",
                Paragraph("DELETED",
                           ParagraphStyle("del", fontName=FONT_BOLD, fontSize=9,
                                          textColor=C_DEL_LABEL)),
                del_cell,
            ])
            row_colors.append((row_idx, bg_del))
            row_idx += 1

    style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0), C_HEADER_BG),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#fcd34d")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]
    for (ri, bg) in row_colors:
        style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), bg))

    # Span separator rows
    ri = 1
    for g_idx, group in enumerate(groups):
        style_cmds.append(("SPAN", (0, ri), (-1, ri)))
        style_cmds.append(("LEFTPADDING", (0, ri), (-1, ri), 8))
        ri += 2 + len(group["deleted"])

    main_table = Table(table_data, colWidths=COL_W, repeatRows=1)
    main_table.setStyle(TableStyle(style_cmds))
    story.append(main_table)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#fcd34d"), spaceAfter=6))
    story.append(Paragraph(
        "Generated by Duplicate File Finder  •  Deleted files are in the macOS Trash and can be recovered.",
        note_style
    ))

    doc.build(story)
    return True, output_path

# ── File scanning ─────────────────────────────────────────────────────────────

def get_display_path(path):
    """Return the path as-is."""
    return path

def file_hash(path, buf=65536):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(buf):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None

import re as _re

# Temporary files to skip
_TEMP_PATTERNS = _re.compile(
    r'(\.(tmp|temp|bak|cache|lock)$'       # generic temp extensions
    r'|~\$'                                  # Word/Excel lock files (~$doc.docx)
    r'|\.[a-zA-Z]{2,4}[A-F0-9]{2,4}$'      # .docXXX .xlsAB3 temp files
    r'|\.part$'                              # partial downloads
    r')', _re.IGNORECASE
)

def _is_temp_file(name):
    """Return True if the file looks like a temporary/lock file to skip."""
    if name.startswith('~$'):
        return True
    if name.startswith('.'):
        return True
    if _TEMP_PATTERNS.search(name):
        return True
    return False

def find_duplicates(folder, progress_cb, done_cb):
    size_map = defaultdict(list)
    all_files = []

    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in files:
            if _is_temp_file(name):
                continue
            fp = os.path.join(root, name)
            try:
                sz = os.path.getsize(fp)
                if sz > 0:
                    size_map[sz].append(fp)
                    all_files.append(fp)
            except OSError:
                pass

    candidates = [paths for paths in size_map.values() if len(paths) > 1]
    total = sum(len(p) for p in candidates)
    done_count = [0]

    hash_map = defaultdict(list)
    for paths in candidates:
        for fp in paths:
            h = file_hash(fp)
            if h:
                hash_map[h].append(fp)
            done_count[0] += 1
            progress_cb(done_count[0], total, fp)

    dupes = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    done_cb(dupes, len(all_files))


# ── App ───────────────────────────────────────────────────────────────────────

class DuplicateFinderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Duplicate Finder")
        self.geometry("1200x780")
        self.minsize(1000, 600)
        self.configure(bg=BG)

        try:
            self.tk.call("::tk::unsupported::MacWindowStyle", "style", self._w, "document", "")
        except Exception:
            pass

        self._selected_folder = tk.StringVar(value="")
        self._dupes = {}
        self._pdf_var = tk.BooleanVar(value=True)

        self._build_ui()

        # macOS menu: rename app + Quit + Cmd+Q
        try:
            menubar = tk.Menu(self)
            app_menu = tk.Menu(menubar, name="apple")
            menubar.add_cascade(menu=app_menu)
            app_menu.add_command(label="About Duplicate Finder")
            app_menu.add_separator()
            app_menu.add_command(label="Quit Duplicate Finder",
                                  command=self.destroy, accelerator="Cmd+Q")
            self.config(menu=menubar)
            self.bind_all("<Command-q>", lambda e: self.destroy())
        except Exception:
            pass

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(24, 0))
        tk.Label(header, text="⊜  Duplicate Finder",
                 font=FONT_TITLE, bg=BG, fg=FG).pack(side="left")

        # Folder picker
        picker = tk.Frame(self, bg=BG)
        picker.pack(fill="x", padx=28, pady=(18, 0))
        tk.Label(picker, text="Folder", font=FONT_LABEL,
                 bg=BG, fg=FG_DIM, width=6, anchor="w").pack(side="left")
        self._path_entry = tk.Entry(
            picker, textvariable=self._selected_folder,
            font=FONT_MONO, bg=CARD, fg=FG, relief="flat",
            insertbackground=ACCENT, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT
        )
        self._path_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 10))
        self._make_btn(picker, "Browse...", self._browse,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left", padx=(0, 10))
        self._scan_btn = self._make_btn(picker, "  Scan  ", self._start_scan,
                                        bg=ACCENT, fg="#ffffff", pad=(18, 0))
        self._scan_btn.pack(side="left")

        # Progress
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=28, pady=(14, 0))
        self._progress_label = tk.Label(prog_frame, text="",
                                        font=FONT_SMALL, bg=BG, fg=FG_DIM)
        self._progress_label.pack(anchor="w")
        self._progress = ttk.Progressbar(prog_frame, mode="determinate")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT,
                         thickness=4, borderwidth=0)
        self._progress.pack(fill="x", pady=(4, 0))

        # Stats
        self._stats_frame = tk.Frame(self, bg=BG)
        self._stats_frame.pack(fill="x", padx=28, pady=(12, 0))

        # Results
        results_frame = tk.Frame(self, bg=SURFACE,
                                  highlightthickness=1, highlightbackground=BORDER)
        results_frame.pack(fill="both", expand=True, padx=28, pady=(12, 0))

        cols = ("keep", "file", "size", "path")
        self._tree = ttk.Treeview(results_frame, columns=cols, show="headings",
                                   selectmode="extended")
        style.configure("Treeview", background=SURFACE, foreground=FG,
                         fieldbackground=SURFACE, rowheight=28, borderwidth=0, font=FONT_SMALL)
        style.configure("Treeview.Heading", background=CARD, foreground=FG_DIM,
                         relief="flat", font=FONT_SMALL)
        style.map("Treeview", background=[("selected", ACCENT)])

        self._tree.heading("keep", text="")
        self._tree.heading("file", text="File name")
        self._tree.heading("size", text="Size")
        self._tree.heading("path", text="Full path")
        self._tree.column("keep", width=90,   minwidth=90,   stretch=False, anchor="center")
        self._tree.column("file", width=280,  minwidth=280,  stretch=False)
        self._tree.column("size", width=100,  minwidth=100,  stretch=False, anchor="e")
        self._tree.column("path", width=1200, minwidth=1200, stretch=False)

        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(side="left", fill="both", expand=True)

        self._tree.tag_configure("group_a", background=SURFACE)
        self._tree.tag_configure("group_b", background=CARD)
        self._tree.tag_configure("header", background="#d2e3fc",
                                  foreground=ACCENT2, font=(*FONT_SMALL[:2], "bold"))

        # Action bar
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=28, pady=(10, 6))
        self._make_btn(bar, "Select all duplicates", self._select_all_dupes,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left", padx=(0, 8))
        self._make_btn(bar, "Deselect all", self._deselect_all,
                       bg=CARD, fg=FG_DIM, pad=(14, 0)).pack(side="left", padx=(0, 8))
        tk.Frame(bar, bg=BG).pack(side="left", expand=True)
        self._make_btn(bar, "Reveal in Finder", self._reveal_selected,
                       bg=CARD, fg=FG, pad=(14, 0)).pack(side="left", padx=(0, 8))
        self._make_btn(bar, "  Move to Trash  ", self._delete_selected,
                       bg=DANGER, fg="#ffffff", pad=(16, 0)).pack(side="left")

        # PDF option
        pdf_row = tk.Frame(self, bg=BG)
        pdf_row.pack(fill="x", padx=28, pady=(4, 16))
        tk.Checkbutton(
            pdf_row,
            text="  Generate PDF report when moving to Trash",
            variable=self._pdf_var,
            font=FONT_SMALL, bg=BG, fg=FG_DIM,
            selectcolor=CARD, activebackground=BG, activeforeground=FG,
            relief="flat", bd=0, cursor="hand2"
        ).pack(side="left")
        tk.Label(pdf_row, text="(saved to your Desktop)",
                 font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="left", padx=(6, 0))

        tk.Frame(pdf_row, bg=BG).pack(side="left", expand=True)
        self._make_btn(pdf_row, "✕  Quit", self.destroy,
                       bg=CARD, fg=FG_DIM, pad=(14, 0)).pack(side="right")

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

    @staticmethod
    def _fmt_size(n):
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def _clear_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()

    def _add_stat(self, label, value, color=FG):
        f = tk.Frame(self._stats_frame, bg=BG)
        f.pack(side="left", padx=(0, 24))
        tk.Label(f, text=label, font=FONT_SMALL, bg=BG, fg=FG_DIM).pack(anchor="w")
        tk.Label(f, text=value, font=(*FONT_LABEL[:2], "bold"),
                 bg=BG, fg=color).pack(anchor="w")

    def _browse(self):
        folder = filedialog.askdirectory(title="Choose a folder to scan")
        if folder:
            # Store real path internally, show display name in the entry
            self._real_folder = folder
            display = get_display_path(folder)
            self._selected_folder.set(display)

    def _get_real_folder(self):
        """Return the real filesystem path even if display name is shown."""
        if hasattr(self, '_real_folder') and os.path.isdir(self._real_folder):
            return self._real_folder
        # Fallback: the entry value might already be a real path
        return self._selected_folder.get().strip()

    def _start_scan(self):
        folder = self._get_real_folder()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No folder", "Please choose a valid folder first.")
            return

        self._tree.delete(*self._tree.get_children())
        self._clear_stats()
        self._progress["value"] = 0
        self._progress_label.config(text="Scanning...")
        self._scan_btn.config(text="Scanning...", cursor="arrow")
        self._scan_btn.unbind("<Button-1>")

        def on_progress(done, total, fp):
            if total:
                self.after(0, lambda: self._progress.configure(value=(done/total)*100))
            self.after(0, lambda n=Path(fp).name:
                       self._progress_label.config(text=f"Hashing: {n}"))

        def on_done(dupes, total_files):
            self.after(0, lambda: self._render_results(dupes, total_files))
            self.after(0, self._enable_scan_btn)

        threading.Thread(target=find_duplicates,
                         args=(folder, on_progress, on_done), daemon=True).start()

    def _enable_scan_btn(self):
        self._scan_btn.config(text="  Scan  ", cursor="hand2")
        self._scan_btn.bind("<Button-1>", lambda e: self._start_scan())

    def _render_results(self, dupes, total_files):
        self._dupes = dupes
        self._tree.delete(*self._tree.get_children())
        self._progress["value"] = 100
        self._progress_label.config(text="")
        self._enable_scan_btn()

        self._clear_stats()
        dupe_count = sum(len(v) - 1 for v in dupes.values())
        wasted = sum(os.path.getsize(p) * (len(paths) - 1)
                     for paths in dupes.values() for p in paths[:1])
        self._add_stat("Files scanned",   str(total_files), FG)
        self._add_stat("Duplicate sets",  str(len(dupes)),  ACCENT2)
        self._add_stat("Duplicate files", str(dupe_count),  DANGER if dupe_count else SUCCESS)
        self._add_stat("Space wasted",    self._fmt_size(wasted), DANGER if wasted else SUCCESS)

        if not dupes:
            self._tree.insert("", "end", values=("", "No duplicates found!", "", ""),
                               tags=("header",))
            return

        for idx, (h, paths) in enumerate(dupes.items()):
            tag = "group_a" if idx % 2 == 0 else "group_b"
            sz = os.path.getsize(paths[0])
            self._tree.insert("", "end",
                               values=("", f"-- Group {idx+1}  ({len(paths)} files, {self._fmt_size(sz)} each)", "", ""),
                               tags=("header",))
            for i, fp in enumerate(paths):
                self._tree.insert("", "end",
                                   values=("keep" if i == 0 else "delete",
                                           Path(fp).name, self._fmt_size(sz), fp),
                                   tags=(tag,))

    def _select_all_dupes(self):
        self._tree.selection_remove(*self._tree.get_children())
        self._tree.selection_set([
            iid for iid in self._tree.get_children()
            if self._tree.item(iid, "values") and
               self._tree.item(iid, "values")[0] == "delete"
        ])

    def _deselect_all(self):
        self._tree.selection_remove(*self._tree.get_children())

    def _get_selected_paths(self):
        return [
            self._tree.item(iid, "values")[3]
            for iid in self._tree.selection()
            if self._tree.item(iid, "values") and self._tree.item(iid, "values")[3]
        ]

    def _reveal_selected(self):
        paths = self._get_selected_paths()
        if not paths:
            messagebox.showinfo("Nothing selected", "Select one or more files first.")
            return
        for p in paths[:5]:
            subprocess.run(["open", "-R", p])

    def _delete_selected(self):
        paths = self._get_selected_paths()
        if not paths:
            messagebox.showinfo("Nothing selected",
                                "Select files to remove.\nTip: use \'Select all duplicates\'.")
            return

        msg = f"Move {len(paths)} file(s) to the Trash?"
        if self._pdf_var.get():
            msg += "\n\nA PDF report will be saved to your Desktop."
        msg += "\n\nThis can be undone from the Trash."

        if not messagebox.askyesno("Move to Trash", msg, icon="warning"):
            return

        # ── 1. Collect file info BEFORE deleting ──
        paths_set = set(paths)
        groups_info = []
        for h, group_paths in self._dupes.items():
            deleted_in_group = [p for p in group_paths if p in paths_set]
            if not deleted_in_group:
                continue
            kept = [p for p in group_paths if p not in paths_set]
            source_path = kept[0] if kept else group_paths[0]
            try:
                src_sz = os.path.getsize(source_path)
            except OSError:
                src_sz = 0
            deleted_files = []
            for p in deleted_in_group:
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    sz = 0
                deleted_files.append({"path": p, "size": sz})
            groups_info.append({
                "source":  {"path": source_path, "size": src_sz},
                "deleted": deleted_files,
            })

        if not groups_info:
            for p in paths:
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    sz = 0
                groups_info.append({
                    "source":  {"path": p, "size": sz},
                    "deleted": [{"path": p, "size": sz}],
                })

        # ── 2. Move to Trash ──
        # Always use AppleScript Finder — it handles cross-device (external volumes)
        # by moving to the volume's own .Trashes folder automatically.
        errors = []
        for p in paths:
            try:
                escaped = p.replace('"', '\\"')
                script  = f'''tell application "Finder" to delete POSIX file "{escaped}"'''
                result  = subprocess.run(["osascript", "-e", script],
                                         capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    # Fallback: detect the correct volume for this file
                    # e.g. /Volumes/Maia/foo/bar.pdf → volume = /Volumes/Maia
                    parts = Path(p).parts
                    if len(parts) >= 3 and parts[1] == "Volumes":
                        # External volume: /Volumes/VolumeName/...
                        volume = os.path.join("/", parts[1], parts[2])
                    else:
                        # System volume — use user Trash
                        volume = os.path.expanduser("~")

                    uid       = os.getuid()
                    vol_trash = os.path.join(volume, ".Trashes", str(uid))
                    try:
                        os.makedirs(vol_trash, exist_ok=True)
                    except OSError:
                        # Last resort: use home Trash with shutil (handles cross-device)
                        vol_trash = os.path.expanduser("~/.Trash")
                        os.makedirs(vol_trash, exist_ok=True)

                    dest = os.path.join(vol_trash, Path(p).name)
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(Path(p).name)
                        dest = os.path.join(vol_trash, f"{base}_{os.getpid()}{ext}")
                    shutil.move(p, dest)
            except Exception as e:
                errors.append(f"{Path(p).name}: {e}")

        # ── 3. Generate PDF ──
        pdf_path = None
        if self._pdf_var.get() and groups_info:
            try:
                ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                pdf_path = os.path.expanduser(f"~/Desktop/DuplicateReport_{ts}.pdf")
                folder   = self._get_real_folder()
                ok, res  = generate_pdf_report(groups_info, folder, pdf_path)
                if not ok:
                    messagebox.showwarning("PDF not generated", res)
                    pdf_path = None
            except Exception as e:
                messagebox.showwarning("PDF error", str(e))
                pdf_path = None

        # ── 4. Show result ──
        if errors:
            messagebox.showerror("Some errors", "\n".join(errors[:5]))
        else:
            result_msg = f"{len(paths)} file(s) moved to Trash."
            if pdf_path and os.path.exists(pdf_path):
                result_msg += f"\n\nPDF report saved to:\n{pdf_path}"
            messagebox.showinfo("Done", result_msg)

        # ── 5. Open PDF then rescan ──
        if pdf_path and os.path.exists(pdf_path):
            subprocess.run(["open", pdf_path])

        # Clear tree immediately so it feels responsive
        self._tree.delete(*self._tree.get_children())
        self._dupes = {}
        self._start_scan()

if __name__ == "__main__":
    app = DuplicateFinderApp()
    app.mainloop()
