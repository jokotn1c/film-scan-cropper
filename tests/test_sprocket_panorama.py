"""Regression coverage for off-center film on a bright scanning canvas."""
import unittest
import cv2
import numpy as np
from film_sprockets import paired_perforations
from film_engine import locate


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


class NearBlackPerforationsTests(unittest.TestCase):
    def image(self):
        image = np.full((800, 1200, 3), 255, np.uint8)
        image[180:745, 80:1120] = 0
        image[262:643, 145:1034] = 100
        image[262:643, 145:400] = 2
        # Interior scene edges are stronger than the left picture boundary.
        for x in range(440, 950, 40):
            image[262:643, x:x+12] = 45
        for x in range(105, 1100, 74):
            for y in (224, 666):
                cv2.ellipse(image, (x, y), (18, 25), 0, 0, 360, (6, 6, 6), -1)
                cv2.ellipse(image, (x, y), (15, 22), 0, 0, 360, (0, 0, 0), -1)
        return image

    def test_dark_holes_recover_wide_frame_with_faint_end(self):
        image = self.image()
        for turn in range(4):
            with self.subTest(turn=turn):
                rotated = np.ascontiguousarray(np.rot90(image, turn))
                evidence = paired_perforations(rotated)
                self.assertIsNotNone(evidence)
                self.assertTrue(evidence['low_contrast'])
                detection = locate(rotated, 'auto')
                self.assertEqual(detection['format'], '5.6x2.4')
                x0,x1,y0,y1 = detection['bounds']
                if turn % 2:
                    self.assertLess(detection['ratio'], 1)
                    self.assertAlmostEqual(x1-x0, 381, delta=8)
                    self.assertAlmostEqual(y1-y0, 889, delta=8)
                else:
                    self.assertGreater(detection['ratio'], 1)
                    self.assertAlmostEqual(x1-x0, 889, delta=8)
                    self.assertAlmostEqual(y1-y0, 381, delta=8)

    def test_single_row_is_not_enough_to_infer_film(self):
        image = self.image()
        image[640:710, 80:1120] = 0
        self.assertIsNone(paired_perforations(image))


if __name__ == '__main__':
    unittest.main()
