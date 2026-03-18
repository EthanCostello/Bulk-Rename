import os
import sys
import queue
import threading
import subprocess
import logging
import json
from pathlib import Path
from typing import Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk

# Windows-only registry access
try:
    import winreg
    has_winreg = True
except ImportError:
    has_winreg = False

# Follow the OS light/dark preference
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

tk_logger = logging.getLogger('BatchRenamer')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

HISTORY_FILE = Path.home() / ".batch_renamer_history.json"
MEDIA_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v'}
MAX_HISTORY = 20


# ---------------------------------------------------------------------------
# Pure helper functions (no GUI dependencies)
# ---------------------------------------------------------------------------

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
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.run(['open', folder], check=False)
        else:
            subprocess.run(['xdg-open', folder], check=False)
    except OSError as e:
        tk_logger.warning(f"Could not open folder '{folder}': {e}")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class BatchRenamer(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Batch File Renamer")
        self.geometry("740x620")
        self.minsize(560, 480)

        self.folder: Optional[str] = None
        self.files: list = []
        self._rename_queue: queue.Queue = queue.Queue()
        self._file_rows: list = []

        self._build_gui()
        self._poll_rename_queue()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_gui(self) -> None:
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_folder_card()
        self._build_file_list()
        self._build_bottom_bar()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 6))

        ctk.CTkLabel(
            header,
            text="Batch File Renamer",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Rename TV episodes to a standard format in seconds",
            font=ctk.CTkFont(size=13),
            text_color=("gray45", "gray65"),
        ).pack(anchor="w")

    def _build_folder_card(self) -> None:
        card = ctk.CTkFrame(self)
        card.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="FOLDER",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray45", "gray65"),
        ).grid(row=0, column=0, padx=(16, 8), pady=14, sticky="w")

        self.lbl_folder = ctk.CTkLabel(
            card,
            text="No folder selected",
            font=ctk.CTkFont(size=13),
            text_color=("gray45", "gray65"),
            anchor="w",
        )
        self.lbl_folder.grid(row=0, column=1, sticky="ew", padx=4)

        ctk.CTkButton(
            card,
            text="Browse",
            width=90,
            height=32,
            command=self._choose_folder,
        ).grid(row=0, column=2, padx=(8, 16), pady=14)

    def _build_file_list(self) -> None:
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 6))
        section.grid_rowconfigure(1, weight=1)
        section.grid_columnconfigure(0, weight=1)

        self.lbl_count = ctk.CTkLabel(
            section,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray65"),
        )
        self.lbl_count.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.file_list = ctk.CTkScrollableFrame(section)
        self.file_list.grid(row=1, column=0, sticky="nsew")
        self.file_list.grid_columnconfigure(0, weight=1)

        self._placeholder = ctk.CTkLabel(
            self.file_list,
            text="Select a folder to see your media files here",
            font=ctk.CTkFont(size=13),
            text_color=("gray45", "gray65"),
        )
        self._placeholder.grid(row=0, column=0, pady=50, padx=20)

    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(6, 22))
        bar.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(bar)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.progress.grid_remove()

        self.lbl_status = ctk.CTkLabel(
            bar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray65"),
        )
        self.lbl_status.grid(row=1, column=0, sticky="w")

        self.btn_rename = ctk.CTkButton(
            bar,
            text="Rename Files  →",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=160,
            command=self._start_rename_thread,
        )
        self.btn_rename.grid(row=1, column=1)

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self._load_files_from_folder(folder)

    def _load_files_from_folder(self, folder: str) -> None:
        try:
            files = sorted(
                f.name for f in Path(folder).iterdir()
                if not f.name.startswith('.')
                and f.is_file()
                and f.suffix.lower() in MEDIA_EXTS
            )
        except OSError as e:
            messagebox.showerror("Folder Error", f"Cannot read folder:\n{e.strerror}", parent=self)
            return

        if not files:
            messagebox.showwarning(
                "No Media Files",
                f"No supported media files found in the selected folder.\n\n"
                f"Supported formats: {', '.join(sorted(MEDIA_EXTS))}",
                parent=self,
            )
            return

        self.folder = folder
        self.files = files

        display = folder if len(folder) <= 62 else "…" + folder[-59:]
        self.lbl_folder.configure(text=display, text_color=("gray10", "gray90"))

        for row in self._file_rows:
            row.destroy()
        self._file_rows.clear()
        self._placeholder.grid_remove()

        for i, filename in enumerate(files):
            row = ctk.CTkFrame(
                self.file_list,
                fg_color=("gray91", "gray18") if i % 2 == 0 else "transparent",
                corner_radius=6,
            )
            row.grid(row=i, column=0, sticky="ew", padx=2, pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                row, text="🎬", width=30, font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, padx=(10, 4), pady=6)
            ctk.CTkLabel(
                row, text=filename, anchor="w", font=ctk.CTkFont(size=13),
            ).grid(row=0, column=1, sticky="ew", padx=(0, 10))
            self._file_rows.append(row)

        n = len(files)
        self.lbl_count.configure(
            text=f"{n} file{'s' if n != 1 else ''} found",
            text_color=("gray30", "gray70"),
        )
        self.lbl_status.configure(text="")

    # ------------------------------------------------------------------
    # Rename flow
    # ------------------------------------------------------------------

    def _start_rename_thread(self) -> None:
        if not self.files:
            messagebox.showwarning("No Files", "Please select a folder with media files first.", parent=self)
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
            messagebox.showerror("Rename Error", str(e), parent=self)
            return

        if not self._show_preview(plan):
            return

        self._set_rename_ui_state(running=True)
        threading.Thread(target=self._rename, args=(plan,), daemon=True).start()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _prompt_details(self) -> Optional[dict]:
        """Show show-details dialog. Returns validated dict or None if cancelled."""
        hist = load_history()

        dlg = ctk.CTkToplevel(self)
        dlg.title("Rename Setup")
        dlg.geometry("400x330")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            dlg,
            text="Show Details",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(18, 14), sticky="w")

        fields = ['title', 'year', 'season', 'episode']
        labels = ["Show Title", "Year", "Start Season", "Start Episode"]
        combos: dict = {}
        defaults = [hist[k][-1] if hist[k] else '' for k in fields]

        for i, (lbl, field) in enumerate(zip(labels, fields), start=1):
            ctk.CTkLabel(dlg, text=lbl, font=ctk.CTkFont(size=13), anchor="w").grid(
                row=i, column=0, padx=(20, 10), pady=6, sticky="w",
            )
            cb = ctk.CTkComboBox(dlg, values=[str(x) for x in hist[field]], width=190)
            cb.set(defaults[i - 1])
            cb.grid(row=i, column=1, padx=(0, 20), pady=6, sticky="ew")
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

            result.update({
                'title': title,
                'year': year,
                'season': int(season_str),
                'episode': int(episode_str),
            })
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

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="ew", padx=20, pady=(14, 20))
        btn_row.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_row, text="Cancel", width=90, height=34,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            command=on_cancel,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            btn_row, text="Continue  →", width=120, height=34,
            font=ctk.CTkFont(weight="bold"),
            command=on_ok,
        ).grid(row=0, column=2, padx=(8, 0))

        dlg.protocol("WM_DELETE_WINDOW", on_cancel)
        dlg.wait_window()

        return None if (cancelled['flag'] or not result) else result

    def _show_preview(self, plan: list) -> bool:
        """Show before/after preview dialog. Returns True if user confirms."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Preview Renames")
        dlg.geometry("740x480")
        dlg.grab_set()
        dlg.grid_rowconfigure(1, weight=1)
        dlg.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(dlg, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            hdr,
            text=f"Review {len(plan)} rename{'s' if len(plan) != 1 else ''}",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            hdr,
            text="Check the list carefully — you can roll back on failure, but it's best to review first.",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray65"),
            wraplength=680,
        ).pack(anchor="w")

        # Two-column scrollable list
        scroll = ctk.CTkScrollableFrame(dlg)
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        for col, heading in enumerate(("BEFORE", "AFTER")):
            ctk.CTkLabel(
                scroll, text=heading,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("gray45", "gray65"),
            ).grid(row=0, column=col, sticky="w", padx=10, pady=(4, 2))

        for i, (old, new) in enumerate(plan, start=1):
            bg = ("gray91", "gray18") if i % 2 == 0 else "transparent"
            for col, text in enumerate((old, new)):
                ctk.CTkLabel(
                    scroll, text=text, anchor="w",
                    font=ctk.CTkFont(size=12),
                    fg_color=bg, corner_radius=4,
                ).grid(row=i, column=col, sticky="ew", padx=(8 if col == 0 else 4, 4 if col == 0 else 8), pady=1)

        # Buttons
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
        btn_row.grid_columnconfigure(0, weight=1)

        confirmed = {'value': False}

        def on_confirm():
            confirmed['value'] = True
            dlg.destroy()

        ctk.CTkButton(
            btn_row, text="Cancel", width=90, height=34,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            command=dlg.destroy,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            btn_row, text="Rename Files  →", width=150, height=34,
            font=ctk.CTkFont(weight="bold"),
            command=on_confirm,
        ).grid(row=0, column=2, padx=(8, 0))

        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.wait_window()
        return confirmed['value']

    # ------------------------------------------------------------------
    # Rename worker + queue
    # ------------------------------------------------------------------

    def _set_rename_ui_state(self, running: bool) -> None:
        if running:
            self.btn_rename.configure(state="disabled")
            self.progress.grid()
            self.progress.set(0)
            self.lbl_status.configure(text="Renaming…")
        else:
            self.btn_rename.configure(state="normal")
            self.progress.grid_remove()

    def _poll_rename_queue(self) -> None:
        try:
            while True:
                msg = self._rename_queue.get_nowait()
                self._handle_rename_message(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_rename_queue)

    def _handle_rename_message(self, msg: dict) -> None:
        kind = msg.get('type')
        if kind == 'progress':
            self.progress.set(msg['value'] / 100)
            self.lbl_status.configure(text=msg.get('text', ''))
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
                        f"Roll back the {len(completed)} successful rename(s)?",
                        parent=self,
                    ):
                        self._rollback(completed)
                        self.lbl_status.configure(text="Rolled back.")
                        return
                else:
                    messagebox.showerror(
                        "Rename Failed", f"No files were renamed:\n{err_text}", parent=self,
                    )
            else:
                self.lbl_status.configure(text=f"✓  Renamed {len(completed)} file(s).")
                open_folder(self.folder)
            self._load_files_from_folder(self.folder)

    def _rollback(self, completed: list) -> None:
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
    app = BatchRenamer()
    app.mainloop()
