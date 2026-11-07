"""Regression coverage for off-center film on a bright scanning canvas."""
import unittest
import cv2
import numpy as np
from film_sprockets import paired_perforations


class OffCenterPerforationsTests(unittest.TestCase):
    def test_low_contrast_holes_with_large_white_canvas(self):
        for hole, film in ((2, 24), (18, 39)):
            image = np.full((800, 1200, 3), 255, np.uint8)
            image[180:745, 80:1120] = film
            image[262:643, 145:1034] = 110
            for x in range(105, 1100, 74):
                for y in (224, 666):
                    cv2.ellipse(image, (x, y), (15, 22), 0, 0, 360,
                                (hole, hole, hole), -1)
            for turn in range(4):
                with self.subTest(hole=hole, turn=turn):
                    rotated = np.ascontiguousarray(np.rot90(image, turn))
                    result = paired_perforations(rotated)
                    self.assertIsNotNone(result)
                    self.assertEqual(result['polarity'], 'dark')
                    self.assertLess(abs(result['angle']), .1)
                    self.assertAlmostEqual(max(result['box'][2:]), 74 * 36 / 4.75, delta=3)


if __name__ == '__main__':
    unittest.main()
