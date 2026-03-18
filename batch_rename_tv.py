import os
import sys
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import logging
import json
from pathlib import Path
from typing import Optional

# Windows-only registry access
try:
    import winreg
    has_winreg = True
except ImportError:
    has_winreg = False

# Optional: requires 'ttkthemes' package (pip install ttkthemes)
try:
    from ttkthemes import ThemedStyle
    has_ttkthemes = True
except ImportError:
    has_ttkthemes = False

# Optional: requires 'tkinterdnd2' package (pip install tkinterdnd2)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    has_dnd = True
except ImportError:
    has_dnd = False

# Logging setup
tk_logger = logging.getLogger('BatchRenamer')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

HISTORY_FILE = Path.home() / ".batch_renamer_history.json"
MEDIA_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v'}
MAX_HISTORY = 20


def load_history() -> dict:
    """Load input history from disk, returning empty defaults on any failure."""
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError, ValueError) as e:
            tk_logger.warning(f"Could not load history file: {e}")
    return {"title": [], "year": [], "season": [], "episode": []}


def save_history(hist: dict) -> None:
    """Persist input history to disk."""
    try:
        HISTORY_FILE.write_text(json.dumps(hist, indent=2), encoding='utf-8')
    except OSError as e:
        tk_logger.error(f"Failed saving history: {e}")


def windows_use_light() -> bool:
    """Return True if Windows is set to light theme, False for dark. Defaults to True."""
    if not has_winreg:
        return True
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        return bool(val)
    except OSError:
        return True


def validate_inputs(title: str, year: str, season: str, episode: str) -> Optional[str]:
    """
    Validate rename dialog inputs.
    Returns an error message string on failure, or None if all inputs are valid.
    """
    if not title:
        return "Show title cannot be empty."
    if not year.isdigit() or len(year) != 4:
        return "Year must be a 4-digit number (e.g. 2008)."
    try:
        if int(season) < 1:
            raise ValueError
    except ValueError:
        return "Season must be a positive integer."
    try:
        if int(episode) < 1:
            raise ValueError
    except ValueError:
        return "Episode must be a positive integer."
    return None


def build_rename_plan(
    files: list,
    title: str,
    year: str,
    season: int,
    episode: int,
) -> list:
    """
    Build a list of (old_name, new_name) pairs without performing any renames.
    Raises ValueError if any target filename would collide with another.
    """
    plan = []
    ep = episode
    targets: set = set()
    for old in files:
        ext = Path(old).suffix
        new = f"{title} ({year}) - S{season:02d}E{ep:02d}{ext}"
        if new in targets:
            raise ValueError(f"Duplicate target filename: {new}")
        targets.add(new)
        plan.append((old, new))
        ep += 1
    return plan


def open_folder(folder: str) -> None:
    """Open the given folder in the system file manager without shell injection risk."""
    try:
        if os.name == 'nt':
            os.startfile(folder)  # Safe on Windows; no shell involved
        elif sys.platform == 'darwin':
            subprocess.run(['open', folder], check=False)
        else:
            subprocess.run(['xdg-open', folder], check=False)
    except OSError as e:
        tk_logger.warning(f"Could not open folder '{folder}': {e}")


class BatchRenamer:
    """Main application window for batch renaming TV episode files."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.folder: Optional[str] = None
        self.files: list = []
        self._rename_queue: queue.Queue = queue.Queue()
        self._setup_style()
        self._build_gui()
        self._poll_rename_queue()

    def _setup_style(self) -> None:
        """Apply platform-appropriate theme."""
        if has_ttkthemes:
            style = ThemedStyle(self.master)
            theme = 'equilux' if not windows_use_light() else 'arc'
            style.set_theme(theme)
        else:
            style = ttk.Style(self.master)
            for t in ('vista', 'winnative'):
                if t in style.theme_names():
                    style.theme_use(t)
                    break

    def _build_gui(self) -> None:
        """Construct all widgets."""
        self.master.title("Batch File Renamer")
        main = ttk.Frame(self.master)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_open = ttk.Button(main, text="Select Folder", command=self._choose_folder)
        btn_open.grid(row=0, column=0, sticky=tk.W)

        self.lbl_folder = ttk.Label(main, text="No folder selected")
        self.lbl_folder.grid(row=0, column=1, sticky=tk.W, padx=5)

        self.tree = ttk.Treeview(main, columns=("file",), show='headings', height=12)
        self.tree.heading("file", text="File Name")
        self.tree.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, pady=(5, 5))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        # Progress bar — hidden until a rename is running
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(0, 3))
        self.progress.grid_remove()

        self.lbl_status = ttk.Label(main, text="")
        self.lbl_status.grid(row=3, column=0, columnspan=2, sticky=tk.W)

        if has_dnd:
            self.tree.drop_target_register(DND_FILES)
            self.tree.dnd_bind('<<Drop>>', self._on_drop)

        self.btn_rename = ttk.Button(main, text="Rename Files", command=self._start_rename_thread)
        self.btn_rename.grid(row=4, column=0, columnspan=2, pady=(5, 0))

    def _choose_folder(self) -> None:
        """Open a folder picker dialog."""
        folder = filedialog.askdirectory()
        if folder:
            self._load_files_from_folder(folder)

    def _load_files_from_folder(self, folder: str) -> None:
        """Scan folder for media files and populate the tree view."""
        try:
            folder_path = Path(folder)
            files = sorted(
                f.name for f in folder_path.iterdir()
                if not f.name.startswith('.')
                and f.is_file()
                and f.suffix.lower() in MEDIA_EXTS
            )
        except OSError as e:
            messagebox.showerror("Folder Error", f"Cannot read folder:\n{e.strerror}")
            return

        if not files:
            messagebox.showwarning(
                "No Media Files",
                "No supported media files found in the selected folder.\n\n"
                f"Supported formats: {', '.join(sorted(MEDIA_EXTS))}"
            )
            return

        self.folder = folder
        self.files = files
        self.lbl_folder.config(text=folder)
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for f in files:
            self.tree.insert('', tk.END, values=(f,))
        self.lbl_status.config(text=f"{len(files)} file(s) loaded.")

    def _on_drop(self, event) -> None:
        """Handle drag-and-drop of a folder onto the file list."""
        paths = self.master.splitlist(event.data)
        folders = [p for p in paths if os.path.isdir(p)]
        if not folders:
            messagebox.showwarning("Drop Error", "Please drop a folder, not individual files.")
            return
        if len(folders) > 1:
            messagebox.showinfo("Multiple Folders", "Only the first dropped folder will be loaded.")
        self._load_files_from_folder(folders[0])

    def _start_rename_thread(self) -> None:
        """Validate selection, show preview, then start background rename."""
        if not self.files:
            messagebox.showwarning("No Files", "Please select a folder with media files first.")
            return

        details = self._prompt_details()
        if details is None:
            return

        try:
            plan = build_rename_plan(
                self.files,
                details['title'], details['year'],
                details['season'], details['episode'],
            )
        except ValueError as e:
            messagebox.showerror("Rename Error", str(e))
            return

        if not self._show_preview(plan):
            return

        self._set_rename_ui_state(running=True)
        threading.Thread(target=self._rename, args=(plan,), daemon=True).start()

    def _show_preview(self, plan: list) -> bool:
        """
        Show a dialog listing old → new filenames for user confirmation.
        Returns True if the user confirms, False if they cancel.
        """
        dlg = tk.Toplevel(self.master)
        dlg.title("Preview Renames")
        dlg.grab_set()

        ttk.Label(dlg, text="The following files will be renamed:").pack(padx=10, pady=(10, 5))

        cols = ("Before", "After")
        tree = ttk.Treeview(dlg, columns=cols, show='headings', height=min(len(plan), 15))
        tree.heading("Before", text="Before")
        tree.heading("After", text="After")
        tree.column("Before", width=300)
        tree.column("After", width=300)
        for old, new in plan:
            tree.insert('', tk.END, values=(old, new))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        confirmed = {'value': False}

        def on_confirm():
            confirmed['value'] = True
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Rename", command=on_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.wait_window()
        return confirmed['value']

    def _prompt_details(self) -> Optional[dict]:
        """
        Show a dialog for show title, year, season, and episode input.
        Returns a dict of validated values, or None if cancelled.
        """
        hist = load_history()
        dlg = tk.Toplevel(self.master)
        dlg.title("Rename Setup")
        dlg.resizable(False, False)

        fields = ['title', 'year', 'season', 'episode']
        labels = ["Show Title", "Year", "Start Season", "Start Episode"]
        combos: dict = {}
        defaults = [hist[k][-1] if hist[k] else '' for k in fields]

        for i, (lbl, field) in enumerate(zip(labels, fields)):
            ttk.Label(dlg, text=lbl + ":").grid(row=i, column=0, padx=5, pady=5, sticky=tk.E)
            cb = ttk.Combobox(dlg, values=[str(x) for x in hist[field]])
            cb.grid(row=i, column=1, padx=5, pady=5)
            cb.set(defaults[i])
            combos[field] = cb

        result: dict = {}
        cancelled = {'flag': False}

        def on_ok():
            title = combos['title'].get().strip()
            year = combos['year'].get().strip()
            season_str = combos['season'].get().strip() or '1'
            episode_str = combos['episode'].get().strip() or '1'

            err = validate_inputs(title, year, season_str, episode_str)
            if err:
                messagebox.showerror("Input Error", err, parent=dlg)
                return

            result['title'] = title
            result['year'] = year
            result['season'] = int(season_str)
            result['episode'] = int(episode_str)

            for k in fields:
                v = str(result[k])
                lst = hist[k]
                if v not in lst:
                    lst.append(v)
                    if len(lst) > MAX_HISTORY:
                        lst.pop(0)
            save_history(hist)
            dlg.destroy()

        def on_cancel():
            cancelled['flag'] = True
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        dlg.protocol("WM_DELETE_WINDOW", on_cancel)
        dlg.grab_set()
        dlg.wait_window()

        if cancelled['flag'] or not result:
            return None
        return result

    def _set_rename_ui_state(self, running: bool) -> None:
        """Toggle progress bar and rename button for the duration of a rename."""
        if running:
            self.btn_rename.config(state=tk.DISABLED)
            self.progress.grid()
            self.progress['value'] = 0
            self.lbl_status.config(text="Renaming…")
        else:
            self.btn_rename.config(state=tk.NORMAL)
            self.progress.grid_remove()

    def _poll_rename_queue(self) -> None:
        """Drain the inter-thread queue on the main thread via after()."""
        try:
            while True:
                msg = self._rename_queue.get_nowait()
                self._handle_rename_message(msg)
        except queue.Empty:
            pass
        self.master.after(100, self._poll_rename_queue)

    def _handle_rename_message(self, msg: dict) -> None:
        """Process a message from the rename worker thread (always called on main thread)."""
        kind = msg.get('type')
        if kind == 'progress':
            self.progress['value'] = msg['value']
            self.lbl_status.config(text=msg.get('text', ''))
        elif kind == 'done':
            self._set_rename_ui_state(running=False)
            errors: list = msg.get('errors', [])
            completed: list = msg.get('completed', [])
            if errors:
                err_text = "\n".join(errors)
                if completed:
                    if messagebox.askyesno(
                        "Partial Failure",
                        f"Some files could not be renamed:\n{err_text}\n\n"
                        f"Roll back the {len(completed)} successful rename(s)?"
                    ):
                        self._rollback(completed)
                        self.lbl_status.config(text="Rolled back.")
                        return
                else:
                    messagebox.showerror("Rename Failed", f"No files were renamed:\n{err_text}")
            else:
                self.lbl_status.config(text=f"Renamed {len(completed)} file(s).")
                open_folder(self.folder)
            self._load_files_from_folder(self.folder)

    def _rollback(self, completed: list) -> None:
        """Undo completed renames in reverse order."""
        for old, new in reversed(completed):
            src = Path(self.folder) / new
            dst = Path(self.folder) / old
            try:
                src.rename(dst)
                tk_logger.debug(f"Rolled back: {new} -> {old}")
            except OSError as e:
                tk_logger.error(f"Rollback failed for '{new}': {e}")
        self._load_files_from_folder(self.folder)

    def _rename(self, plan: list) -> None:
        """Worker thread: rename files per plan, sending progress via queue."""
        completed: list = []
        errors: list = []
        total = len(plan)

        for i, (old, new) in enumerate(plan, start=1):
            src = Path(self.folder) / old
            dst = Path(self.folder) / new
            try:
                src.rename(dst)
                completed.append((old, new))
                tk_logger.debug(f"Renamed: {old!r} -> {new!r}")
            except OSError as e:
                errors.append(f'"{old}" — {e.strerror}')
                tk_logger.error(f"Rename failed for '{old}': {e}")

            self._rename_queue.put({
                'type': 'progress',
                'value': int(i / total * 100),
                'text': f"Renamed {i} of {total}…",
            })

        self._rename_queue.put({
            'type': 'done',
            'completed': completed,
            'errors': errors,
        })


if __name__ == '__main__':
    if has_dnd:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    BatchRenamer(root)
    root.mainloop()
