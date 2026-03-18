# Batch File Renamer

A simple, self-contained Python desktop application for batch renaming video files.

## Description

Batch File Renamer provides an intuitive graphical interface to:

* **Browse & select** a folder containing your media files (MP4, MKV, AVI, MOV, FLV, WMV, M4V).
* **Auto-detect** only supported video formats, filtering out other files.
* **Prompt** for show details — Show Title, Release Year, Start Season & Episode — with dropdown history of previous inputs.
* **Preview** the full before/after list of renames before committing.
* **Sequentially rename** all files to the format:

  ```text
  <Show Title> (YYYY) - SXXEYY.ext
  ```

* **Roll back** automatically if a partial failure occurs mid-batch.
* **Open the target folder** automatically upon successful completion.
* **Follow your Windows theme** (light/dark) using native or `ttkthemes` styling.

All rename operations run on a background thread to keep the interface responsive, with a live progress bar and detailed debug logging.

## Features

* **Media-only file listing** prevents accidental renames of non-video files.
* **Rename preview dialog** shows every old → new mapping before any file is touched.
* **Rollback on partial failure** — if any rename fails mid-batch, you are offered the option to undo all completed renames.
* **Input validation** — title, year (must be 4 digits), season, and episode are all validated before proceeding.
* **Input history** up to 20 entries per field for quick autofill.
* **Progress bar** with per-file status updates; Rename button is disabled during operation to prevent concurrent runs.
* **Cross-platform compatibility** (Windows, macOS, Linux) with native theming where available.
  * On Windows, detects system dark mode via registry and applies a dark theme if `ttkthemes` is installed.
* **Drag-and-drop support** (optional, requires `tkinterdnd2`).
* **Error feedback** via pop-up dialogs with user-friendly messages.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/EthanCostello/batch-file-renamer.git
   cd batch-file-renamer
   ```

2. **Create a virtual environment (optional but recommended):**

   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate      # Windows
   ```

3. **Install optional dependencies** (core app requires only the Python standard library):

   ```bash
   pip install ttkthemes    # Enhanced dark/light theme support
   pip install tkinterdnd2  # Drag-and-drop folder support
   ```

   > `tkinter` is included with standard Python distributions and does not need a separate install.

## Usage

Run the application:

```bash
python batch_rename_tv.py
```

1. Click **Select Folder** (or drag a folder onto the file list) to choose your video directory.
2. Click **Rename Files**.
3. In the dialog, fill in Show Title, Year, Start Season, and Start Episode (auto-filled from history).
4. Click **OK** to see a preview of all renames.
5. In the preview dialog, click **Rename** to commit or **Cancel** to go back.
6. Upon completion the folder opens automatically, or you are offered a rollback if any errors occurred.

## Configuration

* **Supported Extensions:** Edit the `MEDIA_EXTS` set near the top of `batch_rename_tv.py` to add or remove video formats.
* **History File:** `~/.batch_renamer_history.json` stores the last 20 inputs per field (excluded from version control via `.gitignore`).
* **History Limit:** Adjust `MAX_HISTORY` in `batch_rename_tv.py` to change how many entries are remembered.

## Building a Standalone Executable

You can package the app as a single executable using [PyInstaller](https://pyinstaller.org/).
The output format depends on the OS you build on:

| Build OS | Output |
|---|---|
| Windows | `dist\BatchRenamer.exe` |
| macOS | `dist/BatchRenamer` |
| Linux | `dist/BatchRenamer` |

**Steps:**

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Build:
   ```bash
   pyinstaller batch_rename_tv.spec --clean
   ```

3. The executable is at `dist/BatchRenamer` (or `dist\BatchRenamer.exe` on Windows).
   Copy it anywhere — no Python installation required on the target machine.

> **Optional icon:** Place a `icon.ico` file in the project root before building on Windows
> and the exe will use it as its icon.

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Cross-platform Support

Batch File Renamer is written in pure Python with Tkinter/ttk, so it runs on **Windows, macOS, and Linux**.

* On **Windows**, uses `os.startfile` to open the folder.
* On **macOS**, runs `open <folder>` via subprocess to reveal files in Finder.
* On **Linux**, uses `xdg-open <folder>` to open the default file manager.

Folder-open commands use `subprocess.run` with argument lists (not shell strings) to avoid shell injection issues.

## License

This project is released under the [MIT License](LICENSE).

---

Happy renaming!
