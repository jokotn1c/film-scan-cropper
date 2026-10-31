import tempfile
import unittest
from pathlib import Path

from film_paths import output_path, plan_output_paths, require_output_available


class FilmPathsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=Path(__file__).parent
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.folder = Path(self.temporary_directory.name)

    def test_output_path_builds_expected_generated_name(self):
        source = self.folder / "source.ARW"

        self.assertEqual(
            output_path(self.folder, source, "TIFF16", "border"),
            self.folder / "source_border.tif",
        )
        self.assertEqual(
            output_path(self.folder, source, "JPEG"),
            self.folder / "source_crop.jpg",
        )

    def test_keeps_free_candidate(self):
        candidate = self.folder / "IMG_crop.tif"

        self.assertEqual(plan_output_paths([candidate]), [candidate])

    def test_numbers_after_existing_base(self):
        candidate = self.folder / "IMG_crop.tif"
        candidate.write_bytes(b"existing")

        self.assertEqual(
            plan_output_paths([candidate]),
            [self.folder / "IMG_crop_2.tif"],
        )

    def test_skips_existing_numbered_candidates(self):
        candidate = self.folder / "IMG_crop.tif"
        candidate.write_bytes(b"existing")
        (self.folder / "IMG_crop_2.tif").write_bytes(b"existing-2")

        self.assertEqual(
            plan_output_paths([candidate]),
            [self.folder / "IMG_crop_3.tif"],
        )

    def test_reserves_duplicates_within_batch(self):
        candidate = self.folder / "IMG_crop.tif"

        self.assertEqual(
            plan_output_paths([candidate, candidate, candidate]),
            [
                candidate,
                self.folder / "IMG_crop_2.tif",
                self.folder / "IMG_crop_3.tif",
            ],
        )

    def test_reservations_are_case_insensitive(self):
        upper = self.folder / "IMG_crop.tif"
        lower = self.folder / "img_crop.tif"

        self.assertEqual(
            plan_output_paths([upper, lower]),
            [upper, self.folder / "img_crop_2.tif"],
        )

    def test_existing_names_are_case_insensitive(self):
        (self.folder / "IMG_crop.tif").write_bytes(b"existing")
        candidate = self.folder / "img_crop.tif"

        self.assertEqual(
            plan_output_paths([candidate]),
            [self.folder / "img_crop_2.tif"],
        )

    def test_directory_occupies_candidate(self):
        candidate = self.folder / "IMG_crop.tif"
        candidate.mkdir()

        self.assertEqual(
            plan_output_paths([candidate]),
            [self.folder / "IMG_crop_2.tif"],
        )

    def test_require_output_available_rejects_existing_path(self):
        candidate = self.folder / "IMG_crop.tif"
        candidate.write_bytes(b"existing")

        with self.assertRaisesRegex(FileExistsError, "IMG_crop\\.tif"):
            require_output_available(candidate)


if __name__ == "__main__":
    unittest.main()
