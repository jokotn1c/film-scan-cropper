"""Behavioral coverage for entry compatibility and atomic output policies."""
import contextlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import tifffile

import film_crop
from film_engine import Options, process_file, crop_pixels
from film_io import read_image, write_output
from film_modern_export import export_one
from film_pipeline import process_image


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input.tif'
        self.image = np.arange(80 * 120 * 3, dtype=np.uint16).reshape(80, 120, 3)
        tifffile.imwrite(self.source, self.image[:, :, ::-1], photometric='rgb')
        self.detection = dict(format='135/6x9', ratio=1.5, measured_ratio=1.5,
                              bounds=[10, 106, 8, 72], needs_review=False,
                              review_reasons=[], rotation_degrees=0.)

    def pixels(self, record):
        return tifffile.imread(record['output'])[:, :, ::-1]

    def test_three_entries_decode_once_and_export_identical_pixels(self):
        options = Options(format='135/6x9', collision_policy='overwrite')
        with patch('film_pipeline.locate', return_value=self.detection), \
             patch('film_pipeline.read_image', wraps=read_image) as decode:
            classic = process_file(self.source, self.root / 'classic', options)
            modern = export_one(self.source, self.root / 'modern', options)
            with contextlib.redirect_stdout(io.StringIO()):
                cli = film_crop.process_one(self.source, self.root / 'cli.tif',
                    1.5, None, 0., '135/6x9', False, None, output_format='TIFF16')
        self.assertEqual(decode.call_count, 3)
        expected = crop_pixels(self.image, self.detection, options)
        for record in (classic, modern, cli):
            np.testing.assert_array_equal(self.pixels(record), expected)
            self.assertEqual(record['source_bit_depth'], 16)
            self.assertEqual(record['output_ratio'], expected.shape[1] / expected.shape[0])
            self.assertEqual(set(record['timings']), {'read', 'detect', 'crop', 'write', 'total'})

    def test_manual_box_preserves_pixels_and_bypasses_automatic_settings(self):
        options = Options(manual_box=(.25, .25, .75, .75), keep_border=True)
        with patch('film_pipeline.locate', side_effect=AssertionError('unexpected detection')):
            record = process_file(self.source, self.root / 'out', options)
        np.testing.assert_array_equal(self.pixels(record), self.image[20:60, 30:90])
        self.assertEqual(record['mode'], 'manual')
        self.assertFalse(record['keep_border'])
        self.assertEqual(record['top_trim'], 0.)

    def test_explicit_corners_ratio_orientation_padding_and_sprockets(self):
        corners = ((20, 20), (98, 20), (98, 60), (20, 60))
        for orientation in ('landscape', 'portrait'):
            for sprockets in (False, True):
                with self.subTest(orientation=orientation, sprockets=sprockets):
                    options = Options(format='135/6x9', corners=corners, ratio=1.6,
                        orientation=orientation, padding=.015, keep_sprockets=sprockets,
                        sprocket_margins=(.1, .04, .12, .03))
                    ratio = film_crop.oriented_ratio(self.image, 1.6, orientation)
                    quad = corners
                    if sprockets:
                        quad = film_crop.expand_for_sprockets(quad, self.image.shape[:2],
                            options.format, options.sprocket_margins)
                        ratio = film_crop.SPROCKET_RATIO_135 if ratio >= 1 else 1 / film_crop.SPROCKET_RATIO_135
                    expected = film_crop.perspective_crop(self.image, quad, ratio, padding=.015)
                    if not sprockets:
                        expected = film_crop.trim_borders(expected, ratio, .01, .01)
                    with patch('film_pipeline.locate', side_effect=AssertionError('unexpected detection')):
                        record = process_image(self.source, self.root / 'out', options)
                    np.testing.assert_array_equal(self.pixels(record), expected)

    def test_custom_ratio_uses_legacy_frame_search(self):
        with patch('film_pipeline.locate', side_effect=AssertionError('unexpected detection')), \
             patch('film_crop.detect_frame', return_value=(10, 90, 10, 60)) as detect:
            process_image(self.source, self.root / 'out', Options(format='135/6x9', ratio=1.6))
        detect.assert_called_once()
        self.assertEqual(detect.call_args.args[1], 1.6)

    def test_modern_numbers_by_default_classic_overwrites(self):
        folder = self.root / 'out'
        options = Options(manual_box=(.25, .25, .75, .75))
        first = export_one(self.source, folder, options)
        target = Path(first['output'])
        target.write_bytes(b'previous')
        second = export_one(self.source, folder, options)
        self.assertEqual(Path(second['output']).name, 'input_crop_2.tif')
        self.assertEqual(target.read_bytes(), b'previous')
        third = process_file(self.source, folder, options)
        self.assertEqual(Path(third['output']), target)
        self.assertNotEqual(target.read_bytes(), b'previous')

    def test_skip_and_error_do_not_decode_existing_output(self):
        target = self.root / 'existing.tif'
        target.write_bytes(b'previous')
        with patch('film_pipeline.read_image', side_effect=AssertionError('unexpected decode')):
            record = process_image(self.source, output=target, options=Options(collision_policy='skip'))
            self.assertTrue(record['skipped'])
            with self.assertRaises(FileExistsError):
                process_image(self.source, output=target, options=Options(collision_policy='error'))
        self.assertEqual(target.read_bytes(), b'previous')

    def test_original_path_and_hardlink_are_protected_for_every_policy(self):
        link = self.root / 'link.tif'
        link.hardlink_to(self.source)
        for target in (self.source, link):
            for policy in ('overwrite', 'number', 'skip', 'error'):
                with self.subTest(target=target, policy=policy), self.assertRaises(ValueError):
                    process_image(self.source, output=target, options=Options(collision_policy=policy))
        np.testing.assert_array_equal(read_image(self.source)[0], self.image)

    def test_encoding_failure_keeps_previous_output_and_cleans_temp(self):
        target = self.root / 'existing.tif'
        target.write_bytes(b'previous')
        def failed_write(path, *args, **kwargs):
            Path(path).write_bytes(b'incomplete')
            raise OSError('encoding failed')
        with patch('tifffile.imwrite', side_effect=failed_write), self.assertRaises(OSError):
            write_output(target, self.image)
        self.assertEqual(target.read_bytes(), b'previous')
        self.assertEqual(list(self.root.glob('.*.tmp')), [])

    def test_concurrent_numbered_exports_preserve_each_output(self):
        target = self.root / 'result.tif'
        def save(index):
            return write_output(target, self.image + index, collision_policy='number')
        with ThreadPoolExecutor(max_workers=4) as pool:
            outputs = list(pool.map(save, range(4)))
        self.assertEqual(len({path for path, _ in outputs}), 4)
        for index, (path, skipped) in enumerate(outputs):
            self.assertFalse(skipped)
            np.testing.assert_array_equal(tifffile.imread(path)[:, :, ::-1], self.image + index)

    def test_collision_during_commit_obeys_skip_and_error(self):
        import os
        actual_link = os.link
        for policy in ('skip', 'error'):
            target = self.root / (policy + '.tif')
            def competing_link(source, dest):
                Path(dest).write_bytes(b'winner')
                actual_link(source, dest)
            with patch('film_io.os.link', side_effect=competing_link):
                if policy == 'error':
                    with self.assertRaises(FileExistsError):
                        write_output(target, self.image, collision_policy=policy)
                else:
                    self.assertTrue(write_output(target, self.image, collision_policy=policy)[1])
            self.assertEqual(target.read_bytes(), b'winner')
            self.assertEqual(list(self.root.glob('.*.tmp')), [])

    def test_raw_tiff_preserves_depth_and_embeds_srgb_profile(self):
        metadata = dict(source_type='RAW', source_bit_depth=16)
        options = Options(manual_box=(0., 0., 1., 1.))
        with patch('film_pipeline.read_image', return_value=(self.image, metadata)):
            record = process_image(self.root / 'camera.ARW', self.root / 'out', options)
        np.testing.assert_array_equal(self.pixels(record), self.image)
        with tifffile.TiffFile(record['output']) as tiff:
            self.assertEqual(tiff.pages[0].dtype, np.uint16)
            self.assertTrue(tiff.pages[0].tags[34675].value)

    def test_automatic_output_format(self):
        options = Options(output_format='auto', manual_box=(0., 0., 1., 1.))
        record = process_image(self.source, self.root / 'out', options)
        self.assertEqual(record['output_format'], 'JPEG')
        record = process_image(self.source, output=self.root / 'explicit.tif', options=options)
        self.assertEqual(record['output_format'], 'TIFF16')

    def test_folder_cli_forwards_rotation_and_collision_options(self):
        args = ['film_crop.py', str(self.root), '--no-auto-rotate', '--existing', 'skip']
        with patch('sys.argv', args), patch('film_crop.process_one') as process:
            film_crop.main()
        self.assertEqual(process.call_count, 1)
        self.assertIs(process.call_args.args[-2], False)
        self.assertEqual(process.call_args.args[-1], 'skip')

    def test_invalid_options_fail_before_decode(self):
        for options in (Options(collision_policy='bad'), Options(ratio=float('nan')),
                        Options(corners=((0., 0.),)), Options(padding=.5)):
            with patch('film_pipeline.read_image', side_effect=AssertionError('unexpected decode')), \
                 self.assertRaises(ValueError):
                process_image(self.source, self.root / 'out', options)


if __name__ == '__main__':
    unittest.main()
