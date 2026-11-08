import queue
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from film_darkframe import FormatRequired
from film_engine import Options
from film_gui_modern import ModernFilmApp


class DeferredBatchTests(unittest.TestCase):
    def test_reopen_only_lists_unresolved_files_still_in_batch(self):
        from unittest.mock import Mock
        app = ModernFilmApp.__new__(ModernFilmApp)
        pending, done, removed = map(Path, ('pending.jpg', 'done.jpg', 'removed.jpg'))
        app.paths = [pending, done]
        app.records = {p: {'requires_format':True} for p in (pending, done, removed)}
        app.states = {pending:'needs_format', done:'done', removed:'needs_format'}
        app.running = False
        app.ask_dark_formats = Mock()
        app.open_pending_formats()
        app.ask_dark_formats.assert_called_once_with([pending])
        app.running = True
        app.open_pending_formats()
        self.assertEqual(app.ask_dark_formats.call_count, 1)

    def test_deferred_is_separate_from_failure_and_batch_continues(self):
        app = ModernFilmApp.__new__(ModernFilmApp)
        app.stop = threading.Event()
        app.jobs = queue.Queue()
        paths = [Path('dark.jpg'), Path('good.jpg'), Path('broken.jpg')]
        app.active_options = {p: Options() for p in paths}
        with TemporaryDirectory() as folder, patch('film_gui_modern.export_one',
                side_effect=[FormatRequired('choose'), {'output':'good.jpg'}, ValueError('broken')]) as export:
            app.worker([(p, None) for p in paths], Path(folder), Options())
        events = list(app.jobs.queue)
        results = [event for event in events if event[0] == 'result']
        self.assertTrue(results[0][2]['requires_format'])
        self.assertIsNone(results[1][3])
        self.assertNotIn('requires_format', results[2][2])
        self.assertEqual(export.call_count, 3)
        self.assertEqual(events[-1][1:4], (1, 1, 0))

    def test_retry_uses_per_image_format(self):
        app = ModernFilmApp.__new__(ModernFilmApp)
        app.stop = threading.Event()
        app.jobs = queue.Queue()
        path = Path('dark.jpg')
        app.active_options = {path: Options(format='6x6')}
        with TemporaryDirectory() as folder, patch('film_gui_modern.export_one', return_value={}) as export:
            app.worker([(path, None)], Path(folder), Options())
        self.assertEqual(export.call_args.args[2].format, '6x6')
