# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Two standalone macOS desktop apps written in Python + Tkinter. There is no build step, no test suite, no package manifest — each script is run directly.

- `duplicate_finder.py` — scans a folder for duplicate files (by content hash) and lets the user move duplicates to the Trash.
- `folder_diff.py` — compares two folders, shows files unique to each side and files with differing content, and copies selected files between them.

## Running

```bash
python3 duplicate_finder.py
python3 folder_diff.py
```

Both apps depend on `reportlab` for the PDF report feature:

```bash
pip3 install reportlab
```

## Versioning

The window title carries a manually-bumped version (e.g. `"Duplicate Finder v5"`, `"Folder Differences v2"`). Bump the version in `self.title(...)` inside `__init__` whenever a behavior change ships. There is no CHANGELOG — git history is the source of truth.

## Architecture (shared patterns)

Both apps follow the same shape: a single `tk.Tk` subclass that builds the UI, runs work on a background thread, and marshals results back to the main thread via `self.after(0, ...)`. The scan/compare core lives in module-level functions outside the UI class.

The codebase has been hardened against UI freezes with large file sets (1000+ files). When making changes, preserve these patterns:

### 1. Two-stage content hashing

`file_hash` (full BLAKE2b, 1 MB read buffer) and `file_quick_hash` (BLAKE2b of first 64 KB) are used in tandem:

- **duplicate_finder**: group by size → quick-hash collision → full-hash collision.
- **folder_diff**: size mismatch → quick-hash mismatch → full-hash mismatch.

This avoids fully reading files that are obviously different. Do not switch back to SHA-256 or single-stage hashing — duplicate detection does not need cryptographic strength and full-file hashing is the bottleneck on large folders.

### 2. Background threads for slow operations

Scanning, comparing, copying files, and moving files to Trash all run on a `threading.Thread`. The trash-move loop in particular makes one synchronous `osascript` call per file (~300ms each); on the main thread it freezes the UI for minutes. Always use `self.after(0, lambda: ...)` to update tkinter widgets from worker threads.

### 3. Batched tree rendering and selection

`ttk.Treeview` becomes unresponsive when you insert or select thousands of rows in one call. Both apps use the pattern:

```python
def _insert_rows_batch(self, rows, start, chunk=100):
    end = min(start + chunk, len(rows))
    for tag, values in rows[start:end]:
        self._tree.insert("", "end", values=values, tags=(tag,))
    if end < len(rows):
        self._progress_label.config(text=f"Loading… {end} / {len(rows)}")
        self.update_idletasks()
        self.after(1, lambda: self._insert_rows_batch(rows, end, chunk))
```

Same shape for `_batch_select`. Set the progress label **before** scheduling the next batch and call `update_idletasks()` so the label actually paints.

### 4. iid → data caches

Calling `self._tree.item(iid, "values")` for thousands of rows is slow (each call is a tkinter roundtrip). Both apps maintain caches populated during insertion:

- `duplicate_finder`: `self._delete_iids` (list) and `self._iid_path` (dict).
- `folder_diff`: `self._selectable_iids` (list) and `self._iid_data` (dict).

Selection lookups (`_get_selected_paths`, `_get_selected_items`) read from these caches instead of querying the tree. When you add a new row type or change the row schema, update both the cache write (in `_insert_rows_batch`) and the cache reader.

### 5. Throttled progress callbacks

Scan/compare workers call `progress_cb` only every ~25 files (and once at completion), not per file. Without throttling, thousands of `self.after(0, ...)` callbacks queue up and the UI lags behind the actual work.

## Color convention

Both apps share a deliberate palette:

- **Blue** (`#2979ff`) — Folder 1 in folder_diff; "keep" / source rows in duplicate_finder.
- **Yellow** (`#ffd600`) — Folder 2 in folder_diff; "delete" / duplicate rows in duplicate_finder.
- **Orange** (`#ff6d00`, `ACCENT`) — neutral UI chrome (primary buttons, progress bar, section headers, totals). Never a per-folder/per-role color.
- **Red** (`#ff1744`, `DANGER`) — destructive actions (Move to Trash).

When adding UI elements, color folder/role-specific things with blue/yellow and neutral chrome with orange. Do not reintroduce the old yellow `ACCENT` — yellow is reserved for folder 2 / delete rows.

## PDF reports

Both apps generate landscape A4 PDF reports to `~/Desktop/` after a destructive/copy action, gated by a checkbox (default on). The PDF generator is a single `generate_pdf_report(...)` function near the top of each file using `reportlab.platypus`. It registers Vera fonts from reportlab's bundled fonts directory.
