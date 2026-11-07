"""Exercise the preview application's real Tk layout and export controls."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import time
import traceback
from PIL import ImageGrab, Image
import numpy as np
import tifffile
from film_gui import create_root
from film_gui_modern import ModernFilmApp

def main():
    check_args=sys.argv[sys.argv.index('--windows-preview-check')+1:] if '--windows-preview-check' in sys.argv else []
    report_dir=Path(check_args[0]) if check_args else Path(__file__).resolve().parent/'validation'
    source=Path(check_args[1]) if len(check_args)>1 else Path('F:/datatemp/007/_IMG3592.jpg')
    expected_format=check_args[2] if len(check_args)>2 else '5.6x2.4'
    report_dir.mkdir(exist_ok=True)
    root=create_root()
    app=ModernFilmApp(root)
    failures=[]
    root.report_callback_exception=lambda *exc: failures.append(''.join(traceback.format_exception(*exc)))
    report={'layouts':[]}

    def pump(seconds=.3):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            root.update()
            time.sleep(.015)
        assert not failures,failures

    def inspect():
        try:
            controls=['add_button','folder_button','remove_button','clear_button','format_combo',
                      'rotate_check','border_check','reset_button','export_combo','path_entry',
                      'choose_button','start_button','stop_button','open_button','lang_combo']
            for language in ('zh','en'):
                app.lang=language;app.refresh_language()
                fixed_fonts = {name: getattr(app,name).actual() for name in
                               ('ui_font','heading_font','latin_ui_font','brand_font')}
                fixed_panels = [app.left_panel.winfo_width(),app.right_panel.winfo_width()]
                for width,height in ((1440,900),(1080,675),(900,580)):
                    root.geometry(f'{width}x{height}+20+20');pump(.5)
                    row={'language':language,'window':root.winfo_geometry(),'scale':app.scale,'controls':{}}
                    for name in controls:
                        widget=getattr(app,name)
                        x=widget.winfo_rootx()-root.winfo_rootx();y=widget.winfo_rooty()-root.winfo_rooty()
                        w,h=widget.winfo_width(),widget.winfo_height()
                        row['controls'][name]=[x,y,w,h,widget.winfo_reqwidth(),widget.winfo_reqheight()]
                        assert widget.winfo_ismapped(),(name,row)
                        assert 0<=x and 0<=y and x+w<=root.winfo_width()+1 and y+h<=root.winfo_height()+1,(name,row)
                        assert h>=widget.winfo_reqheight(),(name,row)
                        if name not in ('path_entry','format_combo','export_combo'):
                            assert w>=widget.winfo_reqwidth(),(name,row)
                    report['layouts'].append(row)
                    if sys.platform == 'win32':
                        row['fonts'] = {name: getattr(app,name).actual() for name in fixed_fonts}
                        row['panels'] = [app.left_panel.winfo_width(),app.right_panel.winfo_width()]
                        assert row['fonts'] == fixed_fonts,(language,row['fonts'],fixed_fonts)
                        assert row['panels'] == fixed_panels,(language,row['panels'],fixed_panels)
                    ImageGrab.grab(window=root.winfo_id()).save(report_dir/f'{language}-{width}x{height}.png')
            report['font']={'chinese':app.chinese_font,'latin':app.latin_font}
            root.geometry('1080x675+20+20');app.lang='zh';app.refresh_language();pump()
            app.on_drop(SimpleNamespace(data=root.tk.call('list',str(source)),action='copy'))
            app.on_drop(SimpleNamespace(data=root.tk.call('list',str(source)),action='copy'))
            assert len(app.paths)==1
            until=time.monotonic()+30
            while app.preview_image is None and time.monotonic()<until:pump(.1)
            assert app.preview_image is not None
            if sys.platform == 'win32':
                # Exercise native Tk geometry with a decoded preview present.
                # Font/style changes must not be part of the resize path.
                calls = []
                apply_scale,apply_fonts = app._apply_scale,app._apply_font_scale
                def track_scale():
                    calls.append('layout');return apply_scale()
                def track_fonts():
                    calls.append('fonts');return apply_fonts()
                app._apply_scale,app._apply_font_scale = track_scale,track_fonts
                canvas_sizes = []
                start = time.perf_counter()
                for step in list(range(24))+list(reversed(range(24))):
                    root.geometry(f'{900+step*20}x{580+step*12}+20+20')
                    root.update()
                    canvas_sizes.append([app.canvas.winfo_width(),app.canvas.winfo_height()])
                pump(.1)
                report['continuous_resize'] = {'steps':len(canvas_sizes),
                    'seconds':time.perf_counter()-start,'font_or_layout_updates':calls,
                    'canvas_min':min(canvas_sizes),'canvas_max':max(canvas_sizes)}
                assert not calls,calls
                assert len({tuple(size) for size in canvas_sizes})>20,canvas_sizes
                app._apply_scale,app._apply_font_scale = apply_scale,apply_fonts
                root.geometry('1080x675+20+20');pump()
            app.keep_border.set(True);app.outdir.set(str(report_dir));app.export.set('JPEG');app.start()
            until=time.monotonic()+90
            while app.running and time.monotonic()<until:pump(.1)
            assert not app.running
            record=app.records[source];assert 'error' not in record,record
            assert record['format']==expected_format,record
            pixels=Image.open(record['output']);pixels.thumbnail((1000,1000));pixels.save(report_dir/'auto-border.jpg')
            Path(record['output']).unlink()
            report['automatic_export']=record
            app.keep_border.set(False)
            x,y,w,h=app.preview_rect
            app.drag_start(SimpleNamespace(x=x+.1*w,y=y+.15*h))
            app.drag_move(SimpleNamespace(x=x+.9*w,y=y+.85*h))
            app.drag_end(SimpleNamespace(x=x+.9*w,y=y+.85*h))
            assert source in app.boxes
            ImageGrab.grab(window=root.winfo_id()).save(report_dir/'manual-selection.png')
            app.export.set('TIFF16');app.start()
            until=time.monotonic()+90
            while app.running and time.monotonic()<until:pump(.1)
            assert not app.running
            record=app.records[source];assert record.get('mode')=='manual',record
            with tifffile.TiffFile(record['output']) as tif:
                assert tif.pages[0].dtype==np.uint16
            Path(record['output']).unlink()
            report['manual_export']=record
            report['passed']=True
        except Exception:
            report['error']=traceback.format_exc()
            ImageGrab.grab(window=root.winfo_id()).save(report_dir/'failure.png')
        finally:
            report['callback_errors']=failures
            (report_dir/'gui-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            root.destroy()
        print('GUI checks:', 'PASS' if report.get('passed') else report.get('error'),flush=True)
        if not report.get('passed'):raise SystemExit(1)

    root.after(200,inspect)
    root.mainloop()


if __name__ == '__main__':
    main()
