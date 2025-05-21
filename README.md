# Batch File Renamer

A simple, self-contained Python desktop application for batch renaming video files.

## Description

Batch File Renamer provides an intuitive graphical interface to:

* **Browse & select** a folder containing your media files (MP4, MKV, AVI, MOV, FLV, WMV, M4V).

* **Auto-detect** only supported video formats, filtering out other files.

* **Prompt** for show details—Show Title, Release Year, Start Season & Episode—with dropdown history of previous inputs.

* **Sequentially rename** all files to the format:

  ```text
  <Show Title> (YYYY) - SXXEYY.ext
  ```

* **Open the target folder** automatically upon completion.

* **Follow your Windows theme** (light/dark) using native or `ttkthemes` for consistent UI.

All operations run on a background thread to keep the interface responsive, with detailed debug logging for troubleshooting.

## Features

* **Media-only file listing** prevents accidental renames of non-video files.
* **Input history** up to 20 entries per field for quick autofill.
* **Cross-platform compatibility** (Windows, macOS, Linux) with native theming where available.

  * On Windows, detects system dark mode via registry and applies a dark theme if `ttkthemes` is installed.
* **Error feedback** via pop-up dialogs for missing folder, partial rename failures, or user cancellations.

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
   venv\\Scripts\\activate  # Windows
   ```
3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   * **Optional:** install `ttkthemes` for enhanced dark mode support:

     ```bash
     pip install ttkthemes
     ```

## Usage

Run the application:

```bash
python batch_rename_tv.py
```

1. Click **Select Folder** and choose your video directory.
2. Click **Rename Files**.
3. In the dialog, confirm or edit the Show Title, Year, Season, and starting Episode (auto-filled from history).
4. Click **OK** to begin renaming.
5. Upon completion, the folder will open automatically.

## Screenshots

![Folder Selection and File List](screenshots/folder_list.png)
*Figure: Only video files are listed.*

![Rename Details Dialog](screenshots/details_dialog.png)
*Figure: Enter show details with history dropdowns.*

## Configuration

* **History File:** `~/.batch_renamer_history.json` stores the last 20 inputs per field.
* **Supported Extensions:** Modify the `MEDIA_EXTS` set in the script to add/remove file types.

## Cross-platform Support

Batch File Renamer is written in pure Python with Tkinter/ttk, so it runs on **Windows, macOS, and Linux**.

* On **Windows**, the program uses `os.startfile` to open the folder.
* On **macOS**, it falls back to running `open <folder>` to reveal the files in Finder.
* On **Linux**, it uses `xdg-open <folder>` to open the default file manager.

If you encounter any platform-specific issues (e.g., folder not opening automatically), you can modify the `_rename` method in the script to suit your environment.

## License

This project is released under the [MIT License](LICENSE).

---

Happy renaming!
