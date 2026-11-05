"""FilmCrop modern desktop interface. The original GUI remains in film_gui.py."""
from pathlib import Path
from datetime import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import uuid

from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES
from film_gui import create_root
from film_engine import Options
from film_io import SUPPORTED_EXTENSIONS, read_image, detection_image
from film_crop import FORMAT_CHOICES
from film_manual import normalize_box, translate
from film_modern_export import export_one
from film_version import VERSION

BG = '#202020'
PANEL = '#262626'
FIELD = '#303030'
FG = '#e9e9e9'
MUTED = '#a6a6a6'
LINE = '#414141'


class ModernFilmApp:
    def __init__(self, root):
        self.root = root
        root.title('FilmCrop ' + VERSION + ' · Preview')
        root.geometry('1280x800')
        root.minsize(900, 580)
        root.configure(bg=BG)
        self.lang = 'zh'
        self.paths = []
        self.boxes = {}
        self.states = {}
        self.records = {}
        self.current = None
        self.preview_image = None
        self.preview_photo = None
        self.preview_rect = None
        self.drag_anchor = None
        self.drag_corner = None
        self.drag_box = None
        self.jobs = queue.Queue()
        self.stop = threading.Event()
        self.running = False
        self.outdir = tk.StringVar()
        self.format = tk.StringVar(value='auto')
        self.export = tk.StringVar(value='TIFF16')
        self.auto_rotate = tk.BooleanVar(value=True)
        self.keep_border = tk.BooleanVar(value=False)
        self.language = tk.StringVar(value='中文')
        self.status_key = 'select'
        self.status_value = None
        self.translated_widgets = []
        self._style()
        self._build()
        self.refresh_language()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.poll)

    def tr(self, key, **kwargs):
        return translate(self.lang)[key].format(**kwargs)

    def label(self, parent, key, **kwargs):
        widget = ttk.Label(parent, **kwargs)
        self.translated_widgets.append((widget, key))
        return widget

    def button(self, parent, key, command, **kwargs):
        widget = ttk.Button(parent, command=command, **kwargs)
        self.translated_widgets.append((widget, key))
        return widget

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Helvetica Neue', 12), background=BG, foreground=FG)
        style.configure('TFrame', background=BG)
        style.configure('Panel.TFrame', background=PANEL)
        style.configure('TLabel', background=BG, foreground=FG)
        style.configure('Panel.TLabel', background=PANEL, foreground=FG)
        style.configure('Muted.TLabel', background=BG, foreground=MUTED)
        style.configure('TButton', padding=(10, 7), background=FIELD, foreground=FG, borderwidth=0)
        style.map('TButton', background=[('active', '#464646'), ('disabled', '#292929')], foreground=[('disabled', '#777777')])
        style.configure('Primary.TButton', background='#e0e0e0', foreground='#171717', padding=(18, 9))
        style.map('Primary.TButton', background=[('active', '#ffffff'), ('disabled', '#555555')], foreground=[('disabled', '#999999')])
        style.configure('TCheckbutton', background=BG, foreground=FG, padding=(0, 4))
        style.map('TCheckbutton', background=[('active', BG)], foreground=[('disabled', '#777777')])
        style.configure('TCombobox', fieldbackground=FIELD, background=FIELD, foreground=FG, arrowcolor=FG, bordercolor=LINE, padding=5)
        style.map('TCombobox', fieldbackground=[('readonly', FIELD)], foreground=[('readonly', FG)])
        style.configure('TEntry', fieldbackground=FIELD, foreground=FG, bordercolor=LINE, insertcolor=FG, padding=6)
        style.configure('TSeparator', background=LINE)

    def _build(self):
        toolbar = ttk.Frame(self.root, padding=(16, 10))
        toolbar.pack(fill='x')
        self.add_button = self.button(toolbar, 'add', self.add_files)
        self.folder_button = self.button(toolbar, 'folder', self.add_folder)
        self.remove_button = self.button(toolbar, 'remove', self.remove)
        self.clear_button = self.button(toolbar, 'clear', self.clear)
        for widget in (self.add_button, self.folder_button, self.remove_button, self.clear_button):
            widget.pack(side='left', padx=(0, 6))
        self.lang_combo = ttk.Button(toolbar, text='中文 / English', command=self.change_language)
        self.lang_combo.pack(side='right')
        self.label(toolbar, 'language', style='Muted.TLabel').pack(side='right', padx=8)
        self.label(toolbar, 'drop', style='Muted.TLabel').pack(side='right', padx=18)
        ttk.Separator(self.root).pack(fill='x')
        content = ttk.Frame(self.root)
        content.pack(fill='both', expand=True)
        left = ttk.Frame(content, width=225, padding=(12, 14))
        left.pack(side='left', fill='y'); left.pack_propagate(False)
        self.files_label = self.label(left, 'files')
        self.files_label.pack(anchor='w', pady=(0, 10))
        self.listbox = tk.Listbox(left, bg=BG, fg=FG, selectbackground='#444444', selectforeground='white',
                                  highlightthickness=0, borderwidth=0, activestyle='none',
                                  font=('Helvetica Neue', 11), exportselection=False)
        self.listbox.pack(fill='both', expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.select_file)
        ttk.Separator(content, orient='vertical').pack(side='left', fill='y')
        right = ttk.Frame(content, width=280, padding=(18, 16))
        right.pack(side='right', fill='y'); right.pack_propagate(False)
        ttk.Separator(content, orient='vertical').pack(side='right', fill='y')
        self.label(right, 'crop_settings', font=('Helvetica Neue', 13, 'bold')).pack(anchor='w', pady=(0, 12))
        self.label(right, 'format').pack(anchor='w', pady=(0, 5))
        self.format_combo = ttk.Combobox(right, state='readonly')
        self.format_combo.pack(fill='x', pady=(0, 12))
        self.format_combo.bind('<<ComboboxSelected>>', self.format_changed)
        self.rotate_check = ttk.Checkbutton(right, variable=self.auto_rotate)
        self.translated_widgets.append((self.rotate_check, 'rotate'))
        self.rotate_check.pack(anchor='w')
        self.border_check = ttk.Checkbutton(right, variable=self.keep_border)
        self.translated_widgets.append((self.border_check, 'border'))
        self.border_check.pack(anchor='w', pady=(0, 10))
        self.reset_button = self.button(right, 'reset', self.reset_crop)
        self.reset_button.pack(fill='x', pady=(2, 10))
        self.note = self.label(right, 'manual_note', wraplength=240, style='Muted.TLabel', justify='left')
        self.note.pack(anchor='w', pady=(0, 12))
        ttk.Separator(right).pack(fill='x', pady=(0, 16))
        self.label(right, 'export_settings', font=('Helvetica Neue', 13, 'bold')).pack(anchor='w', pady=(0, 12))
        self.label(right, 'export').pack(anchor='w', pady=(0, 5))
        self.export_combo = ttk.Combobox(right, textvariable=self.export, values=('TIFF16', 'JPEG'), state='readonly')
        self.export_combo.pack(fill='x', pady=(0, 14))
        self.label(right, 'location').pack(anchor='w', pady=(0, 5))
        self.path_entry = ttk.Entry(right, textvariable=self.outdir)
        self.path_entry.pack(fill='x')
        self.choose_button = self.button(right, 'choose', self.choose_output)
        self.choose_button.pack(anchor='e', pady=(6, 0))
        center = ttk.Frame(content, padding=(16, 12))
        center.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(center, bg='#181818', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.redraw())
        self.canvas.bind('<ButtonPress-1>', self.drag_start)
        self.canvas.bind('<B1-Motion>', self.drag_move)
        self.canvas.bind('<ButtonRelease-1>', self.drag_end)
        self.hint = self.label(center, 'draw', style='Muted.TLabel')
        self.hint.pack(anchor='w', pady=(8, 0))
        footer = ttk.Frame(self.root, padding=(16, 10))
        ttk.Separator(self.root).pack(fill='x')
        footer.pack(fill='x')
        self.status = ttk.Label(footer, style='Muted.TLabel')
        self.status.pack(side='left', fill='x', expand=True)
        self.start_button = self.button(footer, 'start', self.start, style='Primary.TButton')
        self.start_button.pack(side='right')
        self.stop_button = self.button(footer, 'stop', self.cancel, state='disabled')
        self.stop_button.pack(side='right', padx=8)
        self.open_button = self.button(footer, 'open', self.open_output)
        self.open_button.pack(side='right')
        for widget in (self.root, self.canvas, self.listbox):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', self.on_drop)

    def refresh_language(self):
        for widget, key in self.translated_widgets:
            widget.configure(text=self.tr(key))
        choices = list(FORMAT_CHOICES)
        self.format_labels = [self.tr('auto') if FORMAT_CHOICES[x] == 'auto' else (x.replace('半格', 'Half frame') if self.lang == 'en' else x) for x in choices]
        self.format_values = [FORMAT_CHOICES[x] for x in choices]
        self.format_combo.configure(values=self.format_labels)
        try: index = self.format_values.index(self.format.get())
        except ValueError: index = 0
        self.format_combo.current(index)
        self.update_list()
        self.update_status()
        self.redraw()

    def change_language(self, _event=None):
        self.lang = 'en' if self.lang == 'zh' else 'zh'
        self.refresh_language()

    def format_changed(self, _event=None):
        index = self.format_combo.current()
        if index >= 0: self.format.set(self.format_values[index])

    def update_status(self):
        if self.status_key == 'summary':
            self.status.configure(text=self.tr('summary', **self.status_value))
        elif self.status_key == 'detail':
            self.status.configure(text=self.status_value)
        else:
            self.status.configure(text=self.tr(self.status_key))

    def set_status(self, key, value=None):
        self.status_key, self.status_value = key, value
        self.update_status()

    def update_list(self):
        selected = self.current
        self.listbox.delete(0, 'end')
        for path in self.paths:
            state = self.states.get(path, 'pending')
            self.listbox.insert('end', f'{path.name}  ·  {self.tr(state)}')
        if selected in self.paths:
            self.listbox.selection_set(self.paths.index(selected))
        self.files_label.configure(text=f"{self.tr('files')}  ({len(self.paths)})")

    def add_files(self):
        if self.running: return
        self.add_paths(filedialog.askopenfilenames(parent=self.root, title=self.tr('add')))

    def add_folder(self):
        if self.running: return
        folder = filedialog.askdirectory(parent=self.root, title=self.tr('folder'))
        if folder: self.add_paths([folder])

    def on_drop(self, event):
        if not self.running: self.add_paths(self.root.tk.splitlist(event.data))

    def add_paths(self, names):
        for name in names:
            path = Path(name).expanduser()
            candidates = sorted(path.iterdir()) if path.is_dir() else [path]
            for item in candidates:
                item = item.resolve()
                if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS and item not in self.paths:
                    self.paths.append(item)
                    self.states[item] = 'pending'
        self.update_list()
        if self.paths and self.current is None:
            self.listbox.selection_set(0)
            self.select_file()

    def remove(self):
        if self.running: return
        indexes = self.listbox.curselection()
        if not indexes: return
        path = self.paths.pop(indexes[0])
        self.boxes.pop(path, None); self.states.pop(path, None); self.records.pop(path, None)
        self.current = None; self.preview_image = None
        self.update_list(); self.redraw()
        if self.paths:
            self.listbox.selection_set(min(indexes[0], len(self.paths)-1)); self.select_file()

    def clear(self):
        if self.running: return
        self.paths.clear(); self.boxes.clear(); self.states.clear(); self.records.clear()
        self.current = None; self.preview_image = None
        self.update_list(); self.redraw(); self.set_status('select')

    def choose_output(self):
        folder = filedialog.askdirectory(parent=self.root, title=self.tr('location'))
        if folder: self.outdir.set(folder)

    def select_file(self, _event=None):
        selected = self.listbox.curselection()
        if not selected: return
        path = self.paths[selected[0]]
        self.current = path
        self.preview_image = None
        self.preview_rect = None
        self.set_status('loading'); self.redraw()
        threading.Thread(target=self.load_preview, args=(path,), daemon=True).start()

    def load_preview(self, path):
        try:
            image, _ = read_image(path)
            rgb = detection_image(image)[:, :, ::-1]
            image = Image.fromarray(rgb)
            image.thumbnail((1600, 1600))
            self.jobs.put(('preview', path, image, None))
        except Exception as exc:
            self.jobs.put(('preview', path, None, str(exc)))

    def redraw(self):
        if not hasattr(self, 'canvas'): return
        canvas = self.canvas
        canvas.delete('all')
        if self.preview_image is None:
            canvas.create_text(max(canvas.winfo_width(), 200)//2, max(canvas.winfo_height(), 200)//2,
                               text=self.tr('select'), fill=MUTED, font=('Helvetica Neue', 13))
            return
        available = (max(1, canvas.winfo_width()-32), max(1, canvas.winfo_height()-32))
        img = self.preview_image.copy(); img.thumbnail(available)
        width, height = img.size
        left = (canvas.winfo_width()-width)//2; top = (canvas.winfo_height()-height)//2
        self.preview_rect = (left, top, width, height)
        self.preview_photo = ImageTk.PhotoImage(img, master=self.root)
        canvas.create_image(left, top, anchor='nw', image=self.preview_photo)
        box = self.drag_box or self.boxes.get(self.current)
        if box:
            x0,y0,x1,y1 = box
            ax,ay,bx,by = left+x0*width,top+y0*height,left+x1*width,top+y1*height
            canvas.create_rectangle(ax, ay, bx, by, outline='white', width=2)
            for x,y in ((ax,ay),(bx,ay),(bx,by),(ax,by)):
                canvas.create_rectangle(x-5,y-5,x+5,y+5, fill='white', outline='#444444')

    def point(self, event):
        if not self.preview_rect: return None
        x,y,w,h = self.preview_rect
        return ((event.x-x)/w, (event.y-y)/h)

    def drag_start(self, event):
        if self.running or not self.preview_rect or self.current is None: return
        p = self.point(event)
        if not (0 <= p[0] <= 1 and 0 <= p[1] <= 1): return
        existing = self.boxes.get(self.current)
        self.drag_corner = None
        if existing:
            x0,y0,x1,y1 = existing
            corners = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
            _,_,w,h = self.preview_rect
            distances = [((p[0]-x)*w)**2+((p[1]-y)*h)**2 for x,y in corners]
            nearest = min(range(4), key=lambda i: distances[i])
            if distances[nearest] <= 18**2:
                self.drag_corner = nearest
                self.drag_anchor = corners[(nearest+2)%4]
        if self.drag_corner is None: self.drag_anchor = p
        self.drag_box = existing

    def drag_move(self, event):
        if self.drag_anchor is None: return
        try: self.drag_box = normalize_box(self.drag_anchor, self.point(event))
        except ValueError: return
        self.redraw()

    def drag_end(self, event):
        if self.drag_anchor is None: return
        try:
            box = normalize_box(self.drag_anchor, self.point(event))
            self.boxes[self.current] = box
            self.states[self.current] = 'manual_state'
            self.update_list()
        except ValueError: pass
        self.drag_anchor = None; self.drag_box = None; self.redraw()

    def reset_crop(self):
        if self.running or self.current is None: return
        self.boxes.pop(self.current, None)
        self.states[self.current] = 'pending'
        self.update_list(); self.redraw()

    def set_busy(self, busy):
        self.running = busy
        for w in (self.add_button,self.folder_button,self.remove_button,self.clear_button,self.reset_button,
                  self.choose_button,self.path_entry,self.rotate_check,self.border_check,self.start_button):
            w.configure(state='disabled' if busy else 'normal')
        for w in (self.format_combo,self.export_combo): w.configure(state='disabled' if busy else 'readonly')
        self.lang_combo.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')

    def start(self):
        if not self.paths:
            messagebox.showerror(self.tr('error'), self.tr('select_required'), parent=self.root); return
        folder = Path(self.outdir.get()).expanduser()
        if not self.outdir.get().strip() or not folder.is_dir():
            messagebox.showerror(self.tr('error'), self.tr('output_required'), parent=self.root); return
        options = Options(format=self.format.get(), output_format=self.export.get(), keep_border=self.keep_border.get(), auto_rotate=self.auto_rotate.get())
        self.stop.clear(); self.set_busy(True)
        items = [(p, self.boxes.get(p)) for p in self.paths]
        threading.Thread(target=self.worker, args=(items, folder, options), daemon=True).start()

    def worker(self, items, folder, options):
        ok = failed = 0; records = []
        for path, box in items:
            if self.stop.is_set(): break
            self.jobs.put(('state', path, 'processing'))
            try:
                record = export_one(path, folder, options, box)
                records.append(record); ok += 1
                self.jobs.put(('result', path, record, None))
            except Exception as exc:
                record = {'source':str(path), 'error':str(exc)}
                records.append(record); failed += 1
                self.jobs.put(('result', path, record, str(exc)))
        report_error = None
        try:
            name = 'FilmCrop_report_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6] + '.json'
            (folder/name).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf8')
        except Exception as exc: report_error = str(exc)
        self.jobs.put(('finished', ok, failed, len(items)-len(records), report_error))

    def poll(self):
        try:
            while True:
                event = self.jobs.get_nowait()
                if event[0] == 'preview':
                    _, path, image, error = event
                    if path != self.current: continue
                    self.preview_image = image
                    self.set_status('detail', self.tr('no_image') + ': ' + error) if error else self.set_status('manual' if path in self.boxes else 'draw')
                    self.redraw()
                elif event[0] == 'state':
                    _,path,state = event; self.states[path] = state; self.update_list()
                elif event[0] == 'result':
                    _,path,record,error = event
                    self.states[path] = 'failed' if error else 'done'
                    self.records[path] = record
                    self.update_list()
                    if error: self.set_status('detail', f'{path.name}: {error}')
                elif event[0] == 'finished':
                    _,ok,failed,remaining,report_error = event
                    self.set_busy(False)
                    self.set_status('summary', {'ok':ok,'failed':failed,'remaining':remaining})
                    if report_error: messagebox.showerror(self.tr('error'), report_error, parent=self.root)
        except queue.Empty: pass
        self.root.after(100, self.poll)

    def cancel(self):
        self.stop.set(); self.set_status('stopping'); self.stop_button.configure(state='disabled')

    def open_output(self):
        path = Path(self.outdir.get())
        if self.outdir.get() and path.is_dir():
            if sys.platform == 'darwin': subprocess.Popen(['open', str(path)])
            elif sys.platform == 'win32': os.startfile(str(path))
            else: subprocess.Popen(['xdg-open', str(path)])

    def close(self):
        if self.running:
            self.cancel(); messagebox.showinfo('FilmCrop', self.tr('busy'), parent=self.root)
        else: self.root.destroy()


def main():
    root = create_root()
    app = ModernFilmApp(root)
    if '--startup-test' in sys.argv:
        from film_diagnostic import startup_test
        startup_test(root, sys.argv[sys.argv.index('--startup-test')+1])
    root.mainloop()

if __name__ == '__main__': main()
