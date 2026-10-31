import unittest
from pathlib import Path

from film_version import VERSION


EXPECTED_VERSION = "1.9.1"
ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_runtime_version_matches_release(self):
        self.assertEqual(VERSION, EXPECTED_VERSION)

    def test_primary_user_documents_match_release(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        usage = (ROOT / "使用说明.txt").read_text(encoding="utf-8").splitlines()
        technical = (ROOT / "技术说明.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual(readme[0], f"# FilmCrop {EXPECTED_VERSION}")
        self.assertEqual(usage[0], f"FilmCrop {EXPECTED_VERSION}")
        self.assertEqual(
            technical[0],
            f"胶片裁切 FilmCrop-RAW {EXPECTED_VERSION} · Windows 64 位便携版",
        )
        self.assertEqual(
            technical[2],
            f"1. 双击 FilmCrop-RAW-{EXPECTED_VERSION}.exe，无需安装 Python。",
        )

    def test_macos_artifact_references_match_release(self):
        guide = (ROOT / "MACOS-ARM.md").read_text(encoding="utf-8")
        workflow = (
            ROOT / ".github" / "workflows" / "build-macos-arm64.yml"
        ).read_text(encoding="utf-8")
        artifact = f"FilmCrop-RAW-{EXPECTED_VERSION}-mac-arm64"

        self.assertIn(artifact, guide)
        self.assertIn(f"name: {artifact}", workflow)


if __name__ == "__main__":
    unittest.main()
