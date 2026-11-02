import errno
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _stub_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules.setdefault(name, module)
    return sys.modules[name]


_stub_module("numpy", uint8=object(), uint16=object())
_stub_module("cv2", IMWRITE_JPEG_QUALITY=1)
_stub_module("film_crop")
_stub_module("film_detect", detect_auto=lambda image: None, analyze=lambda image, fmt: None)
_stub_module("film_darkframe", FormatRequired=type("FormatRequired", (Exception,), {}))
_stub_module("tkinterdnd2", DND_FILES="DND_FILES", TkinterDnD=SimpleNamespace())
_stub_module(
    "tkinter",
    filedialog=SimpleNamespace(),
    messagebox=SimpleNamespace(),
    ttk=SimpleNamespace(),
)
_stub_module(
    "PIL",
    Image=SimpleNamespace(),
    ImageTk=SimpleNamespace(),
)

sys.modules["film_crop"].FORMAT_LABELS = {}
sys.modules["film_crop"].FORMAT_CHOICES = {}

import film_engine
import film_io
import film_gui


class _EncodedBytes:
    def __init__(self, payload=b"new"):
        self.payload = payload

    def tofile(self, path):
        Path(path).write_bytes(self.payload)


class OutputIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=Path(__file__).parent
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.folder = Path(self.temporary_directory.name)

    def test_write_image_rejects_existing_destination_before_encoding(self):
        destination = self.folder / "IMG_crop.jpg"
        destination.write_bytes(b"original")

        with (
            mock.patch.object(film_io, "detection_image", side_effect=lambda image: image),
            mock.patch.object(
                film_io.cv2,
                "imencode",
                return_value=(True, _EncodedBytes()),
                create=True,
            ) as encode,
        ):
            with self.assertRaises(FileExistsError):
                film_io.write_image(destination, object(), "JPEG")

        encode.assert_not_called()
        self.assertEqual(destination.read_bytes(), b"original")

    def test_write_image_rechecks_destination_before_replace(self):
        destination = self.folder / "IMG_crop.jpg"

        def encode_after_competitor(*args, **kwargs):
            destination.write_bytes(b"competitor")
            return True, _EncodedBytes()

        with (
            mock.patch.object(film_io, "detection_image", side_effect=lambda image: image),
            mock.patch.object(
                film_io.cv2,
                "imencode",
                side_effect=encode_after_competitor,
                create=True,
            ),
        ):
            with self.assertRaises(FileExistsError):
                film_io.write_image(destination, object(), "JPEG")

        self.assertEqual(destination.read_bytes(), b"competitor")
        self.assertEqual(list(self.folder.glob(".*.tmp")), [])

    def test_write_image_does_not_overwrite_destination_created_after_final_check(self):
        destination = self.folder / "IMG_crop.jpg"
        checks = 0
        original_check = film_io.require_output_available

        def create_competitor_after_final_check(path):
            nonlocal checks
            result = original_check(path)
            checks += 1
            if checks == 2:
                destination.write_bytes(b"competitor")
            return result

        with (
            mock.patch.object(
                film_io,
                "require_output_available",
                side_effect=create_competitor_after_final_check,
            ),
            mock.patch.object(film_io, "detection_image", side_effect=lambda image: image),
            mock.patch.object(
                film_io.cv2,
                "imencode",
                return_value=(True, _EncodedBytes()),
                create=True,
            ),
        ):
            with self.assertRaises(FileExistsError):
                film_io.write_image(destination, object(), "JPEG")

        self.assertEqual(checks, 2)
        self.assertEqual(destination.read_bytes(), b"competitor")
        self.assertEqual(list(self.folder.glob(".*.tmp")), [])

    def test_write_image_falls_back_when_hard_links_are_unsupported(self):
        destination = self.folder / "IMG_crop.jpg"

        with (
            mock.patch.object(
                film_io.os,
                "link",
                side_effect=OSError(errno.ENOTSUP, "hard links unsupported"),
            ),
            mock.patch.object(film_io, "detection_image", side_effect=lambda image: image),
            mock.patch.object(
                film_io.cv2,
                "imencode",
                return_value=(True, _EncodedBytes()),
                create=True,
            ),
        ):
            try:
                film_io.write_image(destination, object(), "JPEG")
            except OSError as exc:
                self.fail(f"hard-link failure did not fall back: {exc}")

        self.assertEqual(destination.read_bytes(), b"new")
        self.assertEqual(list(self.folder.glob(".*.tmp")), [])

    def _run_process_file(self, source, *, output=None, options=None):
        image = SimpleNamespace(shape=(120, 180, 3))
        result = SimpleNamespace(shape=(100, 150, 3))
        metadata = {
            "source_type": "raster",
            "source_bit_depth": 8,
            "rendering": "test",
        }
        detection = {
            "format": "135/6x9",
            "ratio": 1.5,
            "measured_ratio": 1.5,
            "bounds": [0, 179, 0, 119],
            "negative_hint": False,
            "needs_review": False,
            "review_reasons": [],
        }
        options = options or film_engine.Options()

        with (
            mock.patch.object(film_engine, "read_image", return_value=(image, metadata)),
            mock.patch.object(film_engine, "locate", return_value=detection),
            mock.patch.object(film_engine, "crop_pixels", return_value=result),
            mock.patch.object(film_engine, "write_image") as writer,
        ):
            if output is None:
                record = film_engine.process_file(source, self.folder, options)
            else:
                record = film_engine.process_file(
                    source, self.folder, options, output=output
                )

        return record, writer

    def test_process_file_uses_supplied_output_path(self):
        source = self.folder / "source.ARW"
        supplied = self.folder / "chosen-name.tif"

        _, writer = self._run_process_file(source, output=supplied)

        self.assertEqual(writer.call_args.args[0], supplied)

    def test_process_file_records_actual_output_path(self):
        source = self.folder / "source.ARW"
        supplied = self.folder / "chosen-name.tif"

        record, _ = self._run_process_file(source, output=supplied)

        self.assertEqual(record["output"], str(supplied))

    def test_process_file_without_override_avoids_existing_output(self):
        source = self.folder / "source.ARW"
        occupied = self.folder / "source_crop.tif"
        occupied.write_bytes(b"original")

        record, writer = self._run_process_file(source)

        planned = self.folder / "source_crop_2.tif"
        self.assertEqual(writer.call_args.args[0], planned)
        self.assertEqual(record["output"], str(planned))
        self.assertEqual(occupied.read_bytes(), b"original")

    def test_gui_plan_assigns_unique_paths_to_duplicate_stems(self):
        app = object.__new__(film_gui.FilmApp)
        app.active_options = {
            "first": film_engine.Options(),
            "second": film_engine.Options(),
        }
        jobs = [
            ("first", self.folder / "roll-a" / "IMG_0001.ARW"),
            ("second", self.folder / "roll-b" / "IMG_0001.ARW"),
        ]

        outputs = app.plan_job_outputs(jobs, self.folder)

        self.assertEqual(
            outputs,
            {
                "first": self.folder / "IMG_0001_crop.tif",
                "second": self.folder / "IMG_0001_crop_2.tif",
            },
        )

    def test_gui_plan_respects_each_jobs_format_and_border_suffix(self):
        app = object.__new__(film_gui.FilmApp)
        app.active_options = {
            "border": film_engine.Options(output_format="JPEG", keep_border=True),
            "crop": film_engine.Options(output_format="TIFF16", keep_border=False),
        }
        jobs = [
            ("border", self.folder / "border-source.ARW"),
            ("crop", self.folder / "crop-source.ARW"),
        ]

        outputs = app.plan_job_outputs(jobs, self.folder)

        self.assertEqual(outputs["border"], self.folder / "border-source_border.jpg")
        self.assertEqual(outputs["crop"], self.folder / "crop-source_crop.tif")

    def test_worker_passes_planned_path_to_engine(self):
        app = object.__new__(film_gui.FilmApp)
        app.stop = SimpleNamespace(is_set=lambda: False)
        app.events = __import__("queue").Queue()
        source = self.folder / "source.ARW"
        planned = self.folder / "source_crop.tif"
        options = film_engine.Options()
        app.active_options = {"job": options}
        app.active_outputs = {"job": planned}

        with mock.patch.object(
            film_gui,
            "process_file",
            return_value={"source": str(source), "output": str(planned)},
        ) as process:
            app.worker([("job", source)], self.folder, options)

        process.assert_called_once_with(source, self.folder, options, output=planned)


if __name__ == "__main__":
    unittest.main()
