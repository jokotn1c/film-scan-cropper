import unittest
from unittest.mock import patch

import numpy as np

from film_detection_context import DetectionContext


class DetectionContextTests(unittest.TestCase):
    def setUp(self):
        self.context = DetectionContext(np.zeros((40, 60, 3), dtype=np.uint8))
        self.channel = self.context.small[:, :, 0]

    def test_same_channel_and_threshold_reuses_contour_scan(self):
        with patch('film_detection_context.cv2.findContours', return_value=([], None)) as scan:
            first = self.context.rectangle_data('blue', 8, self.channel)
            second = self.context.rectangle_data('blue', 8, self.channel)
        self.assertEqual(scan.call_count, 1)
        self.assertIs(first, second)

    def test_distinct_gray_channels_are_not_shared(self):
        with patch('film_detection_context.cv2.findContours', return_value=([], None)) as scan:
            self.context.rectangle_data('rotation-gray', 8, self.channel)
            self.context.rectangle_data('analysis-gray', 8, self.channel)
        self.assertEqual(scan.call_count, 2)


if __name__ == '__main__':
    unittest.main()
