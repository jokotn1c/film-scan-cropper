"""FilmCrop modern desktop interface. The original GUI remains in film_gui.py."""
from pathlib import Path
from dataclasses import replace
from datetime import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from film_ui_scale import layout_scale, choose_latin_font, choose_chinese_font, register_bundled_font
import uuid

from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES
from film_gui import create_root, FilmApp
from film_engine import Options
from film_io import SUPPORTED_EXTENSIONS, read_image, detection_image
from film_crop import FORMAT_CHOICES
from film_manual import normalize_box, translate, detected_outline
from film_modern_export import export_one
from film_version import VERSION
from film_darkframe import FormatRequired

BG = '#202020'
PANEL = '#262626'
FIELD = '#303030'
FG = '#e9e9e9'
MUTED = '#a6a6a6'
LINE = '#414141'


class ModernFilmApp:
    def __init__(self, root):
        self.root = root
        if sys.platform == 'win32':
            FilmApp.set_app_icon(self)
        register_bundled_font()
        families = set(tkfont.families(root))
        self.latin_font = choose_latin_font(families)
        self.chinese_font = choose_chinese_font(families)
        self.ui_font = tkfont.Font(root=root, family=self.chinese_font, size=16)
        self.heading_font = tkfont.Font(root=root, family=self.chinese_font, size=19, weight='bold')
        self.latin_ui_font = tkfont.Font(root=root, family=self.latin_font, size=16)
        self.brand_font = tkfont.Font(root=root, family=self.latin_font, size=19, weight='bold')
        self.scale = 1.0
        self._resize_job = None
        self._redraw_job = None
        root.title('FilmCrop ' + VERSION + ' · Preview')
        root.geometry('1080x700' if sys.platform == 'win32' else '1440x900')
        root.minsize(900, 580)
        root.configure(bg=BG)
        self.lang = 'zh'
        self.paths = []
        self.boxes = {}
        self.states = {}
        self.records = {}
        self.file_formats = {}
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
        self._capture_layout(root)
        if sys.platform == 'win32':
            # Windows uses a fixed control layout. Pack allocates the remaining
            # space to the file list and preview without resizing every widget.
            self._apply_scale()
        else:
            root.bind('<Configure>', self._window_resized, add='+')
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
        kwargs.setdefault('width', 0)
        widget = ttk.Button(parent, command=command, **kwargs)
        self.translated_widgets.append((widget, key))
        return widget

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=self.ui_font, background=BG, foreground=FG)
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
        toolbar = ttk.Frame(self.root, padding=(20, 12))
        toolbar.pack(fill='x')
        self.label(toolbar, 'language', style='Muted.TLabel').pack(side='right', padx=8)
        self.lang_combo = ttk.Button(toolbar, text='中文 / English', command=self.change_language)
        self.lang_combo.pack(side='right')
        ttk.Label(toolbar, text='FilmCrop', font=self.brand_font).pack(anchor='center')
        ttk.Separator(self.root).pack(fill='x')
        content = ttk.Frame(self.root)
        content.pack(fill='both', expand=True)
        self.left_panel = ttk.Frame(content, width=265, padding=(18, 20))
        left = self.left_panel
        left.pack(side='left', fill='y'); left.pack_propagate(False)
        actions = ttk.Frame(left)
        actions.pack(fill='x', pady=(0, 20))
        self.add_button = self.button(actions, 'add', self.add_files)
        self.folder_button = self.button(actions, 'folder', self.add_folder)
        self.add_button.pack(fill='x', pady=(0, 7))
        self.folder_button.pack(fill='x')
        self.files_label = self.label(left, 'files')
        self.files_label.pack(anchor='w', pady=(0, 10))
        self.listbox = tk.Listbox(left, bg=BG, fg=FG, selectbackground='#444444', selectforeground='white',
                                  highlightthickness=0, borderwidth=0, activestyle='none',
                                  font=self.ui_font, exportselection=False)
        self.listbox.pack(fill='both', expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.select_file)
        self.listbox.bind('<Configure>', lambda _event: self.update_list())
        list_actions = ttk.Frame(left)
        list_actions.pack(fill='x', pady=(10, 0))
        self.remove_button = self.button(list_actions, 'remove', self.remove)
        self.clear_button = self.button(list_actions, 'clear', self.clear)
        self.remove_button.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.clear_button.pack(side='left', fill='x', expand=True, padx=(4, 0))
        self.format_retry_button = self.button(left, 'reopen_formats', self.open_pending_formats, state='disabled')
        self.format_retry_button.pack(fill='x', pady=(10, 0))
        ttk.Separator(content, orient='vertical').pack(side='left', fill='y')
        self.right_panel = ttk.Frame(content, width=340, padding=(22, 22))
        right = self.right_panel
        right.pack(side='right', fill='y'); right.pack_propagate(False)
        ttk.Separator(content, orient='vertical').pack(side='right', fill='y')
        self.label(right, 'crop_settings', font=self.heading_font).pack(anchor='w', pady=(0, 16))
        self.label(right, 'format').pack(anchor='w', pady=(0, 6))
        self.format_combo = ttk.Combobox(right, state='readonly', font=self.ui_font)
        self.format_combo.pack(fill='x', pady=(0, 16))
        self.format_combo.bind('<<ComboboxSelected>>', self.format_changed)
        self.rotate_check = ttk.Checkbutton(right, variable=self.auto_rotate)
        self.translated_widgets.append((self.rotate_check, 'rotate'))
        self.rotate_check.pack(anchor='w', pady=(0, 6))
        self.border_check = ttk.Checkbutton(right, variable=self.keep_border)
        self.translated_widgets.append((self.border_check, 'border'))
        self.border_check.pack(anchor='w', pady=(0, 14))
        self.reset_button = self.button(right, 'reset', self.reset_crop)
        self.reset_button.pack(fill='x', pady=(0, 10))
        self.note = self.label(right, 'manual_note', wraplength=290, style='Muted.TLabel', justify='left')
        self.note.pack(anchor='w', pady=(0, 16))
        ttk.Separator(right).pack(fill='x', pady=(0, 20))
        self.label(right, 'export_settings', font=self.heading_font).pack(anchor='w', pady=(0, 16))
        self.label(right, 'export').pack(anchor='w', pady=(0, 6))
        self.export_combo = ttk.Combobox(right, textvariable=self.export, values=('TIFF16', 'JPEG'), state='readonly', font=self.latin_ui_font)
        self.export_combo.pack(fill='x', pady=(0, 16))
        self.label(right, 'location').pack(anchor='w', pady=(0, 6))
        path_row = ttk.Frame(right) if sys.platform == 'win32' else right
        if path_row is not right:
            path_row.pack(fill='x')
        self.path_entry = ttk.Entry(path_row, textvariable=self.outdir, font=self.ui_font)
        self.choose_button = self.button(path_row, 'choose', self.choose_output)
        if sys.platform == 'win32':
            self.choose_button.pack(side='right', padx=(6, 0))
            self.path_entry.pack(side='left', fill='x', expand=True)
        else:
            self.path_entry.pack(fill='x')
            self.choose_button.pack(anchor='e', pady=(8, 0))
        center = ttk.Frame(content, padding=(18, 18))
        center.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(center, bg='#181818', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self._preview_resized)
        self.canvas.bind('<ButtonPress-1>', self.drag_start)
        self.canvas.bind('<B1-Motion>', self.drag_move)
        self.canvas.bind('<ButtonRelease-1>', self.drag_end)
        self.hint = self.label(center, 'draw', style='Muted.TLabel')
        self.hint.pack(anchor='center', pady=(12, 0))
        footer = ttk.Frame(self.root, padding=(20, 14))
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

    def _capture_layout(self, widget):
        if not hasattr(self, '_scaled_layout'):
            self._scaled_layout = []
        for child in widget.winfo_children():
            info = child.pack_info() if child.winfo_manager() == 'pack' else None
            if info:
                margins = {key: info[key] for key in ('padx', 'pady')}
                self._scaled_layout.append((child, margins))
            if isinstance(child, ttk.Frame):
                child._base_padding = tuple(map(int, child.cget('padding'))) if child.cget('padding') else ()
            self._capture_layout(child)

    @staticmethod
    def _scaled_padding(value, scale):
        values = value if isinstance(value, (tuple, list)) else (value,)
        result = tuple(round(int(v) * scale) for v in values)
        return result if len(result) > 1 else result[0]

    def _window_resized(self, event):
        if event.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(60, self._apply_scale)

    def _preview_resized(self, _event=None):
        # Render the latest canvas dimensions once per frame, even when several
        # geometry notifications arrive before Tk has finished laying out.
        if self._redraw_job is None:
            self._redraw_job = self.root.after(16, self._redraw_preview)

    def _redraw_preview(self):
        self._redraw_job = None
        self.redraw()

    def _apply_scale(self):
        self._resize_job = None
        scale = .55 if sys.platform == 'win32' else layout_scale(self.root.winfo_width(), self.root.winfo_height())
        self.scale = scale
        self._apply_font_scale()
        self.left_panel.configure(width=200 if sys.platform == 'win32' else round(265 * scale))
        self.right_panel.configure(width=280 if sys.platform == 'win32' else round(340 * scale))
        self.note.configure(wraplength=250 if sys.platform == 'win32' else round(290 * scale))
        for widget, margins in self._scaled_layout:
            widget.pack_configure(**{key: self._scaled_padding(value, scale) for key, value in margins.items()})
            if isinstance(widget, ttk.Frame) and getattr(widget, '_base_padding', ()):
                widget.configure(padding=self._scaled_padding(widget._base_padding, scale))
        style = ttk.Style(self.root)
        style.configure('TButton', padding=(round(10*scale), round(7*scale)))
        style.configure('Primary.TButton', padding=(round(18*scale), round(9*scale)))
        style.configure('TCombobox', padding=round(5*scale))
        style.configure('TEntry', padding=round(6*scale))
        style.configure('TCheckbutton', padding=(0, round(4*scale)))
        self.redraw()

    def _apply_font_scale(self):
        if sys.platform == 'win32':
            # Point sizes follow system DPI, never the size of the app window.
            self.ui_font.configure(size=10)
            self.heading_font.configure(size=12)
            self.latin_ui_font.configure(size=10)
            self.brand_font.configure(size=14)
        else:
            self.ui_font.configure(size=max(8, round(16 * self.scale)))
            self.heading_font.configure(size=max(10, round(19 * self.scale)))
            self.latin_ui_font.configure(size=max(8, round(16 * self.scale)))
            self.brand_font.configure(size=max(10, round(19 * self.scale)))

    def refresh_language(self):
        family = self.chinese_font if self.lang == 'zh' else self.latin_font
        self.ui_font.configure(family=family)
        self.heading_font.configure(family=family)
        self._apply_font_scale()
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
        scroll = self.listbox.yview()[0]
        self.listbox.delete(0, 'end')
        for path in self.paths:
            state = self.states.get(path, 'pending')
            prefix = f'{self.tr(state)} · '
            available = max(20, self.listbox.winfo_width()-12-self.ui_font.measure(prefix))
            name = path.name
            if self.ui_font.measure(name) > available:
                left, right = len(path.stem), len(path.suffix)
                while left+right > 1 and self.ui_font.measure(name[:left]+'…'+name[-right:]) > available:
                    if left > right: left -= 1
                    else: right -= 1
                name = name[:left]+'…'+(name[-right:] if right else '')
            self.listbox.insert('end', prefix+name)
        if selected in self.paths:
            self.listbox.selection_set(self.paths.index(selected))
        self.listbox.yview_moveto(scroll)
        self.files_label.configure(text=f"{self.tr('files')}  ({len(self.paths)})")
        self.update_format_retry_button()

    def pending_format_paths(self):
        return [p for p in self.paths if self.records.get(p, {}).get('requires_format')
                and self.states.get(p) == 'needs_format']

    def update_format_retry_button(self):
        self.format_retry_button.configure(state='normal' if not self.running and self.pending_format_paths() else 'disabled')

    def open_pending_formats(self):
        if self.running: return
        paths = self.pending_format_paths()
        if paths: self.ask_dark_formats(paths)

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
        self.file_formats.pop(path, None)
        self.current = None; self.preview_image = None
        self.update_list(); self.redraw()
        if self.paths:
            self.listbox.selection_set(min(indexes[0], len(self.paths)-1)); self.select_file()

    def clear(self):
        if self.running: return
        self.paths.clear(); self.boxes.clear(); self.states.clear(); self.records.clear()
        self.file_formats.clear()
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
                               text=self.tr('select'), fill=MUTED, font=self.ui_font)
            return
        available = (max(1, canvas.winfo_width()-32), max(1, canvas.winfo_height()-32))
        img = self.preview_image.copy(); img.thumbnail(available)
        width, height = img.size
        left = (canvas.winfo_width()-width)//2; top = (canvas.winfo_height()-height)//2
        self.preview_rect = (left, top, width, height)
        self.preview_photo = ImageTk.PhotoImage(img, master=self.root)
        canvas.create_image(left, top, anchor='nw', image=self.preview_photo)
        box = self.drag_box or self.boxes.get(self.current)
        outline = detected_outline(self.records.get(self.current, {})) if box is None else None
        if box:
            x0,y0,x1,y1 = box
            outline = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        if outline:
            points = [(left+x*width, top+y*height) for x,y in outline]
            canvas.create_polygon(*[v for point in points for v in point], fill='', outline='white', width=2)
            for x,y in points:
                canvas.create_rectangle(x-5*self.scale,y-5*self.scale,x+5*self.scale,y+5*self.scale, fill='white', outline='#444444')

    def point(self, event):
        if not self.preview_rect: return None
        x,y,w,h = self.preview_rect
        return ((event.x-x)/w, (event.y-y)/h)

    def drag_start(self, event):
        if self.running or not self.preview_rect or self.current is None: return
        p = self.point(event)
        if not (0 <= p[0] <= 1 and 0 <= p[1] <= 1): return
        existing = self.boxes.get(self.current)
        auto_outline = None
        if existing is None:
            outline = detected_outline(getattr(self, 'records', {}).get(self.current, {}))
            if outline:
                auto_outline = outline
                existing = (min(p[0] for p in outline), min(p[1] for p in outline),
                            max(p[0] for p in outline), max(p[1] for p in outline))
        self.drag_corner = None
        if existing:
            x0,y0,x1,y1 = existing
            corners = auto_outline or [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
            _,_,w,h = self.preview_rect
            distances = [((p[0]-x)*w)**2+((p[1]-y)*h)**2 for x,y in corners]
            nearest = min(range(4), key=lambda i: distances[i])
            if distances[nearest] <= (18*self.scale)**2:
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
        self.update_format_retry_button()

    def start(self, retry_paths=None):
        if self.running: return
        if not self.paths:
            messagebox.showerror(self.tr('error'), self.tr('select_required'), parent=self.root); return
        folder = Path(self.outdir.get()).expanduser()
        if not self.outdir.get().strip() or not folder.is_dir():
            messagebox.showerror(self.tr('error'), self.tr('output_required'), parent=self.root); return
        options = Options(format=self.format.get(), output_format=self.export.get(), keep_border=self.keep_border.get(), auto_rotate=self.auto_rotate.get())
        self.stop.clear(); self.set_busy(True)
        items = [(p, self.boxes.get(p)) for p in (self.paths if retry_paths is None else retry_paths)]
        self.active_paths = [p for p, _ in items]
        self.active_options = {p: replace(options, format=self.file_formats.get(p, options.format))
                               if options.format == 'auto' else options for p, _ in items}
        threading.Thread(target=self.worker, args=(items, folder, options), daemon=True).start()

    def worker(self, items, folder, options):
        ok = failed = 0; records = []
        for path, box in items:
            if self.stop.is_set(): break
            self.jobs.put(('state', path, 'processing'))
            try:
                record = export_one(path, folder, self.active_options.get(path, options), box)
                records.append(record); ok += 1
                self.jobs.put(('result', path, record, None))
            except FormatRequired as exc:
                record = {'source':str(path), 'error':str(exc), 'requires_format':True}
                records.append(record)
                self.jobs.put(('result', path, record, str(exc)))
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
                    self.states[path] = 'needs_format' if record.get('requires_format') else ('failed' if error else 'done')
                    self.records[path] = record
                    self.update_list()
                    if path == self.current: self.redraw()
                    if error: self.set_status('detail', f'{path.name}: {error}')
                elif event[0] == 'finished':
                    _,ok,failed,remaining,report_error = event
                    self.set_busy(False)
                    self.set_status('summary', {'ok':ok,'failed':failed,'remaining':remaining})
                    if report_error: messagebox.showerror(self.tr('error'), report_error, parent=self.root)
                    pending = [p for p in self.active_paths if self.records.get(p, {}).get('requires_format')]
                    if pending and not self.stop.is_set(): self.ask_dark_formats(pending)
        except queue.Empty: pass
        self.root.after(100, self.poll)

    def ask_dark_formats(self, paths):
        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr('needs_format'))
        dialog.transient(self.root)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=self.tr('format_prompt')).pack(anchor='w', pady=(0, 10))
        content = ttk.Frame(body)
        content.pack(fill='both', expand=True)
        listing = ttk.Frame(content)
        listing.pack(side='left', fill='both', expand=True)
        preview_panel = ttk.Frame(content, padding=(12, 0, 0, 0))
        preview_panel.pack(side='right', fill='both')
        preview = tk.Canvas(preview_panel, bg='#181818', highlightthickness=0, width=320, height=300)
        preview.pack(fill='both', expand=True)
        preview_name = ttk.Label(preview_panel, wraplength=320)
        preview_name.pack(fill='x', pady=(6, 0))
        canvas = tk.Canvas(listing, bg=BG, highlightthickness=0, width=480, height=min(340, 44*len(paths)))
        scrollbar = ttk.Scrollbar(listing, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        rows = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=rows, anchor='nw')
        rows.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        preview_jobs = queue.Queue()
        cache = {}
        hover = {'path':None, 'timer':None, 'poll':None, 'initial':None}
        def close_dialog():
            for key in ('timer', 'poll', 'initial'):
                if hover[key] is not None:
                    dialog.after_cancel(hover[key])
                    hover[key] = None
            dialog.destroy()
        dialog.protocol('WM_DELETE_WINDOW', close_dialog)
        def read_preview(path):
            try:
                image, _ = read_image(path)
                image = Image.fromarray(detection_image(image)[:, :, ::-1])
                image.thumbnail((320, 300))
                preview_jobs.put((path, image, None))
            except Exception as exc:
                preview_jobs.put((path, None, str(exc)))
        def show_preview(image):
            preview.delete('all')
            photo = ImageTk.PhotoImage(image, master=dialog)
            preview.photo = photo
            preview.create_image(preview.winfo_width()/2, preview.winfo_height()/2, image=photo)
        def request_preview(path):
            if hover['path'] == path: return
            hover['path'] = path
            preview_name.configure(text=path.name)
            preview.delete('all')
            preview.photo = None
            if hover['timer'] is not None:
                dialog.after_cancel(hover['timer'])
            if path in cache:
                show_preview(cache[path])
                return
            preview.create_text(160, 150, text=self.tr('loading'), fill=MUTED, font=self.ui_font)
            def launch():
                hover['timer'] = None
                threading.Thread(target=read_preview, args=(path,), daemon=True).start()
            hover['timer'] = dialog.after(180, launch)
        def poll_preview():
            if not dialog.winfo_exists(): return
            try:
                while True:
                    path, image, error = preview_jobs.get_nowait()
                    if image is not None:
                        # Keep a bounded thumbnail cache, never full RAW images.
                        if len(cache) >= 12: cache.pop(next(iter(cache)))
                        cache[path] = image
                    if path != hover['path']: continue
                    if error:
                        preview.delete('all')
                        preview.create_text(160, 150, text=self.tr('no_image'), fill=MUTED, font=self.ui_font)
                    else: show_preview(image)
            except queue.Empty: pass
            hover['poll'] = dialog.after(100, poll_preview)
        hover['poll'] = dialog.after(100, poll_preview)
        choices = {}
        for path in paths:
            row = ttk.Frame(rows)
            row.pack(fill='x', pady=5)
            name = path.name if len(path.name) <= 38 else path.name[:25]+'…'+path.name[-12:]
            label = ttk.Label(row, text=name, width=29)
            label.pack(side='left')
            label.bind('<Enter>', lambda _event, p=path: request_preview(p))
            combo = ttk.Combobox(row, state='readonly', width=20,
                                 values=self.format_labels[1:])
            combo.set(self.tr('choose_format'))
            combo.pack(side='right')
            choices[path] = combo
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', pady=(12, 0))
        def apply():
            selected = {p:self.format_values[c.current()+1] for p,c in choices.items() if c.current() >= 0}
            if not selected: return
            self.file_formats.update(selected)
            close_dialog()
            self.start(list(selected))
        ttk.Button(buttons, text=self.tr('retry_format'), command=apply).pack(side='right')
        ttk.Button(buttons, text=self.tr('later'), command=close_dialog).pack(side='right', padx=8)
        dialog.grab_set()
        dialog.focus_set()
        if paths: hover['initial'] = dialog.after_idle(lambda: request_preview(paths[0]))

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
    if '--windows-preview-check' in sys.argv:
        from tools.check_windows_preview import main as preview_check
        preview_check()
        return
    root = create_root()
    app = ModernFilmApp(root)
    if '--startup-test' in sys.argv:
        from tools.film_diagnostic import startup_test
        startup_test(root, sys.argv[sys.argv.index('--startup-test')+1])
    root.mainloop()

if __name__ == '__main__': main()
