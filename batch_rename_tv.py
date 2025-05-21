import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import logging
import json
from pathlib import Path
import winreg

# Optional: requires 'ttkthemes' package (pip install ttkthemes)
try:
    from ttkthemes import ThemedStyle
    has_ttkthemes = True
except ImportError:
    has_ttkthemes = False

# Logging setup
tk_logger = logging.getLogger('BatchRenamer')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

HISTORY_FILE = Path.home() / ".batch_renamer_history.json"

def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except:
            pass
    return {"title": [], "year": [], "season": [], "episode": []}

def save_history(hist):
    try:
        HISTORY_FILE.write_text(json.dumps(hist, indent=2))
    except Exception as e:
        tk_logger.error(f"Failed saving history: {e}")

# Detect Windows app theme (Light=1 or Dark=0)
def windows_use_light():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        val = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        return bool(val)
    except:
        return True

class BatchRenamer:
    def __init__(self, master):
        self.master = master
        self.folder = None
        self.files = []

        # Setup styling
        if has_ttkthemes:
            style = ThemedStyle(master)
            theme = 'equilux' if not windows_use_light() else 'arc'
            style.set_theme(theme)
        else:
            style = ttk.Style(master)
            # fallback to native
            for t in ('vista','winnative'):
                if t in style.theme_names():
                    style.theme_use(t)
                    break

        self._build_gui()

    def _build_gui(self):
        self.master.title("Batch File Renamer")
        main = ttk.Frame(self.master)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_open = ttk.Button(main, text="Select Folder", command=self._choose_folder)
        btn_open.grid(row=0, column=0, sticky=tk.W)

        self.lbl_folder = ttk.Label(main, text="No folder selected")
        self.lbl_folder.grid(row=0, column=1, sticky=tk.W, padx=5)

        self.tree = ttk.Treeview(main, columns=("file",), show='headings', height=12)
        self.tree.heading("file", text="File Name")
        self.tree.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, pady=(5,10))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        btn_rename = ttk.Button(main, text="Rename Files", command=self._start_rename_thread)
        btn_rename.grid(row=2, column=0, columnspan=2)

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        exts = {'.mp4','.mkv','.avi','.mov','.flv','.wmv','.m4v'}
        files = sorted([f for f in os.listdir(folder)
                        if os.path.isfile(os.path.join(folder,f))
                        and os.path.splitext(f)[1].lower() in exts])
        if not files:
            messagebox.showwarning("No Media Files",
                                   "No media files found in folder.")
            return
        self.folder = folder
        self.files = files
        self.lbl_folder.config(text=folder)
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for f in files:
            self.tree.insert('', tk.END, values=(f,))

    def _start_rename_thread(self):
        if not self.files:
            messagebox.showwarning("No Files", "Please select a folder first.")
            return
        details = self._prompt_details()
        if details is None:
            tk_logger.debug("Rename cancelled by user")
            return
        threading.Thread(target=self._rename, args=(details,), daemon=True).start()

    def _prompt_details(self):
        hist = load_history()
        dlg = tk.Toplevel(self.master)
        dlg.title("Rename Setup")

        fields = ['title','year','season','episode']
        labels = ["Show Title","Year","Start Season","Start Episode"]
        combos = {}
        defaults = [hist[k][-1] if hist[k] else '' for k in fields]
        for i, (lbl, field) in enumerate(zip(labels, fields)):
            ttk.Label(dlg, text=lbl+":").grid(row=i, column=0, padx=5, pady=5, sticky=tk.E)
            cb = ttk.Combobox(dlg, values=[str(x) for x in hist[field]])
            cb.grid(row=i, column=1, padx=5, pady=5)
            cb.set(defaults[i])
            combos[field] = cb

        result = {}
        cancelled = {'flag': False}

        def on_ok():
            try:
                result['title'] = combos['title'].get().strip()
                result['year'] = combos['year'].get().strip()
                result['season'] = int(combos['season'].get().strip() or 1)
                result['episode'] = int(combos['episode'].get().strip() or 1)
            except Exception:
                messagebox.showerror("Input Error", "Please enter valid values.")
                return
            for k in fields:
                v = result[k]
                lst = hist[k]
                if v not in lst:
                    lst.append(v)
                    if len(lst) > 20: lst.pop(0)
            save_history(hist)
            dlg.destroy()

        def on_cancel():
            cancelled['flag'] = True
            dlg.destroy()

        btn_ok = ttk.Button(dlg, text="OK", command=on_ok)
        btn_ok.grid(row=len(fields), column=0, pady=10)
        btn_cancel = ttk.Button(dlg, text="Cancel", command=on_cancel)
        btn_cancel.grid(row=len(fields), column=1, pady=10)
        dlg.protocol("WM_DELETE_WINDOW", on_cancel)
        dlg.grab_set()
        dlg.wait_window()

        if cancelled['flag'] or not result:
            return None
        return result

    def _rename(self, details):
        ep = details['episode']
        errs = []
        for old in self.files:
            base, ext = os.path.splitext(old)
            new = f"{details['title']} ({details['year']}) - S{details['season']:02d}E{ep:02d}{ext}"
            try:
                os.rename(os.path.join(self.folder, old), os.path.join(self.folder, new))
                ep+=1
            except Exception as e:
                errs.append(f"{old}: {e}")
        try: os.startfile(self.folder)
        except: pass
        if errs:
            messagebox.showwarning("Errors", "\n".join(errs))
        else:
            messagebox.showinfo("Done", "Renamed and opened folder!")

if __name__=='__main__':
    root=tk.Tk()
    BatchRenamer(root)
    root.mainloop()