import unittest

import numpy as np

from film_boundaries import surrounded_frame
from film_crop import FORMATS


class UniformSurroundTests(unittest.TestCase):
    def test_all_formats_both_orientations(self):
        for fmt, ratio in FORMATS.items():
            ratio = max(ratio, 1/ratio)
            fw, fh = 700, round(700/ratio)
            image = np.full((fh+100, fw+160, 3), 12, np.uint8)
            rng = np.random.default_rng(10)
            image[50:50+fh, 80:80+fw] = rng.integers(
                45, 200, (fh, fw, 3), dtype=np.uint8)
            for turn in (0, 1):
                with self.subTest(format=fmt, turn=turn):
                    rotated = np.ascontiguousarray(np.rot90(image, turn))
                    result = surrounded_frame(rotated)
                    self.assertIsNotNone(result)
                    self.assertEqual(result['format'], fmt)
                    expected = [80,50,fw,fh] if not turn else [50,80,fh,fw]
                    np.testing.assert_allclose(result['box'], expected, atol=5)
                    forced = surrounded_frame(rotated, fmt)
                    self.assertEqual(forced['box'], result['box'])

    def test_no_edges_cannot_invent_a_frame(self):
        image = np.full((600, 900, 3), 12, np.uint8)
        self.assertIsNone(surrounded_frame(image))
        for fmt in FORMATS:
            self.assertIsNone(surrounded_frame(image, fmt))

    def test_one_visible_edge_cannot_infer_format(self):
        image = np.full((600, 900, 3), 12, np.uint8)
        image[:, 100:] = 100
        self.assertIsNone(surrounded_frame(image))


if __name__ == '__main__':
    unittest.main()
