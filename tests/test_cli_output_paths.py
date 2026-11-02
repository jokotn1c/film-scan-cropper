import contextlib
import io
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

    def _run_main_error(self, *arguments):
        stderr = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["film_crop.py", *map(str, arguments)]),
            mock.patch.object(film_crop, "process_one") as process,
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            film_crop.main()
        self.assertEqual(raised.exception.code, 2)
        return process, stderr.getvalue()

    def _run_main_capture(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = None
        with (
            mock.patch.object(sys, "argv", ["film_crop.py", *map(str, arguments)]),
            mock.patch.object(film_crop, "process_one") as process,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            try:
                film_crop.main()
            except SystemExit as exc:
                exit_code = exc.code
        return process, stdout.getvalue(), exit_code

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

    def test_dry_run_single_prints_numbered_plan_without_processing(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")
        occupied = self.folder / "source_135_6x9.jpg"
        occupied.write_bytes(b"existing")

        process, output, exit_code = self._run_main_capture(source, "--dry-run")

        self.assertIsNone(exit_code)
        process.assert_not_called()
        planned = self.folder / "source_135_6x9_2.jpg"
        self.assertEqual(output, f"PLAN {source} -> {planned}\n")

    def test_dry_run_folder_prints_unique_plan_without_writes(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        first = source_folder / "frame.jpg"
        second = source_folder / "frame.png"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        output_folder = self.folder / "planned-outputs"

        process, output, exit_code = self._run_main_capture(
            source_folder,
            "--output-dir",
            output_folder,
            "--dry-run",
        )

        self.assertIsNone(exit_code)
        process.assert_not_called()
        self.assertFalse(output_folder.exists())
        self.assertEqual(
            output.splitlines(),
            [
                f"PLAN {first} -> {output_folder / 'frame_135_6x9.jpg'}",
                f"PLAN {second} -> {output_folder / 'frame_135_6x9_2.jpg'}",
            ],
        )

    def test_dry_run_explicit_existing_output_still_fails(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")
        output = self.folder / "chosen.jpg"
        output.write_bytes(b"original")

        with (
            mock.patch.object(
                sys,
                "argv",
                [
                    "film_crop.py",
                    str(source),
                    "--output",
                    str(output),
                    "--dry-run",
                ],
            ),
            mock.patch.object(film_crop, "process_one") as process,
        ):
            with self.assertRaises(FileExistsError):
                try:
                    film_crop.main()
                except SystemExit as exc:
                    self.fail(f"--dry-run was rejected with exit code {exc.code}")

        process.assert_not_called()
        self.assertEqual(output.read_bytes(), b"original")

    def test_explicit_auto_output_rejects_unsupported_extension(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")

        process, error = self._run_main_error(
            source,
            "--output",
            self.folder / "result.png",
        )

        process.assert_not_called()
        self.assertIn(".jpg, .jpeg, .tif, or .tiff", error)

    def test_explicit_auto_output_rejects_missing_extension(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")

        process, error = self._run_main_error(
            source,
            "--output",
            self.folder / "result",
        )

        process.assert_not_called()
        self.assertIn(".jpg, .jpeg, .tif, or .tiff", error)

    def test_explicit_output_format_rejects_mismatched_extension(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")
        cases = [
            ("JPEG", self.folder / "result.tif", ".jpg or .jpeg"),
            ("TIFF16", self.folder / "result.jpg", ".tif or .tiff"),
        ]

        for output_format, output, expected_error in cases:
            with self.subTest(output_format=output_format):
                process, error = self._run_main_error(
                    source,
                    "--output",
                    output,
                    "--output-format",
                    output_format,
                )
                process.assert_not_called()
                self.assertIn(expected_error, error)

    def test_explicit_auto_output_accepts_supported_extensions(self):
        source = self.folder / "source.jpg"
        source.write_bytes(b"source")
        cases = [
            ("result.jpg", "JPEG"),
            ("result.jpeg", "JPEG"),
            ("result.tif", "TIFF16"),
            ("result.tiff", "TIFF16"),
            ("result.JPEG", "JPEG"),
            ("result.TIFF", "TIFF16"),
        ]

        for name, expected_format in cases:
            with self.subTest(name=name):
                process = self._run_main(
                    source,
                    "--output",
                    self.folder / name,
                )
                self.assertEqual(process.call_args.args[11], expected_format)

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

    def test_folder_rejects_output_directory_equal_to_input(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        (source_folder / "frame.jpg").write_bytes(b"source")
        child = source_folder / "child"
        child.mkdir()
        equivalent_output = child / ".."

        process, error = self._run_main_error(
            source_folder,
            "--output-dir",
            equivalent_output,
        )

        process.assert_not_called()
        self.assertIn("different from the input folder", error)

    def test_folder_rejects_existing_file_as_output_directory(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        (source_folder / "frame.jpg").write_bytes(b"source")
        output_file = self.folder / "not-a-directory"
        output_file.write_bytes(b"occupied")

        process, error = self._run_main_error(
            source_folder,
            "--output-dir",
            output_file,
        )

        process.assert_not_called()
        self.assertIn("must be a directory", error)

    def test_folder_default_child_output_directory_remains_allowed(self):
        source_folder = self.folder / "sources"
        source_folder.mkdir()
        source = source_folder / "frame.jpg"
        source.write_bytes(b"source")

        process = self._run_main(source_folder)

        self.assertEqual(process.call_count, 1)
        self.assertEqual(
            process.call_args.args[1].parent,
            source_folder / "cropped",
        )

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
