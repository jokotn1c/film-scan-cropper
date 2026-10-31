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

import film_engine
import film_io


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


if __name__ == "__main__":
    unittest.main()
