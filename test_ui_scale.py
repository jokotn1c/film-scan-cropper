import unittest

class ScaleTests(unittest.TestCase):
    def test_scale_tracks_limiting_dimension(self):
        from film_ui_scale import layout_scale
        self.assertAlmostEqual(layout_scale(1440, 900), 1.0)
        self.assertAlmostEqual(layout_scale(1080, 675), .75)
        self.assertAlmostEqual(layout_scale(1800, 1125), 1.25)
        self.assertAlmostEqual(layout_scale(1440, 675), .75)

    def test_font_selection_has_fallback(self):
        from film_ui_scale import choose_latin_font
        self.assertEqual(choose_latin_font(['EB Garamond', 'Georgia']), 'EB Garamond')
        self.assertEqual(choose_latin_font(['Georgia']), 'Georgia')

    def test_chinese_font_preference_and_fallback(self):
        from film_ui_scale import choose_chinese_font
        self.assertEqual(choose_chinese_font(['Songti SC', 'Microsoft YaHei UI']), 'Microsoft YaHei UI')
        self.assertEqual(choose_chinese_font(['微软雅黑', '宋体']), '微软雅黑')
        self.assertEqual(choose_chinese_font(['Songti SC', 'PingFang SC']), 'PingFang SC')
        self.assertEqual(choose_chinese_font(['Georgia']), 'TkDefaultFont')
