"""Diagnostic entry points, also bundled to verify the finished executable."""
import argparse
import json
from pathlib import Path
import traceback


def main(argv=None):
    from film_engine import Options, process_file
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--keep-border', action='store_true')
    parser.add_argument('--jpeg', action='store_true')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        record = process_file(args.source, args.output,
                              Options(keep_border=args.keep_border, output_format='JPEG' if args.jpeg else 'TIFF16'))
    except Exception:
        record = {'error': traceback.format_exc()}
    (args.output/'diagnostic.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


def ui_smoke_test(root, app, argv):
    """Exercise the same drop callback, queue, preview and save controls as the UI."""
    from types import SimpleNamespace
    source, destination, report = map(Path, argv[:3])
    results = {}
    def run():
        try:
            app.on_drop(SimpleNamespace(data=root.tk.call('list', str(source)), action='copy'))
            app.on_drop(SimpleNamespace(data=root.tk.call('list', str(source)), action='copy'))
            assert len(app.paths) == 1
            results['drop_and_deduplicate'] = True
            app.keep.set(True); app.mode_changed()
            assert str(app.trim_widgets[0]['state']) == 'disabled'
            app.keep.set(False); app.mode_changed()
            app.output_dir.set(str(destination))
            app.start()
            root.after(300, check)
        except Exception:
            results['error'] = traceback.format_exc(); finish()
    def check():
        if app.running: root.after(300, check); return
        try:
            assert len(app.outputs) == 1
            record = next(iter(app.outputs.values()))
            assert 'error' not in record, record
            assert Path(record['output']).is_file()
            app.select_preview()
            assert app.preview_photo is not None
            results.update({'worker_and_export': True, 'preview': True, 'record': record})
        except Exception: results['error'] = traceback.format_exc()
        finish()
    def finish():
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        root.destroy()
    root.after(100, run)


if __name__ == '__main__': main()


def layout_test(argv):
    from film_gui import create_root, FilmApp
    rows=[]
    for scale in [1.,1.333333,1.666667,2.]:
     root=create_root();root.tk.call('tk','scaling',scale);app=FilmApp(root)
     for expanded in [False,True]:
      if app.advanced_open!=expanded:app.toggle_advanced()
      for size in ['800x470','900x620','1120x800']:
       root.geometry(size);root.update()
       widgets=[app.start_button,app.cancel_button,app.open_button,app.more_button,app.keep_check,app.rotate_check,app.export_combo,app.drop]
       if expanded:widgets+=app.trim_widgets+[app.margin_widget,app.side_widget]
       bounds=[]
       for w in widgets:
        x=w.winfo_rootx()-root.winfo_rootx();y=w.winfo_rooty()-root.winfo_rooty();ww=w.winfo_width();hh=w.winfo_height()
        assert hh>=w.winfo_reqheight(),(str(w),hh,w.winfo_reqheight())
        assert x>=0 and y>=0 and x+ww<=root.winfo_width() and y+hh<=root.winfo_height(),(str(w),x,y,ww,hh,root.winfo_geometry())
        bounds.append([x,y,ww,hh])
       assert app.middle.winfo_height()>=120
       rows.append(dict(scale=scale,expanded=expanded,requested=size,actual=root.winfo_geometry(),bounds=bounds))
     for cb in root.tk.call('after','info'):root.after_cancel(cb)
     root.destroy()
    report = Path(argv[0]); report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(rows, indent=2), encoding='utf8')
