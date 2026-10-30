"""FilmCrop desktop application. Drag and drop provided by bundled tkdnd."""
import csv
from datetime import datetime
import json
import os
import subprocess
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid
from dataclasses import replace
from film_darkframe import FormatRequired

from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk
from film_engine import Options, process_file
from film_io import SUPPORTED_EXTENSIONS
from film_version import VERSION
from film_crop import FORMAT_LABELS, FORMAT_CHOICES


class FilmApp:
    def __init__(self, root):
        self.root = root
        self.root.title('FilmCrop ' + VERSION)
        self.set_app_icon()
        self.root.geometry('900x620')
        self.root.minsize(800, 470)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.running = False
        self.paths = {}
        self.outputs = {}
        self.completed = {}
        self.active_jobs = {}
        self.batch_skipped = 0
        self.file_formats = {}
        self.active_options = {}
        self.preview_photo = None
        self.output_dir = tk.StringVar()
        self.format = tk.StringVar(value='自动识别')
        self.export = tk.StringVar(value='16 位 TIFF')
        self.keep = tk.BooleanVar(value=False)
        self.auto_rotate = tk.BooleanVar(value=True)
        self.top_trim = tk.StringVar(value='1.0')
        self.bottom_trim = tk.StringVar(value='1.0')
        self.border_margin = tk.StringVar(value='2.5')
        self.sprocket_side = tk.StringVar(value='3.5')
        self.status = tk.StringVar(value='拖入照片 → 选择输出位置 → 开始裁切')
        self._build()
        self.fit_window(initial=True)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.poll)

    def set_app_icon(self):
        # Cocoa gets the Dock/application icon from the application bundle's
        # Info.plist. Tk's iconphoto replaces it with the window's PNG.
        if sys.platform == 'darwin':
            return
        assets = Path(__file__).resolve().parent / 'assets'
        with Image.open(assets / 'filmcrop.png') as image:
            self.app_icon = ImageTk.PhotoImage(image.copy(), master=self.root)
        self.root.iconphoto(True, self.app_icon)
        if sys.platform == 'win32':
            icon_path = '//?/' + str((assets / 'filmcrop.ico').resolve()).replace('\\', '/')
            self.root.iconbitmap(icon_path)

    def _build(self):
        self.root.configure(bg='#f2f4f6')
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('TFrame', background='#f2f4f6')
        style.configure('TLabel', background='#f2f4f6', foreground='#29323a')
        style.configure('Sub.TLabel', foreground='#66727c')
        style.configure('TButton', padding=(10, 6))
        style.configure('Accent.TButton', background='#365b75', foreground='white')
        style.map('Accent.TButton', background=[('active', '#426e8c'), ('disabled', '#97a5af')])
        style.configure('Treeview', rowheight=29, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', padding=6)
        outer = self.outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill='both', expand=True)
        self.drop = tk.Label(outer, text='拖入 RAW、照片或文件夹',
                             font=('Microsoft YaHei UI', 11), fg='#365b75', bg='#e5ecf1',
                             height=2, highlightthickness=1, highlightbackground='#c7d3dd')
        self.drop.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.drop.drop_target_register(DND_FILES)
        self.drop.dnd_bind('<<Drop>>', self.on_drop)
        bar = ttk.Frame(outer)
        bar.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        self.add_button = ttk.Button(bar, text='添加文件', command=self.choose_files)
        self.folder_button = ttk.Button(bar, text='添加文件夹', command=self.choose_folder)
        self.remove_button = ttk.Button(bar, text='移除', command=self.remove)
        self.clear_button = ttk.Button(bar, text='清空', command=self.clear)
        for widget in [self.add_button, self.folder_button, self.remove_button, self.clear_button]:
            widget.pack(side='left', padx=(0, 6))
        middle = self.middle = ttk.Frame(outer)
        middle.grid(row=2, column=0, sticky='nsew', pady=(0, 12))
        listing = ttk.Frame(middle)
        listing.pack(side='left', fill='both', expand=True)
        self.tree = ttk.Treeview(listing, columns=('name', 'state', 'format'), show='headings', selectmode='extended')
        for key, title, width in [('name', '文件', 280), ('state', '状态', 100), ('format', '画幅', 100)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60)
        scroll = ttk.Scrollbar(listing, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.select_preview)
        self.tree.bind('<Double-1>', self.open_selected)
        preview = ttk.Frame(middle, padding=(12, 0, 0, 0), width=230)
        preview.pack(side='right', fill='y'); preview.pack_propagate(False)
        self.preview = tk.Label(preview, text='选中查看裁切结果', bg='#e3e7eb', fg='#66727c',
                                font=('Microsoft YaHei UI', 10), wraplength=210)
        self.preview.pack(fill='both', expand=True)
        self.detail = ttk.Label(preview, text='双击打开图片', style='Sub.TLabel', wraplength=210)
        self.detail.pack(fill='x', pady=(6, 0))
        pathrow = ttk.Frame(outer)
        pathrow.grid(row=3, column=0, sticky='ew', pady=(0, 10))
        ttk.Label(pathrow, text='输出到').pack(side='left', padx=(0, 10))
        self.path_entry = ttk.Entry(pathrow, textvariable=self.output_dir)
        self.path_entry.pack(side='left', fill='x', expand=True)
        self.browse_button = ttk.Button(pathrow, text='选择…', command=self.choose_output)
        self.browse_button.pack(side='left', padx=(8, 0))
        options = ttk.Frame(outer)
        options.grid(row=4, column=0, sticky='ew', pady=(0, 8))
        ttk.Label(options, text='画幅').pack(side='left')
        self.format_combo = ttk.Combobox(options, textvariable=self.format,
                                        values=list(FORMAT_CHOICES), width=13, state='readonly')
        self.format_combo.pack(side='left', padx=(6, 14))
        ttk.Label(options, text='导出').pack(side='left')
        self.export_combo = ttk.Combobox(options, textvariable=self.export,
                                        values=['16 位 TIFF', 'JPEG'], width=11, state='readonly')
        self.export_combo.pack(side='left', padx=(6, 14))
        self.keep_check = ttk.Checkbutton(options, text='保留齿孔 / 边框', variable=self.keep, command=self.mode_changed)
        self.keep_check.pack(side='left')
        self.rotate_check = ttk.Checkbutton(options, text='自动转正', variable=self.auto_rotate)
        self.rotate_check.pack(side='left', padx=(10, 0))
        self.more_button = ttk.Button(options, text='微调 ▾', command=self.toggle_advanced)
        self.more_button.pack(side='right')
        advanced = self.advanced = ttk.Frame(outer)
        advanced.grid(row=5, column=0, sticky='ew', pady=(0, 10))
        self.trim_widgets = []
        for column, title, variable in [(0, '上收边 %', self.top_trim), (2, '下收边 %', self.bottom_trim)]:
            ttk.Label(advanced, text=title).grid(row=0, column=column, sticky='w', padx=(0, 6))
            widget = ttk.Spinbox(advanced, from_=0, to=9.9, increment=.1, textvariable=variable, width=5)
            widget.grid(row=0, column=column+1, sticky='w', padx=(0, 20))
            self.trim_widgets.append(widget)
        ttk.Label(advanced, text='120 边框 %').grid(row=1, column=0, sticky='w', padx=(0, 6), pady=(8, 0))
        self.margin_widget = ttk.Spinbox(advanced, from_=0, to=10, increment=.5, textvariable=self.border_margin, width=5, state='disabled')
        self.margin_widget.grid(row=1, column=1, sticky='w', padx=(0, 20), pady=(8, 0))
        ttk.Label(advanced, text='135 留边 %').grid(row=1, column=2, sticky='w', padx=(0, 6), pady=(8, 0))
        self.side_widget = ttk.Spinbox(advanced, from_=0, to=10, increment=.5, textvariable=self.sprocket_side, width=5, state='disabled')
        self.side_widget.grid(row=1, column=3, sticky='w', pady=(8, 0))
        self.advanced.grid_remove()
        self.advanced_open = False
        bottom = self.bottom = ttk.Frame(outer)
        bottom.grid(row=6, column=0, sticky='ew')
        self.start_button = ttk.Button(bottom, text='开始裁切', style='Accent.TButton', command=self.start)
        self.start_button.pack(side='right')
        self.cancel_button = ttk.Button(bottom, text='停止', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='right', padx=8)
        self.open_button = ttk.Button(bottom, text='打开输出', command=self.open_output)
        self.open_button.pack(side='right', padx=(0, 8))
        self.progress = ttk.Progressbar(bottom, mode='determinate')
        self.progress.pack(side='left', fill='x', expand=True, padx=(0, 14))
        self.status_label = ttk.Label(outer, textvariable=self.status, style='Sub.TLabel')
        self.status_label.grid(row=7, column=0, sticky='ew', pady=(8, 0))
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1, minsize=120)
        self.layout_rows = list(outer.grid_slaves())
        self.options_row = options
        self._register_drop_targets(outer)

    def _register_drop_targets(self, widget):
        # Register the content area and every child so dropping over the list,
        # preview, controls or output field reaches the same handler.
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', self.on_drop)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._register_drop_targets(child)

    def fit_window(self, initial=False):
        self.root.update_idletasks()
        fixed = sum(w.winfo_reqheight() for w in self.outer.grid_slaves() if w is not self.middle) + 110
        width = max(800, self.options_row.winfo_reqwidth()+32)
        height = max(470, fixed+120)
        self.root.minsize(width, height)
        if initial:
            self.root.geometry(f'{max(900,width)}x{max(620,height)}')

    def toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        if self.advanced_open: self.advanced.grid()
        else: self.advanced.grid_remove()
        self.more_button.configure(text='微调 ▴' if self.advanced_open else '微调 ▾')
        self.fit_window()

    def mode_changed(self):
        for widget in self.trim_widgets: widget.configure(state='disabled' if self.keep.get() else 'normal')
        self.margin_widget.configure(state='normal' if self.keep.get() else 'disabled')
        self.side_widget.configure(state='normal' if self.keep.get() else 'disabled')

    def on_drop(self, event):
        if not self.running:
            self.add_paths(self.root.tk.splitlist(event.data))
        return event.action

    def choose_files(self):
        extensions = ' '.join('*'+s for s in sorted(SUPPORTED_EXTENSIONS))
        self.add_paths(filedialog.askopenfilenames(parent=self.root, title='添加 RAW 或照片',
                                                 filetypes=[('RAW 与照片', extensions), ('全部文件', '*.*')]))

    def choose_folder(self):
        path = filedialog.askdirectory(parent=self.root, title='添加文件夹')
        if path: self.add_paths([path])

    def add_paths(self, items):
        if self.running: return
        count = 0; skipped = 0
        existing = {str(p).casefold() for p in self.paths.values()}
        for item in items:
            path = Path(item).resolve()
            try:
                files = sorted(path.iterdir()) if path.is_dir() else [path]
                for source in files:
                    if not source.is_file() or source.suffix.lower() not in SUPPORTED_EXTENSIONS:
                        skipped += 1; continue
                    key = str(source).casefold()
                    if key in existing: continue
                    iid = self.tree.insert('', 'end', values=(source.name, '待处理', '—'))
                    self.paths[iid] = source; existing.add(key); count += 1
            except OSError as exc:
                self.status.set('读取文件夹失败：' + str(exc))
        self.status.set(f'{len(self.paths)} 个文件' + (f' · 跳过 {skipped} 项' if skipped else ''))

    def remove(self):
        if self.running: return
        for iid in self.tree.selection():
            self.paths.pop(iid, None); self.outputs.pop(iid, None); self.completed.pop(iid, None); self.tree.delete(iid)
            self.file_formats.pop(iid,None)

    def clear(self):
        if self.running: return
        self.tree.delete(*self.tree.get_children()); self.paths.clear(); self.outputs.clear()
        self.completed.clear()
        self.file_formats.clear()
        self.preview.configure(image='', text='选中查看裁切结果'); self.preview_photo = None
        self.status.set('已清空文件列表。')

    def choose_output(self):
        path = filedialog.askdirectory(parent=self.root, title='选择输出文件夹')
        if path: self.output_dir.set(path)

    def job_signature(self, source, folder, options):
        # Changing settings, destination or source requires a fresh crop.
        stat = source.stat()
        return (source, stat.st_size, stat.st_mtime_ns, folder, options)

    def pending_jobs(self, folder, options):
        jobs = []; signatures = {}
        for iid, source in self.paths.items():
            effective=replace(options,format=self.file_formats.get(iid,options.format))
            try:
                signature = self.job_signature(source, folder, effective)
            except OSError:
                signature = None  # Let the worker report unreadable files.
            record = self.outputs.get(iid, {})
            if (signature is not None and self.completed.get(iid) == signature
                    and record.get('output') and Path(record['output']).is_file()):
                continue
            jobs.append((iid, source)); signatures[iid] = signature
        return jobs, signatures

    def start(self):
        if self.running: return
        try:
            if not self.paths: raise ValueError('请先添加 RAW 或照片。')
            if not self.output_dir.get().strip(): raise ValueError('请选择输出文件夹。')
            folder = Path(self.output_dir.get().strip()).resolve()
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ('.filmcrop-' + uuid.uuid4().hex)
            probe.write_bytes(b''); probe.unlink()
            top, bottom = float(self.top_trim.get())/100, float(self.bottom_trim.get())/100
            margin = float(self.border_margin.get())/100
            side = float(self.sprocket_side.get())/100
            if not 0 <= side <= .1: raise ValueError('135 两侧留边范围为 0 至 10%。')
            if not 0 <= top < .1 or not 0 <= bottom < .1: raise ValueError('上下收边范围为 0 至小于 10%。')
            if not 0 <= margin <= .1: raise ValueError('120 边框扩展范围为 0 至 10%。')
            options = Options(format=FORMAT_CHOICES[self.format.get()],
                              output_format='TIFF16' if self.export.get() == '16 位 TIFF' else 'JPEG',
                              keep_border=self.keep.get(), auto_rotate=self.auto_rotate.get(), top_trim=top, bottom_trim=bottom, border_margin=margin, sprocket_side=side)
        except Exception as exc:
            messagebox.showerror('无法开始', str(exc), parent=self.root); return
        jobs, self.active_jobs = self.pending_jobs(folder, options)
        self.batch_skipped = len(self.paths)-len(jobs)
        if not jobs:
            self.status.set(f'已跳过 {self.batch_skipped} 个已完成文件。')
            return
        self.running = True; self.stop.clear()
        self.active_options={iid:replace(options,format=self.file_formats.get(iid,options.format)) for iid,_ in jobs}
        self.set_busy(True)
        for iid, source in jobs:
            self.outputs.pop(iid, None); self.completed.pop(iid, None)
            self.tree.item(iid, values=(source.name, '待处理', '—'))
        self.progress.configure(value=0, maximum=len(jobs))
        threading.Thread(target=self.worker, args=(jobs, folder, options), daemon=True).start()

    def set_busy(self, busy):
        for widget in [self.add_button, self.folder_button, self.clear_button, self.remove_button,
                       self.browse_button, self.path_entry, self.keep_check, self.rotate_check, self.more_button, self.start_button]:
            widget.configure(state='disabled' if busy else 'normal')
        for widget in [self.format_combo, self.export_combo]: widget.configure(state='disabled' if busy else 'readonly')
        self.cancel_button.configure(state='normal' if busy else 'disabled')
        if busy:
            for widget in self.trim_widgets + [self.margin_widget, self.side_widget]: widget.configure(state='disabled')
        else: self.mode_changed()

    def worker(self, jobs, folder, options):
        records = []; errors = 0; success = 0
        for index, (iid, path) in enumerate(jobs):
            if self.stop.is_set(): break
            self.events.put(('working', iid, path.name))
            try:
                record = process_file(path, folder, self.active_options.get(iid,options))
                records.append(record); success += 1
                self.events.put(('result', iid, record, index+1))
            except FormatRequired as exc:
                record={'source':str(path),'error':str(exc),'requires_format':True}
                records.append(record)
                self.events.put(('error',iid,record,index+1))
            except Exception as exc:
                errors += 1
                record = {'source': str(path), 'error': str(exc)}
                records.append(record)
                self.events.put(('error', iid, record, index+1))
        report = None; report_error = None
        try:
            name = 'FilmCrop_report_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
            report = folder / (name + '.json')
            report.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
            with (folder / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as fp:
                keys = ['source', 'output', 'format', 'measured_ratio', 'rotation_degrees', 'rotation_method', 'rotation_confident', 'output_width', 'output_height', 'output_ratio', 'keep_border', 'needs_review', 'review_reasons', 'error']
                writer = csv.DictWriter(fp, fieldnames=keys, extrasaction='ignore'); writer.writeheader(); writer.writerows(records)
        except Exception as exc: report_error = str(exc)
        self.events.put(('done', success, errors, len(jobs)-len(records), report, report_error))

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait(); kind = event[0]
                if kind == 'working':
                    _, iid, name = event
                    self.tree.item(iid, values=(name, '处理中', '—'))
                    self.status.set('正在处理 ' + name)
                elif kind == 'result':
                    _, iid, record, index = event
                    self.outputs[iid] = record
                    self.completed[iid] = self.active_jobs[iid]
                    state = '完成'
                    self.tree.item(iid, values=(self.paths[iid].name, state, FORMAT_LABELS[record['format']]))
                    self.progress.configure(value=index)
                    self.tree.selection_set(iid)
                elif kind == 'error':
                    _, iid, record, index = event
                    self.outputs[iid] = record
                    self.tree.item(iid, values=(self.paths[iid].name, '待指定画幅' if record.get('requires_format') else '失败', '—'))
                    self.progress.configure(value=index)
                elif kind == 'done':
                    _, success, errors, remaining, report, report_error = event
                    self.running = False; self.set_busy(False)
                    if remaining:
                        for iid in self.active_jobs:
                            if iid not in self.outputs: self.tree.item(iid, values=(self.paths[iid].name, '已停止', '—'))
                    self.status.set(f'完成 {success} 个，失败 {errors} 个，未处理 {remaining} 个。' +
                                    (f' 已跳过 {self.batch_skipped} 个已完成文件。' if self.batch_skipped else '') +
                                    ('' if not report_error else ' 报告写入失败：' + report_error))
                    if report_error: messagebox.showerror('报告写入失败', report_error, parent=self.root)
                    pending=[iid for iid in self.active_jobs if self.outputs.get(iid,{}).get('requires_format')]
                    if pending and not self.stop.is_set():self.ask_dark_formats(pending)
        except queue.Empty: pass
        self.root.after(100, self.poll)

    def ask_dark_formats(self, items):
        dialog=tk.Toplevel(self.root);dialog.title('指定画幅');dialog.transient(self.root)
        body=ttk.Frame(dialog,padding=16);body.pack(fill='both',expand=True)
        ttk.Label(body,text='以下图片亮度低、边界不完整。选择画幅后按可见边缘推算。').pack(anchor='w')
        choices={}
        for iid in items:
            row=ttk.Frame(body);row.pack(fill='x',pady=5)
            ttk.Label(row,text=self.paths[iid].name,width=38).pack(side='left')
            value=tk.StringVar(value='请选择')
            ttk.Combobox(row,textvariable=value,state='readonly',width=13,
                         values=list(FORMAT_LABELS.values())).pack(side='right')
            choices[iid]=value
        def apply():
            selected={iid:FORMAT_CHOICES[v.get()]
                      for iid,v in choices.items() if v.get()!='请选择'}
            if not selected:return
            self.file_formats.update(selected);dialog.destroy();self.start()
        ttk.Button(body,text='按所选画幅重试',command=apply).pack(side='right',pady=(10,0))
        ttk.Button(body,text='稍后处理',command=dialog.destroy).pack(side='right',padx=8,pady=(10,0))
        dialog.grab_set()

    def select_preview(self, _event=None):
        selection = self.tree.selection()
        if not selection: return
        record = self.outputs.get(selection[0])
        if not record: return
        if 'error' in record:
            self.preview.configure(image='', text='请指定画幅' if record.get('requires_format') else '此文件处理失败'); self.preview_photo = None
            self.detail.configure(text=record['error']); return
        try:
            with Image.open(record['output']) as image:
                image.thumbnail((210, 230))
                self.preview_photo = ImageTk.PhotoImage(image.convert('RGB'))
            self.preview.configure(image=self.preview_photo, text='')
            self.detail.configure(text=f"{record['format']}  ·  {record['output_width']} × {record['output_height']}\n内框宽高比 {record['measured_ratio']:.4f}\n转正角度 {record.get('rotation_degrees', 0):+.2f}°")
        except Exception as exc:
            self.detail.configure(text='预览失败：' + str(exc))

    def open_path(self, path):
        if sys.platform == 'win32': os.startfile(str(path))
        elif sys.platform == 'darwin': subprocess.Popen(['open', str(path)])
        else: subprocess.Popen(['xdg-open', str(path)])

    def open_selected(self, _event=None):
        selection = self.tree.selection()
        if selection:
            record = self.outputs.get(selection[0], {})
            if record.get('output'): self.open_path(record['output'])

    def cancel(self):
        self.stop.set(); self.status.set('将在当前文件处理完成后停止。')
        self.cancel_button.configure(state='disabled')

    def open_output(self):
        path = Path(self.output_dir.get())
        if self.output_dir.get() and path.is_dir(): self.open_path(path)

    def close(self):
        if self.running:
            self.cancel()
            messagebox.showinfo('正在处理', '已停止后续任务。请等当前文件保存完成后关闭。', parent=self.root)
        else: self.root.destroy()



def create_root():
    # Extended Windows paths avoid Tcl normalization of localized profile folders.
    import tkinterdnd2
    if sys.platform == 'win32':
        def long_path(path):
            path = str(Path(path).resolve()).replace('\\', '/')
            return path if path.startswith('//?/') else '//?/' + path
        if getattr(sys, 'frozen', False):
            os.environ['TCL_LIBRARY'] = long_path(Path(sys._MEIPASS) / '_tcl_data')
            os.environ['TK_LIBRARY'] = long_path(Path(sys._MEIPASS) / '_tk_data')
        root = tk.Tk()
        tcl_major = int(root.tk.call('info', 'tclversion').split('.')[0])
        variant = 'win-x64-tcl9' if tcl_major >= 9 else 'win-x64'
        module = long_path(Path(tkinterdnd2.__file__).parent / 'tkdnd' / variant)
        root.tk.call('lappend', 'auto_path', module)
        root.tk.call('package', 'require', 'tkdnd')
        # Importing tkinterdnd2 registers DnD methods on tkinter.BaseWidget.
        return root
    return TkinterDnD.Tk()


def main():
    # A packaged diagnostic mode runs the actual decoder and engine without UI.
    # It is also useful when reporting unsupported RAW files.
    if '--layout-test' in sys.argv:
        from film_diagnostic import layout_test
        layout_test(sys.argv[sys.argv.index('--layout-test')+1:]); return
    if '--diagnostic' in sys.argv:
        from film_diagnostic import main as diagnostic
        diagnostic(sys.argv[sys.argv.index('--diagnostic')+1:]); return
    root = create_root()
    app = FilmApp(root)
    if '--startup-test' in sys.argv:
        from film_diagnostic import startup_test
        startup_test(root, sys.argv[sys.argv.index('--startup-test')+1])
    # Optional local smoke-test: exercise Tcl drop parsing, controls and queue.
    if '--ui-smoke-test' in sys.argv:
        from film_diagnostic import ui_smoke_test
        ui_smoke_test(root, app, sys.argv[sys.argv.index('--ui-smoke-test')+1:])
    root.mainloop()


if __name__ == '__main__':
    main()
