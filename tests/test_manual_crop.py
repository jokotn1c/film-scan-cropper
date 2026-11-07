import unittest
import numpy as np
from film_manual import normalize_box, crop_manual, translate

class ManualCropTests(unittest.TestCase):
    def test_reversed_drag_and_clamping(self):
        self.assertEqual(normalize_box((0.8, 1.2), (-0.2, 0.25)), (0.0, 0.25, 0.8, 1.0))

    def test_reject_small_selection(self):
        with self.assertRaises(ValueError):
            normalize_box((.1, .1), (.10001, .8))

    def test_crop_uses_exact_pixel_bounds_and_depth(self):
        image = np.arange(100 * 200 * 3, dtype=np.uint16).reshape(100, 200, 3)
        result = crop_manual(image, (.25, .2, .75, .8))
        np.testing.assert_array_equal(result, image[20:80, 50:150])
        self.assertEqual(result.dtype, np.uint16)

    def test_both_locales_cover_same_keys(self):
        self.assertEqual(set(translate('zh')), set(translate('en')))
        self.assertEqual(translate('en')['start'], 'Start cropping')

if __name__ == '__main__': unittest.main()

class ExportTests(unittest.TestCase):
    def test_manual_export_does_not_overwrite(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        from film_modern_export import export_one
        from film_engine import Options
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'input.jpg'
            Image.new('RGB', (100, 80), (150, 40, 30)).save(source)
            dest = root / 'out'; dest.mkdir()
            old = dest / 'input_crop.jpg'; old.write_bytes(b'preserve')
            record = export_one(source, dest, Options(output_format='JPEG'), (.1, .25, .9, .75))
            self.assertEqual(old.read_bytes(), b'preserve')
            with Image.open(record['output']) as im:
                self.assertEqual(im.size, (80, 40))
            self.assertEqual(record['mode'], 'manual')

class DragInteractionTests(unittest.TestCase):
    def test_drag_and_resize_are_recorded_for_selected_image(self):
        from types import SimpleNamespace
        from film_gui_modern import ModernFilmApp
        fake = SimpleNamespace(scale=1.0, running=False, preview_rect=(10, 20, 200, 100), current='frame',
                               boxes={}, states={}, drag_anchor=None, drag_corner=None, drag_box=None,
                               update_list=lambda: None, redraw=lambda: None)
        fake.point = lambda event: ModernFilmApp.point(fake, event)
        ModernFilmApp.drag_start(fake, SimpleNamespace(x=50, y=40))
        ModernFilmApp.drag_move(fake, SimpleNamespace(x=170, y=100))
        ModernFilmApp.drag_end(fake, SimpleNamespace(x=170, y=100))
        self.assertEqual(fake.boxes['frame'], (.2, .2, .8, .8))
        ModernFilmApp.drag_start(fake, SimpleNamespace(x=50, y=40))
        ModernFilmApp.drag_end(fake, SimpleNamespace(x=70, y=50))
        self.assertEqual(fake.boxes['frame'], (.3, .3, .8, .8))
