import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


def _stub_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules.setdefault(name, module)


_stub_module("numpy", uint8=object(), uint16=object())
_stub_module("cv2", IMWRITE_JPEG_QUALITY=1)

import film_crop


class CliOutputPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=Path(__file__).parent
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.folder = Path(self.temporary_directory.name)

    def _run_main(self, *arguments):
        with (
            mock.patch.object(sys, "argv", ["film_crop.py", *map(str, arguments)]),
            mock.patch.object(film_crop, "process_one") as process,
        ):
            film_crop.main()
        return process

    def test_explicit_existing_output_fails_before_process_one(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")
        output = self.folder / "chosen.jpg"
        output.write_bytes(b"original")

        with (
            mock.patch.object(
                sys,
                "argv",
                ["film_crop.py", str(source), "--output", str(output)],
            ),
            mock.patch.object(film_crop, "process_one") as process,
        ):
            with self.assertRaises(FileExistsError):
                film_crop.main()

        process.assert_not_called()
        self.assertEqual(output.read_bytes(), b"original")

    def test_implicit_single_output_gets_numbered_name(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")
        occupied = self.folder / "source_135_6x9.jpg"
        occupied.write_bytes(b"original")

        process = self._run_main(source)

        self.assertEqual(
            process.call_args.args[1],
            self.folder / "source_135_6x9_2.jpg",
        )
        self.assertEqual(occupied.read_bytes(), b"original")

    def test_folder_outputs_are_planned_before_processing(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        (source_folder / "frame.jpg").write_bytes(b"jpg")
        (source_folder / "frame.png").write_bytes(b"png")
        output_folder = self.folder / "outputs"
        events = []

        def record_plan(candidates):
            candidates = list(candidates)
            events.append(("plan", len(candidates)))
            return candidates

        with (
            mock.patch.object(
                sys,
                "argv",
                [
                    "film_crop.py",
                    str(source_folder),
                    "--output-dir",
                    str(output_folder),
                ],
            ),
            mock.patch(
                "film_paths.plan_output_paths",
                side_effect=record_plan,
            ),
            mock.patch.object(
                film_crop,
                "process_one",
                side_effect=lambda *args, **kwargs: events.append(("process", args[0])),
            ),
        ):
            film_crop.main()

        self.assertEqual(events[0], ("plan", 2))
        self.assertEqual([event[0] for event in events], ["plan", "process", "process"])

    def test_folder_plan_skips_existing_numbered_outputs(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        (source_folder / "frame.jpg").write_bytes(b"jpg")
        (source_folder / "frame.png").write_bytes(b"png")
        output_folder = self.folder / "outputs"
        output_folder.mkdir()
        base = output_folder / "frame_135_6x9.jpg"
        numbered = output_folder / "frame_135_6x9_2.jpg"
        base.write_bytes(b"base")
        numbered.write_bytes(b"numbered")

        process = self._run_main(
            source_folder,
            "--output-dir",
            output_folder,
        )

        self.assertEqual(
            [call.args[1] for call in process.call_args_list],
            [
                output_folder / "frame_135_6x9_3.jpg",
                output_folder / "frame_135_6x9_4.jpg",
            ],
        )
        self.assertEqual(base.read_bytes(), b"base")
        self.assertEqual(numbered.read_bytes(), b"numbered")

    def test_folder_no_auto_rotate_disables_rotation_for_every_file(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        (source_folder / "first.jpg").write_bytes(b"first")
        (source_folder / "second.png").write_bytes(b"second")

        process = self._run_main(source_folder, "--no-auto-rotate")

        self.assertEqual(
            [call.kwargs.get("auto_rotate") for call in process.call_args_list],
            [False, False],
        )

    def test_folder_auto_rotate_remains_enabled_by_default(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        (source_folder / "first.jpg").write_bytes(b"first")
        (source_folder / "second.png").write_bytes(b"second")

        process = self._run_main(source_folder)

        self.assertEqual(
            [call.kwargs.get("auto_rotate") for call in process.call_args_list],
            [True, True],
        )


if __name__ == "__main__":
    unittest.main()
