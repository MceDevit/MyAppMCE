[README.md](https://github.com/user-attachments/files/27206298/README.md)
# Duplicate File Finder

A macOS desktop app for finding and safely removing duplicate files from any folder. Built with Python and tkinter.

---

## What it does

Scans a folder (and all its subfolders) to identify duplicate files, displays them grouped with colour-coded roles, and lets you move unwanted copies to the macOS Trash — with an optional PDF deletion report.

---

## How to run

```bash
# Install the only external dependency
pip3 install reportlab

# Run the app
python3 duplicate_finder.py
```

Requires Python 3.10+ (uses the walrus operator `:=`).

---

## How it works

### 1. Folder selection
Choose any folder via the Browse button or type the path directly. The app stores the real filesystem path internally, which matters for paths that may contain aliases or display-name shortcuts.

### 2. Search modes

| Mode | How it works |
|---|---|
| **File content (hash)** | Two-stage hashing — fast for large folders |
| **File name** | Groups files that share the same filename, regardless of content |

**Two-stage hashing (content mode):**
- **Stage 1 — quick hash:** reads only the first 64 KB of each file using BLAKE2b. This quickly eliminates the vast majority of non-duplicates without reading whole files.
- **Stage 2 — full hash:** only files that matched on size *and* quick hash are fully hashed. This confirms true duplicates with certainty.

Temporary and hidden files are automatically skipped (`.tmp`, `.bak`, `~$` lock files, dot-files, etc.).

### 3. Results display

Duplicates are shown in a grouped tree view:

- **KEEP** (blue) — the first file found in each group; treated as the original to keep
- **DELETE** (yellow) — the remaining copies, pre-selected for removal

You can click the **Role** column on any row to promote it to KEEP — useful when you want to keep a copy in a specific location.

### 4. Moving to Trash

Selected files are moved to the macOS Trash using AppleScript (`osascript`), which gives you the native Trash experience and the ability to restore files if needed. If AppleScript fails (e.g. on an external volume), the app falls back to moving the file to the volume's `.Trashes` folder directly.

The UI stays responsive during deletion — a background thread handles the file operations and reports progress back to the main thread.

### 5. PDF report

If the **Generate PDF report** option is checked, a timestamped PDF is saved to your Desktop after each deletion. The report lists every group with its kept original and all deleted copies, including file paths. It requires the `reportlab` library.

---

## Key files and structure

```
duplicate_finder.py       # Single-file app — everything is here
```

| Section | What it contains |
|---|---|
| Colour palette / fonts | UI theme constants (dark, orange accent) |
| `generate_pdf_report()` | Builds the landscape A4 PDF using reportlab |
| `file_hash()` / `file_quick_hash()` | BLAKE2b hashing functions |
| `find_duplicates()` | Two-stage content scan (runs in a thread) |
| `find_duplicates_by_name()` | Name-based scan (runs in a thread) |
| `DuplicateFinderApp` | Main tkinter window and all UI logic |

---

## Dependencies

| Package | Purpose | Required? |
|---|---|---|
| `tkinter` | GUI framework | Yes (bundled with Python) |
| `hashlib` | BLAKE2b hashing | Yes (stdlib) |
| `reportlab` | PDF report generation | Optional — app works without it |

---

## Platform notes

- Designed for **macOS** — uses AppleScript for Trash integration and SF Pro fonts.
- The Finder integration (`open -R`) for "Reveal in Finder" is also macOS-specific.
- The core scanning logic (hashing, walking directories) is cross-platform and would work on Linux/Windows with minor UI adjustments.
